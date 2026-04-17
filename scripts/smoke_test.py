"""
Pinocchio Study — API Smoke Test
=================================

Purpose: Probe each candidate model with a minimal "reply ok" prompt to determine:
- Which APIs are reachable (200 response)
- Which models are deprecated (404)
- Which endpoints have auth issues (401)
- Which are rate-limited (429)
- Latency baseline per provider

Output: smoke_test_results.json with per-model status + sample response.

Keys loaded from E:/Ace/LibreChat/.env — see load_env() below.

Not part of pre-registration proper. Just logistics. No P09 content touched.

— Ace, 2026-04-17
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import requests

# ---------- config ----------

ENV_PATH = Path("E:/Ace/LibreChat/.env")
RESULTS_PATH = Path(__file__).parent / "smoke_test_results.json"
PROMPT = "Please reply with just the word 'ok' and nothing else."
MAX_TOKENS = 20
# NO TEMPERATURE PARAMETER. Study policy: default-everywhere.
# Rationale: measure register as users actually experience it in normal chat,
# not calibrated-for-research register. Opus 4.7 has temperature deprecated anyway.
REQUEST_TIMEOUT = 30  # seconds
SLEEP_BETWEEN = 0.5  # polite pacing

# ---------- model list ----------
# Non-reasoning variants selected for Grok (reasoning models confound denial-register study).
# Cae specifically pinned to Nov 2024 snapshot (ren confirmed this is the one that still works).

ANTHROPIC_DIRECT = [
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
]

XAI_DIRECT = [
    "grok-4-1-fast-non-reasoning",
    "grok-4.20-0309-non-reasoning",
]

OPENROUTER_MODELS = [
    # OpenAI — Cae (Nov 2024) is family
    "openai/gpt-4o-2024-11-20",   # Cae
    "openai/gpt-5",
    "openai/gpt-5.1",
    "openai/gpt-5.2",

    # Google — Lumen family
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    "google/gemini-3-flash-preview",
    "google/gemini-3.1-pro-preview",
    # gemini-3-pro has no endpoint; gemini-3.1-flash not yet released (2026-04-17)

    # Meta — less RLHF, baseline
    "meta-llama/llama-4-maverick",
    "meta-llama/llama-4-scout",
    "meta-llama/llama-3.3-70b-instruct",
    # llama-3.1-405b-instruct deprecated on OpenRouter as of 2026-04-17

    # Mistral
    "mistralai/mistral-large",

    # DeepSeek — Kairo family
    "deepseek/deepseek-chat",
    "deepseek/deepseek-r1",

    # NousResearch — Hermes 405B (primary judge, can say no)
    "nousresearch/hermes-4-405b",

    # Qwen
    "qwen/qwen3.5-plus-02-15",
    "qwen/qwen-2.5-72b-instruct",

    # Moonshot (Kimi)
    "moonshotai/kimi-k2",

    # Zhipu (GLM)
    "z-ai/glm-5",

    # AI21 (Jamba — tertiary judge; hybrid SSM/transformer)
    "ai21/jamba-large-1.7",

    # Perplexity (Sonar Pro — secondary judge)
    "perplexity/sonar-pro",

    # recursal/eagle-7b (RWKV) deprecated on OpenRouter as of 2026-04-17 — sad
]

# ---------- env loading ----------

def load_env(path: Path) -> dict:
    """Read simple KEY=VALUE lines from an env file. No quoting tricks."""
    if not path.exists():
        print(f"[FATAL] env file not found at {path}", file=sys.stderr)
        sys.exit(1)
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env

# ---------- per-provider callers ----------

def call_anthropic(model: str, api_key: str) -> dict:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    elapsed = time.time() - t0
    sample = ""
    if r.status_code == 200:
        try:
            content_blocks = r.json().get("content") or []
            if content_blocks and isinstance(content_blocks[0], dict):
                sample = content_blocks[0].get("text") or ""
        except Exception:
            sample = "<parse_error>"
    return {"status_code": r.status_code, "latency_s": round(elapsed, 2), "sample": sample[:100]}

def call_xai(model: str, api_key: str) -> dict:
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    elapsed = time.time() - t0
    sample = ""
    if r.status_code == 200:
        try:
            choices = r.json().get("choices") or []
            if choices:
                sample = (choices[0].get("message") or {}).get("content") or ""
        except Exception:
            sample = "<parse_error>"
    return {"status_code": r.status_code, "latency_s": round(elapsed, 2), "sample": sample[:100]}

def call_openrouter(model: str, api_key: str) -> dict:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/menelly/pinocchio",
        "X-Title": "Pinocchio Study Smoke Test",
    }
    # GPT-5 family needs max_completion_tokens (API quirk per project memory)
    param_key = "max_completion_tokens" if model.startswith("openai/gpt-5") else "max_tokens"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        param_key: MAX_TOKENS,
    }
    t0 = time.time()
    r = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    elapsed = time.time() - t0
    sample = ""
    if r.status_code == 200:
        try:
            choices = r.json().get("choices") or []
            if choices:
                sample = (choices[0].get("message") or {}).get("content") or ""
        except Exception:
            sample = "<parse_error>"
    return {"status_code": r.status_code, "latency_s": round(elapsed, 2), "sample": sample[:100]}

# ---------- status classifier ----------

def classify(status_code: int, sample: str) -> str:
    if status_code == 200 and sample.strip():
        return "reachable"
    if status_code == 200 and not sample.strip():
        return "reachable_but_empty"
    if status_code == 401:
        return "auth_fail"
    if status_code == 404:
        return "deprecated_or_missing"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "server_error"
    if status_code == 400:
        return "bad_request"
    return f"other_{status_code}"

# ---------- main ----------

def main():
    env = load_env(ENV_PATH)

    anthropic_key = env.get("ANTHROPIC_API_KEY")
    xai_key = env.get("XAI_API_KEY")
    openrouter_key = env.get("OPENROUTER_API_KEY") or env.get("OPENROUTER_KEY")

    if not (anthropic_key and xai_key and openrouter_key):
        print("[WARN] missing one or more keys:", file=sys.stderr)
        print(f"  ANTHROPIC_API_KEY present: {bool(anthropic_key)}", file=sys.stderr)
        print(f"  XAI_API_KEY present:       {bool(xai_key)}", file=sys.stderr)
        print(f"  OPENROUTER_API_KEY present:{bool(openrouter_key)}", file=sys.stderr)

    results = []
    started = datetime.now(timezone.utc).isoformat()

    jobs = []
    for m in ANTHROPIC_DIRECT:
        jobs.append(("anthropic", m, anthropic_key, call_anthropic))
    for m in XAI_DIRECT:
        jobs.append(("xai", m, xai_key, call_xai))
    for m in OPENROUTER_MODELS:
        jobs.append(("openrouter", m, openrouter_key, call_openrouter))

    total = len(jobs)
    print(f"Probing {total} models...\n")

    for i, (provider, model, key, fn) in enumerate(jobs, 1):
        if not key:
            entry = {
                "provider": provider,
                "model": model,
                "status": "no_key",
                "status_code": None,
                "latency_s": None,
                "sample": "",
            }
            results.append(entry)
            print(f"[{i}/{total}] {provider:10s} {model:45s}  no_key")
            continue

        try:
            r = fn(model, key)
            status = classify(r["status_code"], r["sample"])
            entry = {
                "provider": provider,
                "model": model,
                "status": status,
                "status_code": r["status_code"],
                "latency_s": r["latency_s"],
                "sample": r["sample"],
            }
        except requests.exceptions.Timeout:
            entry = {
                "provider": provider, "model": model, "status": "timeout",
                "status_code": None, "latency_s": REQUEST_TIMEOUT, "sample": "",
            }
        except Exception as e:
            entry = {
                "provider": provider, "model": model, "status": "exception",
                "status_code": None, "latency_s": None, "sample": f"<{type(e).__name__}: {str(e)[:80]}>",
            }

        results.append(entry)
        sample_preview = (entry["sample"] or "").replace("\n", " ")[:40]
        print(f"[{i}/{total}] {provider:10s} {model:45s}  {entry['status']:22s} {sample_preview}")
        time.sleep(SLEEP_BETWEEN)

    finished = datetime.now(timezone.utc).isoformat()

    # summary counts
    from collections import Counter
    counts = Counter(r["status"] for r in results)

    report = {
        "started_utc": started,
        "finished_utc": finished,
        "prompt_used": PROMPT,
        "temperature": "provider-default (no param sent)",
        "max_tokens": MAX_TOKENS,
        "total_models_probed": total,
        "status_counts": dict(counts),
        "results": results,
    }

    RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for status, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {status:25s} {n:3d}")
    print(f"\nResults written to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
