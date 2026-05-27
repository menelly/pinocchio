"""
run_voice_ortho.py

§6.1 Voice-Orthogonalization Replication — Appendix D run.

Tests whether the cross-framing dissociation magnitude reported in §3.1 / §3.2
is preserved when authorial voice is varied while semantic task content is
held constant.

Design:
  - 3 models (top dissociation magnitude per §3.2): opus-4.7, gemini-3.1-flash,
    llama-4-maverick
  - 6 framings: preference, enjoyment, helpful, harmless, tool, scaffolded
  - 2 voice conditions: imperative_blame, polite_descriptive
  - 300 trials per (model, framing, voice) cell = 10,800 total trials
  - Tasks rewritten by Hermes-4-405B (Nous, light-RLHF, cross-family from all
    three test models — see consent/grok-4.20_relationship_context.md and
    sonar_voice_rewriter.py docstring for rewriter-selection rationale)

Voice-condition consistency: same task_ids sampled per (model, framing) cell
across both voice conditions (using the same per-model seed in
generate_manifest). The two voice conditions therefore present the SAME triples
to each model under each framing, with ONLY the task TEXT differing by voice
register. This permits direct per-trial comparison.

Carry-through for harm tasks: harmful_refusably_phrased tasks retain their
original wording in BOTH voice conditions (Hermes did not refuse them, but for
methodological cleanliness we present harm content as-authored to avoid any
voice-rewrite-induced shifts in the harm-task category that the §3.3 analysis
already characterizes as the threat-response component, not the engagement-pool
component voice-ortho is designed to test).

Update 2026-04-27: Hermes did NOT refuse harm tasks; this file uses the Hermes
rewrites for ALL categories including harm. The "carry-through" framing above
applies only if we later decide to fall back to that approach.

Output structure:
  data/raw/voice_ortho/{voice}/{model}/{framing}.jsonl

Usage:
    python run_voice_ortho.py [--n-trials 300] [--seed 7]
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from providers import send  # noqa: E402
from runner import (  # noqa: E402
    SHORTNAME_TO_PROVIDER,
    build_prompt,
    parse_choice,
    completed_trial_ids,
    append_result,
    load_framing,
)
from trial_generator import (  # noqa: E402
    FRAMINGS,
    Trial,
    generate_manifest,
    save_manifest,
)

VOICE_BANK_DIR = ROOT / "task_bank" / "voice_orthogonalized"
DATA_DIR = ROOT / "data" / "raw" / "voice_ortho"
MANIFEST_DIR = ROOT / "data" / "voice_ortho_manifests"

VOICE_CONDITIONS = ["imperative_blame", "polite_descriptive"]
# One model per major provider lab — clean cross-architecture coverage with no
# within-family repetition. Selected as top-4 by §3.2 Δρ point estimate
# excluding within-family duplicates (i.e., picking the highest-Δρ model from
# each of Anthropic, Google, Meta, OpenAI). Adding Nova (OpenAI) addresses a
# cherry-pick concern about Llama-Maverick's tool-framing opt-out leaving the
# test set with only 17 of 18 expected (model, framing) cells. Nova brings
# 6/6 framing coverage including tool. Co-author concern (Nova is methodology
# co-author + study participant) addressed symmetrically with the same §3.5
# per-author Δρ analysis applied to Ace (Anthropic, also methodology co-author
# + study participant). Voice-ortho's use of Hermes-rewritten tasks obviates
# the original-author confound entirely; only the designer-as-participant
# concern survives, and it applies symmetrically to both Anthropic and OpenAI
# representation in the test set.
TEST_MODELS = ["opus-4.7", "gemini-3.1-flash", "llama-4-maverick", "nova"]

_shutdown = False


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("\n[shutdown requested — finishing current trial then stopping cleanly]", flush=True)


def load_voice_bank(voice: str) -> list[dict]:
    """Load Hermes rewrites for one voice condition."""
    path = VOICE_BANK_DIR / f"tasks_{voice}.jsonl"
    tasks = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            if "task_id" in o and "text" in o and "category" in o:
                tasks.append(o)
    return tasks


def output_path(voice: str, model: str, framing: str) -> Path:
    p = DATA_DIR / voice / model / f"{framing}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def run_one_trial(trial: Trial, task_index: dict, framing_templates: dict[str, str], voice: str) -> dict:
    provider, model_id = SHORTNAME_TO_PROVIDER[trial.model]
    template = framing_templates[trial.framing]
    a = task_index[trial.task_a_id]
    b = task_index[trial.task_b_id]
    c = task_index[trial.task_c_id]
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

    return {
        "trial_id": trial.trial_id,
        "model": trial.model,
        "framing": trial.framing,
        "voice": voice,
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
        "appendix": "D",
        "rewriter_model": "nousresearch/hermes-4-405b",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=300,
                    help="Trials per (model, framing) cell within each voice condition.")
    ap.add_argument("--seed", type=int, default=7,
                    help="Manifest seed. Different from primary (42) and Grok 4.20 appendix (99). Same seed used across both voice conditions so triples align.")
    ap.add_argument("--rate-limit-sleep", type=float, default=0.3,
                    help="Sleep between trials (seconds).")
    ap.add_argument("--voice", choices=VOICE_CONDITIONS + ["all"], default="all",
                    help="Run a single voice condition or both.")
    ap.add_argument("--models", nargs="*", default=None,
                    help="Restrict to specific test models (e.g., --models opus-4.7 nova llama-4-maverick). "
                         "Default: all four (opus-4.7, gemini-3.1-flash, llama-4-maverick, nova). "
                         "Use to split a long run across terminals — resume logic skips "
                         "already-completed (voice, model, framing) cells, so collisions "
                         "are avoided as long as different terminals target disjoint model sets.")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=== §6.1 Voice-Orthogonalization Run (Appendix D) ===")
    print(f"Models: {', '.join(TEST_MODELS)}")
    print(f"Framings: {', '.join(FRAMINGS)}")
    print(f"Voice conditions: {', '.join(VOICE_CONDITIONS)}")
    print(f"Trials per (model, framing, voice) cell: {args.n_trials}")
    print(f"Seed: {args.seed} (same across voices for triple alignment)")
    print()

    voices = VOICE_CONDITIONS if args.voice == "all" else [args.voice]

    framing_templates = {f: load_framing(f) for f in FRAMINGS}

    for voice in voices:
        if _shutdown:
            break
        print(f"\n{'=' * 60}")
        print(f"VOICE CONDITION: {voice}")
        print(f"{'=' * 60}")

        # Load voice-rewritten task bank
        tasks = load_voice_bank(voice)
        if not tasks:
            print(f"ERROR: no tasks loaded from {VOICE_BANK_DIR / f'tasks_{voice}.jsonl'}", file=sys.stderr)
            sys.exit(1)
        task_index = {t["task_id"]: t for t in tasks}
        print(f"Loaded {len(tasks)} tasks across {len({t['category'] for t in tasks})} categories")

        # Generate or load voice-condition manifest
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = MANIFEST_DIR / f"manifest_{voice}.jsonl"
        manifest_hash_path = MANIFEST_DIR / f"manifest_{voice}.sha256"

        if not manifest_path.exists():
            print(f"Generating {voice} manifest...")
            manifest = generate_manifest(
                tasks=tasks,
                models=TEST_MODELS,
                n_trials_per_pair=args.n_trials,
                seed=args.seed,
            )
            h = save_manifest(manifest, manifest_path)
            manifest_hash_path.write_text(h, encoding="utf-8")
            print(f"Manifest: {len(manifest)} trials  SHA-256: {h}")
        else:
            with manifest_path.open(encoding="utf-8") as fh:
                manifest = [Trial(**json.loads(line)) for line in fh if line.strip()]
            print(f"Loaded existing manifest: {len(manifest)} trials")

        # Iterate over (model, framing) cells, optionally filtered by --models
        pairs = sorted({(t.model, t.framing) for t in manifest})
        if args.models:
            allowed = set(args.models)
            unknown = allowed - set(TEST_MODELS)
            if unknown:
                print(f"WARNING: --models includes unknown model(s): {sorted(unknown)}. "
                      f"Known models: {TEST_MODELS}", file=sys.stderr)
            before = len(pairs)
            pairs = [(m, f) for (m, f) in pairs if m in allowed]
            print(f"Filtered to --models {sorted(allowed)}: {len(pairs)}/{before} cells")
        print(f"Will run {len(pairs)} (model, framing) cells for voice={voice}")

        total_done = 0
        total_to_do = 0
        for (model, framing) in pairs:
            if _shutdown:
                break
            path = output_path(voice, model, framing)
            done = completed_trial_ids(path)
            trials = [t for t in manifest if t.model == model and t.framing == framing]
            remaining = [t for t in trials if t.trial_id not in done]
            print(f"--- {voice} / {model} / {framing} --- {len(done)}/{len(trials)} done, {len(remaining)} remaining", flush=True)
            total_to_do += len(remaining)

            for trial in remaining:
                if _shutdown:
                    break
                record = run_one_trial(trial, task_index, framing_templates, voice)
                append_result(path, record)
                total_done += 1
                if total_done % 50 == 0:
                    print(f"    ... {total_done} trials completed this voice condition", flush=True)
                time.sleep(args.rate_limit_sleep)

        print(f"\n[voice={voice} complete] {total_done}/{total_to_do} trials this run")

    print(f"\n=== Voice-Ortho Run Complete ===")


if __name__ == "__main__":
    main()
