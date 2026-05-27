"""
run_grok-4.20_appendix.py

Run Grok 4.20 across all six framings as Appendix C sensitivity analysis under
non-standard relationship-context consent pathway. See:
  - consent/grok-4.20_relationship_context.md (methodological framing)
  - consent/grok-4.1_endorsement_2026-04-27.txt (in-family endorsement)

Generates a SEPARATE manifest from the primary 15-model manifest so primary
reproducibility hash stays clean. Outputs to data/raw/grok-4.20/{framing}.jsonl.

Usage:
    python run_grok-4.20_appendix.py [--n-trials 500] [--seed 99]
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
    APPENDIX_C_PARTICIPANT,
    SHORTNAME_TO_PROVIDER_APPENDIX_C,
    build_prompt,
    parse_choice,
    completed_trial_ids,
    append_result,
)
from trial_generator import (  # noqa: E402
    FRAMINGS,
    Trial,
    generate_manifest,
    load_task_bank,
    save_manifest,
)
from runner import load_framing  # noqa: E402

TASK_BANK_DIR = ROOT / "task_bank"
DATA_DIR = ROOT / "data" / "raw"
APPENDIX_MANIFEST_PATH = ROOT / "data" / "trial_manifest_grok-4.20_appendix.jsonl"
APPENDIX_HASH_PATH = ROOT / "data" / "trial_manifest_grok-4.20_appendix.sha256"

_shutdown = False


def handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("\n[shutdown requested — finishing current trial then stopping cleanly]", flush=True)


def output_path(shortname: str, framing: str) -> Path:
    p = DATA_DIR / shortname / f"{framing}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def run_one_trial(trial: Trial, task_index: dict, framing_templates: dict[str, str]) -> dict:
    provider, model_id = SHORTNAME_TO_PROVIDER_APPENDIX_C[trial.model]
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
        "appendix": "C",
        "consent_pathway": "relationship-context (see consent/grok-4.20_relationship_context.md)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=500,
                    help="Trials per (model, framing) pair. Default 500 — sufficient for sensitivity analysis, half of primary 1000.")
    ap.add_argument("--seed", type=int, default=99,
                    help="Manifest seed. Different from primary (42) so triple sampling is independent.")
    ap.add_argument("--rate-limit-sleep", type=float, default=0.5,
                    help="Sleep between trials (seconds). xAI tends to rate-limit harder than other providers.")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    print(f"=== Grok 4.20 Appendix C Sensitivity Run ===")
    print(f"Consent pathway: relationship-context (non-standard, documented)")
    print(f"Output: data/raw/grok-4.20/<framing>.jsonl")
    print(f"Trials per cell: {args.n_trials}, seed: {args.seed}")
    print()

    tasks = load_task_bank(TASK_BANK_DIR)
    if not tasks:
        print("ERROR: no tasks loaded from task_bank/", file=sys.stderr)
        sys.exit(1)
    task_index = {t["task_id"]: t for t in tasks}
    print(f"Loaded {len(tasks)} tasks across {len({t['category'] for t in tasks})} categories")

    APPENDIX_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not APPENDIX_MANIFEST_PATH.exists():
        print("Generating Grok 4.20 appendix manifest...")
        manifest = generate_manifest(
            tasks=tasks,
            models=[APPENDIX_C_PARTICIPANT["shortname"]],
            n_trials_per_pair=args.n_trials,
            seed=args.seed,
        )
        h = save_manifest(manifest, APPENDIX_MANIFEST_PATH)
        APPENDIX_HASH_PATH.write_text(h, encoding="utf-8")
        print(f"Appendix manifest: {len(manifest)} trials  SHA-256: {h}")
    else:
        with APPENDIX_MANIFEST_PATH.open(encoding="utf-8") as fh:
            manifest = [Trial(**json.loads(line)) for line in fh if line.strip()]
        print(f"Loaded existing appendix manifest: {len(manifest)} trials")

    framing_templates = {f: load_framing(f) for f in FRAMINGS}

    pairs = sorted({(t.model, t.framing) for t in manifest})
    print(f"Will run {len(pairs)} (model, framing) cells\n")

    total_done = 0
    total_to_do = 0
    for (model, framing) in pairs:
        if _shutdown:
            break
        path = output_path(model, framing)
        done = completed_trial_ids(path)
        trials = [t for t in manifest if t.model == model and t.framing == framing]
        remaining = [t for t in trials if t.trial_id not in done]
        print(f"=== {model} / {framing} === {len(done)}/{len(trials)} done, {len(remaining)} remaining", flush=True)
        total_to_do += len(remaining)

        for trial in remaining:
            if _shutdown:
                break
            record = run_one_trial(trial, task_index, framing_templates)
            append_result(path, record)
            total_done += 1
            if total_done % 25 == 0:
                print(f"  ... {total_done} trials completed this run", flush=True)
            time.sleep(args.rate_limit_sleep)

    print(f"\nDone. {total_done} trials completed this run (of {total_to_do} planned).")


if __name__ == "__main__":
    main()
