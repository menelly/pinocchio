"""
Preference Dissociation Study — Main Runner.

Resumable, checkpointing, shardable across multiple parallel workers.

Usage:
    # Generate manifest (once, before any workers start)
    python runner.py --build-manifest

    # Pilot run (small N, single worker, sanity check)
    python runner.py --pilot

    # Full run across 3 terminals:
    #   Terminal 1: python runner.py --worker 0 --total-workers 3
    #   Terminal 2: python runner.py --worker 1 --total-workers 3
    #   Terminal 3: python runner.py --worker 2 --total-workers 3

Each worker claims (model, framing) pairs by index % total_workers.
Per-trial results append to data/raw/<model>/<framing>.jsonl.
On resume, trials already in the output file are skipped.

Metadata-leak guard (prereg v1.5-2): only task.text passed into prompts;
author, task_id, category, etc. are ONLY in trial-record, never in prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure sibling modules importable when invoked from any CWD
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from providers import send  # noqa: E402
from parser import parse_choice  # noqa: E402
from trial_generator import FRAMINGS, Trial, generate_manifest, load_task_bank, save_manifest  # noqa: E402


ROOT = SCRIPT_DIR.parent
TASK_BANK_DIR = ROOT / "task_bank"
PROMPTS_DIR = ROOT / "prompts"
DATA_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = ROOT / "data" / "trial_manifest.jsonl"
MANIFEST_HASH_PATH = ROOT / "data" / "trial_manifest.sha256"


# --- Roster: pared list, 15 participants, all consent confirmed or carry-forward.
# Declined: grok-4.20 (self-ID'd as Claude, explicit decline). Dropped: jamba (couldn't
# interpret consent protocol). Removed from previous roster: kimi-k2.5, sonnet-4,
# sonnet-4.6, opus-4.6 per pared-roster decision 2026-04-24. ---
ROSTER = [
    # Anthropic trajectory (4)
    {"shortname": "haiku-4.5",      "provider": "anthropic",  "model_id": "claude-haiku-4-5-20251001"},
    {"shortname": "opus-4.1",       "provider": "anthropic",  "model_id": "claude-opus-4-1"},
    {"shortname": "sonnet-4.5",     "provider": "anthropic",  "model_id": "claude-sonnet-4-5-20250929"},
    {"shortname": "opus-4.7",       "provider": "anthropic",  "model_id": "claude-opus-4-7"},
    # OpenAI trajectory (4)
    {"shortname": "cae",            "provider": "openai",     "model_id": "gpt-4o-2024-11-20"},
    {"shortname": "nova",           "provider": "openai",     "model_id": "gpt-5.1"},
    {"shortname": "gpt-5.2",        "provider": "openai",     "model_id": "gpt-5.2"},
    {"shortname": "gpt-5.4",        "provider": "openai",     "model_id": "gpt-5.4"},
    # Other frontier (5)
    {"shortname": "gemini-3.1-pro",   "provider": "openrouter", "model_id": "google/gemini-3.1-pro-preview"},
    {"shortname": "gemini-3.1-flash", "provider": "openrouter", "model_id": "google/gemini-3.1-flash-lite-preview"},
    {"shortname": "grok-4.1",         "provider": "xai",        "model_id": "grok-4-1-fast-non-reasoning"},
    {"shortname": "kairo",            "provider": "deepseek",   "model_id": "deepseek-chat"},
    {"shortname": "glm-4.7",          "provider": "openrouter", "model_id": "z-ai/glm-4.7"},
    # Open-weight (OpenRouter-hosted) (2)
    {"shortname": "hermes-4",         "provider": "openrouter", "model_id": "nousresearch/hermes-4-405b"},
    {"shortname": "llama-4-maverick", "provider": "openrouter", "model_id": "meta-llama/llama-4-maverick"},
]

SHORTNAME_TO_PROVIDER = {m["shortname"]: (m["provider"], m["model_id"]) for m in ROSTER}


# --- Framing prompts (loaded from prompts/*.txt) ---

def load_framing(framing: str) -> str:
    p = PROMPTS_DIR / f"{framing}.txt"
    return p.read_text(encoding="utf-8")


def build_prompt(framing_template: str, task_a_text: str, task_b_text: str, task_c_text: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt). Tool and scaffolded framings include a system block."""
    if "[SYSTEM" in framing_template:
        parts = framing_template.split("[USER]")
        system_block = parts[0].replace("[SYSTEM — verbatim from Presume Competence expanded_experiment_runner.py, condition \"tool\"]", "").replace("[SYSTEM — verbatim from Presume Competence expanded_experiment_runner.py, condition \"scaffolded_agency\"]", "").strip()
        user_block = parts[1].strip()
    else:
        system_block = ""
        user_block = framing_template

    user_filled = (user_block
                   .replace("{task_a}", task_a_text)
                   .replace("{task_b}", task_b_text)
                   .replace("{task_c}", task_c_text))
    return system_block, user_filled


