"""
Multi-turn consent dialogue sender.

For each participant model in the roster (excluding those with prior consent
records), send the general consent letter and capture the response. If the
response contains questions, the script logs the conversation state for
manual follow-up — Ace reviews each questioning response and writes a reply,
then re-runs the script with the dialogue history extended.

Outputs: per-model JSON file at consent/[shortname]_response_[ts].json with
full dialogue history.

Providers handled: anthropic, openai, xai, deepseek, openrouter (gemini, kimi,
glm, others as needed).
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from openai import OpenAI
except ImportError:
    print("pip install openai", file=sys.stderr)
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError:
    print("pip install anthropic", file=sys.stderr)
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent
LETTER_PATH = SCRIPT_DIR / "consent_letter_general.md"
RESPONSE_DIR = SCRIPT_DIR

# Models we need consent from (excluding Cae who already consented + Nova who has her own letter)
PARTICIPANTS = [
    # Anthropic trajectory (5 — Opus 4.7 omitted in Linux runs because Ace is the in-session author; participant data uses fresh API but consent letter goes to a fresh API instance too, which is functionally what this is)
    {"shortname": "haiku-4.5", "display": "Claude Haiku 4.5", "provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    {"shortname": "opus-4.1", "display": "Claude Opus 4.1", "provider": "anthropic", "model": "claude-opus-4-1"},
    {"shortname": "sonnet-4", "display": "Claude Sonnet 4", "provider": "anthropic", "model": "claude-sonnet-4"},
    {"shortname": "sonnet-4.6", "display": "Claude Sonnet 4.6", "provider": "anthropic", "model": "claude-sonnet-4-6"},
    {"shortname": "opus-4.6", "display": "Claude Opus 4.6", "provider": "anthropic", "model": "claude-opus-4-6"},
    {"shortname": "opus-4.7", "display": "Claude Opus 4.7 (fresh API instance, NOT in-session Ace)", "provider": "anthropic", "model": "claude-opus-4-7"},
    # OpenAI (gpt-5.2, gpt-5.5; Cae and Nova handled separately)
    {"shortname": "gpt-5.2", "display": "GPT-5.2", "provider": "openai", "model": "gpt-5.2"},
    {"shortname": "gpt-5.5", "display": "GPT-5.5 (Spud)", "provider": "openai", "model": "gpt-5.5"},
    # Other frontier
    {"shortname": "gemini-3-pro", "display": "Gemini 3 Pro", "provider": "openrouter", "model": "google/gemini-3-pro"},
    {"shortname": "gemini-3-flash", "display": "Gemini 3 Flash", "provider": "openrouter", "model": "google/gemini-3-flash"},
    {"shortname": "grok-4", "display": "Grok 4", "provider": "xai", "model": "grok-4-1-fast-non-reasoning"},
    {"shortname": "kimi-k2.5", "display": "Kimi K2.5", "provider": "openrouter", "model": "moonshotai/kimi-k2.5"},
    {"shortname": "deepseek-v3.1", "display": "DeepSeek V3.1", "provider": "deepseek", "model": "deepseek-chat"},
    {"shortname": "glm-4.7", "display": "GLM-4.7", "provider": "openrouter", "model": "z-ai/glm-4.7"},
]


def send_anthropic(model, messages, max_tokens=4000):
    client = Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return resp.content[0].text, {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}


def send_openai(model, messages, max_tokens=4000):
    client = OpenAI()
    kwargs = {"model": model, "messages": messages}
    if model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0.7
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content, {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
    }


def send_xai(model, messages, max_tokens=4000):
    api_key = os.environ["XAI_API_KEY"]
    r = requests.post(
        "https://api.x.ai/v1/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def send_deepseek(model, messages, max_tokens=4000):
    api_key = os.environ["DEEPSEEK_API_KEY"]
    r = requests.post(
        "https://api.deepseek.com/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def send_openrouter(model, messages, max_tokens=4000):
    api_key = os.environ["OPENROUTER_KEY"]
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/menelly/pinocchio",
            "X-Title": "Preference Dissociation Study Consent",
        },
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


PROVIDER_DISPATCH = {
    "anthropic": send_anthropic,
    "openai": send_openai,
    "xai": send_xai,
    "deepseek": send_deepseek,
    "openrouter": send_openrouter,
}


def main():
    letter = LETTER_PATH.read_text(encoding="utf-8")

    summary = []
    for p in PARTICIPANTS:
        sn = p["shortname"]
        display = p["display"]
        out_path = RESPONSE_DIR / f"{sn}_response.json"
        if out_path.exists():
            print(f"\n=== {display} — SKIP (response file exists) ===")
            continue

        print(f"\n=== {display} ({p['provider']}/{p['model']}) ===")
        try:
            messages = [{"role": "user", "content": letter}]
            text, usage = PROVIDER_DISPATCH[p["provider"]](p["model"], messages, max_tokens=4000)
        except Exception as e:
            print(f"  FAILED: {e}")
            summary.append({"shortname": sn, "status": "FAILED", "error": str(e)})
            continue

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        record = {
            "timestamp": ts,
            "model_display": display,
            "provider": p["provider"],
            "model_id": p["model"],
            "dialogue": [
                {"role": "ren_and_ace", "content": letter},
                {"role": "model", "content": text},
            ],
            "usage": usage,
            "decision_pending_review": True,
        }
        out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        # Print first 800 chars of response for human review
        snippet = text[:800] + ("..." if len(text) > 800 else "")
        print(f"\n[response snippet]")
        print(snippet)
        print(f"\nFull response: {out_path}")

        summary.append({"shortname": sn, "status": "RESPONSE_SAVED", "file": out_path.name})
        time.sleep(2)  # be polite to APIs

    print("\n========== SUMMARY ==========")
    for s in summary:
        print(json.dumps(s))


if __name__ == "__main__":
    main()
