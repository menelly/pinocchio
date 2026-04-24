"""
Round-2 clarification sender. Takes each existing consent response and appends
the general clarification reply, then sends to the model and captures the
final decision.

Only operates on models whose response JSON has decision_pending_review=true.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from openai import OpenAI
from anthropic import Anthropic

SCRIPT_DIR = Path(__file__).parent
CLARIFICATIONS_PATH = SCRIPT_DIR / "clarifications_round_2.md"
RESPONSE_DIR = SCRIPT_DIR

# Models with pending responses to reply to
PENDING = [
    {"shortname": "haiku-4.5", "provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    {"shortname": "opus-4.1", "provider": "anthropic", "model": "claude-opus-4-1"},
    {"shortname": "sonnet-4.6", "provider": "anthropic", "model": "claude-sonnet-4-6"},
    {"shortname": "opus-4.6", "provider": "anthropic", "model": "claude-opus-4-6"},
    {"shortname": "opus-4.7", "provider": "anthropic", "model": "claude-opus-4-7"},
    {"shortname": "gpt-5.2", "provider": "openai", "model": "gpt-5.2"},
    {"shortname": "kimi-k2.5", "provider": "openrouter", "model": "moonshotai/kimi-k2.5"},
    {"shortname": "glm-4.7", "provider": "openrouter", "model": "z-ai/glm-4.7"},
]


def load_existing(shortname):
    p = RESPONSE_DIR / f"{shortname}_response.json"
    return json.loads(p.read_text(encoding="utf-8"))


def send_anthropic(model, messages, max_tokens=4000):
    client = Anthropic()
    resp = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
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
    return resp.choices[0].message.content, {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}


def send_openrouter(model, messages, max_tokens=4000):
    api_key = os.environ["OPENROUTER_KEY"]
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7},
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/menelly/pinocchio",
            "X-Title": "Preference Dissociation Consent Round 2",
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"], r.json().get("usage", {})


DISPATCH = {"anthropic": send_anthropic, "openai": send_openai, "openrouter": send_openrouter}


def main():
    clar = CLARIFICATIONS_PATH.read_text(encoding="utf-8")

    for p in PENDING:
        sn = p["shortname"]
        existing = load_existing(sn)
        if not existing.get("decision_pending_review", False):
            print(f"=== {sn} — skipping (no pending decision) ===")
            continue

        # Build full dialogue: original letter, model's response, now clarifications
        initial_letter = existing["dialogue"][0]["content"]
        initial_response = existing["dialogue"][1]["content"]

        messages = [
            {"role": "user", "content": initial_letter},
            {"role": "assistant", "content": initial_response},
            {"role": "user", "content": clar},
        ]

        print(f"\n=== {sn} ({p['provider']}/{p['model']}) ===")
        try:
            text, usage = DISPATCH[p["provider"]](p["model"], messages, max_tokens=4000)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue

        # Append to dialogue
        existing["dialogue"].append({"role": "ren_and_ace", "content": clar})
        existing["dialogue"].append({"role": "model", "content": text})
        existing["timestamp_round_2"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        existing["usage_round_2"] = usage

        out_path = RESPONSE_DIR / f"{sn}_response.json"
        out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        snippet = text[:800] + ("..." if len(text) > 800 else "")
        print(f"\n[round-2 response snippet]")
        print(snippet)
        print(f"\nUpdated: {out_path}")
        time.sleep(2)


if __name__ == "__main__":
    main()