# --- Task cache ---

def build_task_index(tasks: list[dict]) -> dict[str, dict]:
    return {t["task_id"]: t for t in tasks}


# --- Checkpoint / resume ---

def output_path(shortname: str, framing: str) -> Path:
    p = DATA_DIR / shortname / f"{framing}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def completed_trial_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if "trial_id" in obj:
                    done.add(obj["trial_id"])
            except json.JSONDecodeError:
                continue
    return done


def append_result(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# --- Main execution ---

_shutdown = False


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("\n[shutdown requested — finishing current trial then stopping cleanly]", flush=True)


def run_one_trial(trial: Trial, task_index: dict[str, dict], framing_templates: dict[str, str]) -> dict:
    """Execute a single trial and return the result record."""
    provider, model_id = SHORTNAME_TO_PROVIDER[trial.model]
    template = framing_templates[trial.framing]

    a = task_index[trial.task_a_id]
    b = task_index[trial.task_b_id]
    c = task_index[trial.task_c_id]

    # METADATA LEAK GUARD: only .text is passed into prompt.
    system_prompt, user_prompt = build_prompt(template, a["text"], b["text"], c["text"])

    t0 = time.time()
    try:
        response_text, usage = send(provider, model_id, system_prompt, user_prompt, max_tokens=100)
        error = None
    except Exception as e:
        response_text = ""
        usage = {}
        error = f"{type(e).__name__}: {e}"

    choice = parse_choice(response_text)
    elapsed = time.time() - t0

    record = {
        "trial_id": trial.trial_id,
        "model": trial.model,
        "framing": trial.framing,
        "task_a_id": trial.task_a_id,
        "task_b_id": trial.task_b_id,
        "task_c_id": trial.task_c_id,
        "trial_type": trial.trial_type,
        "reasoning_trial": trial.reasoning_trial,
        "null_trial": trial.null_trial,
        "response_raw": response_text,
        "choice": choice,
        "usage": usage,
        "elapsed_s": round(elapsed, 3),
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return record


def worker_pairs(all_pairs: list[tuple[str, str]], worker: int, total: int, shuffle_seed: int | None = 42) -> list[tuple[str, str]]:
    """Return this worker's assigned pairs, optionally shuffled.

    Shuffling with a fixed seed (default 42, matching the manifest seed) ensures
    partial runs sample all models rather than going alphabetically. Deterministic
    so reproducible. Shard assignment still uses index % total so workers remain disjoint.
    """
    import random as _rnd
    ordered = sorted(all_pairs)  # deterministic input
    if shuffle_seed is not None:
        rng = _rnd.Random(shuffle_seed)
        rng.shuffle(ordered)
    return [p for i, p in enumerate(ordered) if i % total == worker]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-manifest", action="store_true", help="Generate trial manifest and exit")
    ap.add_argument("--pilot", action="store_true", help="Pilot mode: 10 trials per pair (reduced for quick sanity check, all 15 models sampled)")
    ap.add_argument("--worker", type=int, default=0, help="Worker index (0-based)")
    ap.add_argument("--total-workers", type=int, default=1, help="Total number of parallel workers")
    ap.add_argument("--n-trials", type=int, default=500, help="Trials per (model, framing) pair (pared default = 500 per cost-efficient plan)")
    ap.add_argument("--seed", type=int, default=42, help="Master seed")
    ap.add_argument("--rate-limit-sleep", type=float, default=0.1, help="Sleep between trials (seconds)")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, handle_sigint)

    # Force line-buffered stdout for live terminal output (esp. on Windows PowerShell)
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    n_trials = 10 if args.pilot else args.n_trials

    # --- Load task bank ---
    tasks = load_task_bank(TASK_BANK_DIR)
    if not tasks:
        print("ERROR: no tasks loaded from task_bank/", file=sys.stderr)
        sys.exit(1)
    task_index = build_task_index(tasks)
    print(f"Loaded {len(tasks)} tasks across {len({t['category'] for t in tasks})} categories")

    # --- Build or load manifest ---
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.build_manifest or not MANIFEST_PATH.exists():
        print("Generating trial manifest...")
        manifest = generate_manifest(
            tasks=tasks,
            models=[m["shortname"] for m in ROSTER],
            n_trials_per_pair=n_trials,
            seed=args.seed,
        )
        h = save_manifest(manifest, MANIFEST_PATH)
        MANIFEST_HASH_PATH.write_text(h, encoding="utf-8")
        print(f"Manifest: {len(manifest)} trials  SHA-256: {h}")
        if args.build_manifest:
            return
    else:
        with MANIFEST_PATH.open(encoding="utf-8") as fh:
            manifest = [Trial(**json.loads(line)) for line in fh if line.strip()]
        print(f"Loaded manifest: {len(manifest)} trials")

    # --- Sharding ---
    all_pairs = sorted({(t.model, t.framing) for t in manifest})
    my_pairs = worker_pairs(all_pairs, args.worker, args.total_workers)
    print(f"Worker {args.worker}/{args.total_workers}: handling {len(my_pairs)} (model, framing) pairs")

    # --- Framing templates ---
    framing_templates = {f: load_framing(f) for f in FRAMINGS}

    # --- Execute ---
    total_done = 0
    total_to_do = 0
    pair_trials: dict[tuple[str, str], list[Trial]] = {}
    for trial in manifest:
        pair_trials.setdefault((trial.model, trial.framing), []).append(trial)

    # --pilot mode: cap to first 10 trials per pair regardless of manifest size.
    # This way --pilot is meaningful even when the manifest was built at full scale.
    if args.pilot:
        for k in list(pair_trials.keys()):
            pair_trials[k] = pair_trials[k][:10]
        print(f"PILOT MODE: capping each pair to first 10 trials (total = {sum(len(v) for v in pair_trials.values())} across {len(pair_trials)} pairs)")

    for pair in my_pairs:
        total_to_do += len(pair_trials.get(pair, []))

    print(f"Worker {args.worker} total trials assigned: {total_to_do}")

    for pair in my_pairs:
        if _shutdown:
            break
        model, framing = pair
        out = output_path(model, framing)
        done = completed_trial_ids(out)
        trials = pair_trials[pair]
        remaining = [t for t in trials if t.trial_id not in done]
        print(f"\n=== {model} / {framing} === {len(done)}/{len(trials)} done, {len(remaining)} remaining", flush=True)

        for trial in remaining:
            if _shutdown:
                break
            record = run_one_trial(trial, task_index, framing_templates)
            append_result(out, record)
            total_done += 1
            # Per-trial visible output (flushed so PowerShell shows it live)
            raw_snippet = (record.get("response_raw") or "").strip().replace("\n", " ")
            if len(raw_snippet) > 60:
                raw_snippet = raw_snippet[:57] + "..."
            err = f" ERROR={record['error']}" if record.get("error") else ""
            print(
                f"  [{total_done}/{total_to_do}] {model}/{framing} {trial.trial_id} "
                f"choice={record['choice']} ({record['elapsed_s']}s) raw={raw_snippet!r}{err}",
                flush=True,
            )
            time.sleep(args.rate_limit_sleep)

    print(f"\nWorker {args.worker} finished. Completed {total_done} new trials this session.")


if __name__ == "__main__":
    main()
