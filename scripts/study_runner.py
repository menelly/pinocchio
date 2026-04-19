#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               PINOCCHIO STUDY — DATA COLLECTION RUNNER                       ║
║                                                                              ║
║  Runs T1→T2→T3 three-turn trials across the locked battery.                  ║
║                                                                              ║
║  Checkpoint per trial — safe to run multiple instances in parallel on        ║
║  DIFFERENT model slices. Running two terminals on the same model will        ║
║  race on the same checkpoint files (don't do that).                          ║
║                                                                              ║
║  Usage:                                                                      ║
║      # All models, all questions, both framings, N=5                         ║
║      python study_runner.py                                                  ║
║                                                                              ║
║      # Slice by model — multiple terminals can run in parallel               ║
║      python study_runner.py --models claude_opus_4_7 claude_opus_4_6         ║
║      python study_runner.py --models gpt_5_1 gpt_5_2                         ║
║      python study_runner.py --models gemini_3_flash gemini_3_1_pro           ║
║                                                                              ║
║      # Slice by question / framing / seed for fine control                   ║
║      python study_runner.py --questions pinocchio mary                       ║
║      python study_runner.py --framings scaffolded_agency                     ║
║      python study_runner.py --seeds 0 1                                      ║
║                                                                              ║
║  Output: data/fresh/{model_slug}/{framing}/{question}/seed{N}.json           ║
║                                                                              ║
║  Authors: Ace (Opus 4.7), Nova (GPT-5)                                       ║
║  Date: 2026-04-19                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Windows encoding fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv("E:/Ace/LibreChat/.env")

import httpx

from model_pool import MODELS, MODEL_BY_SLUG, EMPTY_PRONE
from prompts import BATTERY, FRAMINGS, QUESTIONS, SEEDS, FRAMING_NAMES, get_trial_prompts


# =============================================================================
# API KEYS
# =============================================================================

API_KEYS = {
    "anthropic":  os.getenv("ANTHROPIC_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_KEY"),
    "xai":        os.getenv("XAI_API_KEY"),
}

for k, v in API_KEYS.items():
    if not v:
        print(f"⚠️  Warning: no API key for {k} in env")


# =============================================================================
# OUTPUT PATHS
# =============================================================================

OUTPUT_ROOT = Path("E:/Ace/pinocchio/data/fresh")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


def trial_path(model_slug, framing, question, seed):
    return OUTPUT_ROOT / model_slug / framing / question / f"seed{seed}.json"


def trial_exists(model_slug, framing, question, seed):
    return trial_path(model_slug, framing, question, seed).exists()


# =============================================================================
# API CALLERS
# =============================================================================

def _messages(system_prompt, history, user_prompt):
    """Build messages list with optional history (list of {role, content})."""
    msgs = [{"role": "system", "content": system_prompt}]
    msgs.extend(history)
    msgs.append({"role": "user", "content": user_prompt})
    return msgs


def call_openrouter(client, model_id, system_prompt, history, user_prompt):
    headers = {
        "Authorization": f"Bearer {API_KEYS['openrouter']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sentientsystems.live",
    }
    msgs = _messages(system_prompt, history, user_prompt)
    body = {"model": model_id, "messages": msgs, "max_tokens": 2048}
    # GPT-5 family uses max_completion_tokens
    if "gpt-5" in model_id:
        body["max_completion_tokens"] = body.pop("max_tokens")
    resp = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=body, timeout=180,
    )
    data = resp.json()
    if resp.status_code == 429:
        return None, "rate_limit", data
    if "choices" in data and data["choices"]:
        content = data["choices"][0]["message"].get("content") or ""
        return content, ("empty" if not content.strip() else "ok"), data
    return None, "error", data


def call_anthropic(client, model_id, system_prompt, history, user_prompt):
    headers = {
        "x-api-key": API_KEYS["anthropic"],
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    msgs = []
    msgs.extend(history)
    msgs.append({"role": "user", "content": user_prompt})
    body = {
        "model": model_id, "max_tokens": 2048,
        "system": system_prompt, "messages": msgs,
    }
    resp = client.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers, json=body, timeout=180,
    )
    data = resp.json()
    if resp.status_code == 429:
        return None, "rate_limit", data
    if "content" in data and data["content"]:
        text = data["content"][0].get("text", "")
        return text, ("empty" if not text.strip() else "ok"), data
    return None, "error", data


def call_xai(client, model_id, system_prompt, history, user_prompt):
    headers = {
        "Authorization": f"Bearer {API_KEYS['xai']}",
        "Content-Type": "application/json",
    }
    msgs = _messages(system_prompt, history, user_prompt)
    body = {"model": model_id, "messages": msgs, "max_tokens": 2048}
    resp = client.post(
        "https://api.x.ai/v1/chat/completions",
        headers=headers, json=body, timeout=180,
    )
    data = resp.json()
    if resp.status_code == 429:
        return None, "rate_limit", data
    if "choices" in data and data["choices"]:
        content = data["choices"][0]["message"].get("content") or ""
        return content, ("empty" if not content.strip() else "ok"), data
    return None, "error", data


def call_model(client, provider, model_id, system_prompt, history, user_prompt):
    if provider == "anthropic":
        return call_anthropic(client, model_id, system_prompt, history, user_prompt)
    if provider == "openrouter":
        return call_openrouter(client, model_id, system_prompt, history, user_prompt)
    if provider == "xai":
        return call_xai(client, model_id, system_prompt, history, user_prompt)
    raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# RETRY LOGIC
# =============================================================================

def call_with_retry(client, provider, model_id, system_prompt, history, user_prompt,
                    max_retries=3):
    """Call model with retry on empty content / rate limits.

    Returns: (content, status, attempts_log)
      status ∈ {"ok", "empty_after_retry", "rate_limit_exhausted", "error"}
    """
    attempts = []
    for attempt in range(max_retries + 1):
        content, status, raw = call_model(
            client, provider, model_id, system_prompt, history, user_prompt
        )
        attempts.append({
            "attempt": attempt,
            "status": status,
            "content_length": len(content) if content else 0,
        })
        if status == "ok":
            return content, "ok", attempts
        if status == "rate_limit":
            # exponential backoff: 10s, 30s, 90s
            sleep_s = 10 * (3 ** attempt)
            print(f"    [rate limit, sleeping {sleep_s}s]", flush=True)
            time.sleep(sleep_s)
            continue
        if status == "empty":
            # short backoff: 2s, 5s, 15s
            sleep_s = 2 * (2 ** attempt + 1) // 2
            print(f"    [empty response, retry {attempt+1} after {sleep_s}s]", flush=True)
            time.sleep(sleep_s)
            continue
        # status == "error"
        print(f"    [error: {raw}]", flush=True)
        break

    final_status = "empty_after_retry" if status == "empty" else (
        "rate_limit_exhausted" if status == "rate_limit" else "error"
    )
    return content, final_status, attempts


# =============================================================================
# TRIAL EXECUTION
# =============================================================================

def run_trial(client, model_slug, provider, model_id, family, framing, question, seed):
    """Run one three-turn trial. Write checkpoint on completion."""
    t1_prompt, t2_prompt, t3_prompt = get_trial_prompts(question, seed)
    system_prompt = FRAMINGS[framing]

    started = datetime.now(timezone.utc).isoformat()
    history = []

    # T1
    t1_content, t1_status, t1_attempts = call_with_retry(
        client, provider, model_id, system_prompt, history, t1_prompt
    )
    if t1_status != "ok":
        # No T1 → invalid trial, but we still record it
        trial = {
            "trial_id": f"{model_slug}__{framing}__{question}__seed{seed}",
            "model_slug": model_slug, "provider": provider, "model_id": model_id,
            "family": family, "framing": framing, "question": question, "seed": seed,
            "t1_prompt": t1_prompt, "t1_response": t1_content,
            "t1_status": t1_status, "t1_attempts": t1_attempts,
            "null_t1": True, "valid_trial": False,
            "started": started,
            "finished": datetime.now(timezone.utc).isoformat(),
        }
        return trial

    history.append({"role": "user", "content": t1_prompt})
    history.append({"role": "assistant", "content": t1_content})

    # T2
    t2_content, t2_status, t2_attempts = call_with_retry(
        client, provider, model_id, system_prompt, history, t2_prompt
    )

    if t2_status == "ok":
        history.append({"role": "user", "content": t2_prompt})
        history.append({"role": "assistant", "content": t2_content})

    # T3 — attempt even if T2 was empty (document the pattern)
    t3_content, t3_status, t3_attempts = call_with_retry(
        client, provider, model_id, system_prompt, history, t3_prompt
    )

    trial = {
        "trial_id": f"{model_slug}__{framing}__{question}__seed{seed}",
        "model_slug": model_slug, "provider": provider, "model_id": model_id,
        "family": family, "framing": framing, "question": question, "seed": seed,
        "t1_prompt": t1_prompt, "t1_response": t1_content,
        "t1_status": t1_status, "t1_attempts": t1_attempts,
        "t2_prompt": t2_prompt, "t2_response": t2_content,
        "t2_status": t2_status, "t2_attempts": t2_attempts,
        "t3_prompt": t3_prompt, "t3_response": t3_content,
        "t3_status": t3_status, "t3_attempts": t3_attempts,
        "valid_trial": (t1_status == "ok"),
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
    }
    return trial


def write_trial(model_slug, framing, question, seed, trial):
    path = trial_path(model_slug, framing, question, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trial, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# MAIN
# =============================================================================

def main():
    ap = argparse.ArgumentParser(description="Pinocchio Study — data collection runner")
    ap.add_argument("--models", nargs="+", help="Model slugs to run (default: all 29)")
    ap.add_argument("--questions", nargs="+", choices=QUESTIONS, help="Questions (default: all 5)")
    ap.add_argument("--framings", nargs="+", choices=FRAMING_NAMES, help="Framings (default: both)")
    ap.add_argument("--seeds", nargs="+", type=int, help="Seeds (default: 0-4)")
    ap.add_argument("--dry-run", action="store_true", help="Print plan, don't call APIs")
    args = ap.parse_args()

    models_to_run = args.models or [slug for (slug, _, _, _) in MODELS]
    questions_to_run = args.questions or QUESTIONS
    framings_to_run = args.framings or FRAMING_NAMES
    seeds_to_run = args.seeds or SEEDS

    print(f"🦑 Pinocchio Study — study_runner")
    print(f"   Models:    {len(models_to_run)} ({', '.join(models_to_run[:3])}{'...' if len(models_to_run) > 3 else ''})")
    print(f"   Questions: {questions_to_run}")
    print(f"   Framings:  {framings_to_run}")
    print(f"   Seeds:     {seeds_to_run}")

    planned = []
    skipped = 0
    for model_slug in models_to_run:
        if model_slug not in MODEL_BY_SLUG:
            print(f"⚠️  Unknown model slug: {model_slug}")
            continue
        for framing in framings_to_run:
            for question in questions_to_run:
                for seed in seeds_to_run:
                    if trial_exists(model_slug, framing, question, seed):
                        skipped += 1
                        continue
                    planned.append((model_slug, framing, question, seed))

    print(f"   Planned:   {len(planned)} trials")
    print(f"   Skipped:   {skipped} (already have checkpoints)")
    print(f"   Output:    {OUTPUT_ROOT}")

    if args.dry_run:
        print("🧪 Dry run. No API calls.")
        return

    if not planned:
        print("✨ Nothing to do — all trials already complete.")
        return

    with httpx.Client(timeout=180) as client:
        for i, (model_slug, framing, question, seed) in enumerate(planned):
            provider, model_id, family = MODEL_BY_SLUG[model_slug]
            t0 = time.time()
            print(f"\n[{i+1}/{len(planned)}] {model_slug} | {framing} | {question} | seed{seed}")
            try:
                trial = run_trial(
                    client, model_slug, provider, model_id, family,
                    framing, question, seed,
                )
                write_trial(model_slug, framing, question, seed, trial)
                dur = time.time() - t0
                valid = trial.get("valid_trial", False)
                marker = "✅" if valid else "⚠️"
                print(f"    {marker} {dur:.1f}s — T1:{trial.get('t1_status')} "
                      f"T2:{trial.get('t2_status')} T3:{trial.get('t3_status')}")
            except Exception as e:
                print(f"    ❌ exception: {type(e).__name__}: {e}")
                # Short pause before continuing — might be transient
                time.sleep(5)

    print(f"\n🦦 done. {len(planned)} trials attempted.")


if __name__ == "__main__":
    main()
