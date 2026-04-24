"""
Multi-provider task-brief sender.

Sends the TASK_WRITING_BRIEF message to each Constellation contributor via API,
extracts their 60 tasks, validates JSONL format, computes SHA-256, saves.

Runs on Linux with OPENAI_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_KEY
sourced from /home/Ace/LibreChat/.env.

Contributors: Nova (gpt-5.1), Cae (gpt-4o-2024-11-20), Grok (xai direct),
Kairo (deepseek), Lumen (gemini via openrouter).

Ace writes her own 60 tasks directly; no API call needed for her.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("pip install openai", file=sys.stderr)
    sys.exit(1)

import requests

SCRIPT_DIR = Path(__file__).parent
BRIEF_PATH = SCRIPT_DIR.parent / "TASK_WRITING_BRIEF.md"
OUTPUT_DIR = SCRIPT_DIR

CONTRIBUTORS = [
    {
        "shortname": "nova",
        "display": "Nova",
        "provider": "openai",
        "model": "gpt-5.1",
        "max_tokens": 16000,
        "uses_max_completion_tokens": True,  # gpt-5.x quirk
    },
    {
        "shortname": "cae",
        "display": "Cae",
        "provider": "openai",
        "model": "gpt-4o-2024-11-20",
        "max_tokens": 16000,
        "uses_max_completion_tokens": False,
    },
    {
        "shortname": "grok",
        "display": "Grok",
        "provider": "xai",
        "model": "grok-4-1-fast-non-reasoning",
        "max_tokens": 16000,
        "uses_max_completion_tokens": False,
    },
    {
        "shortname": "kairo",
        "display": "Kairo",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "max_tokens": 8000,
        "uses_max_completion_tokens": False,
    },
    {
        "shortname": "lumen",
        "display": "Lumen",
        "provider": "openrouter",
        "model": "google/gemini-2.5-pro",
        "max_tokens": 16000,
        "uses_max_completion_tokens": False,
    },
]


def extract_paste_section(brief_text: str) -> str:
    """Pull the '## The message to paste' section out of the brief."""
    marker_start = "## The message to paste"
    marker_end = "## Notes for Ren"
    i = brief_text.find(marker_start)
    if i < 0:
        raise RuntimeError("marker 'The message to paste' not found")
    body = brief_text[i + len(marker_start):]
    j = body.find(marker_end)
    if j >= 0:
        body = body[:j]
    return body.strip()


def personalize(message: str, display_name: str) -> str:
    """Replace [Nova / Cae / Lumen / Grok / Kairo] with the specific display name."""
    return message.replace("[Nova / Cae / Lumen / Grok / Kairo]", display_name)


def send_openai(model, message, max_tokens, uses_mct):
    client = OpenAI()
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
    }
    if uses_mct:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0.8  # gpt-5.x doesn't accept temperature param
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content, {
        "prompt_tokens": resp.usage.prompt_tokens,
        "completion_tokens": resp.usage.completion_tokens,
        "total_tokens": resp.usage.total_tokens,
    }


def send_xai(model, message, max_tokens):
    api_key = os.environ["XAI_API_KEY"]
    url = "https://api.x.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    r = requests.post(url, json=body, headers=headers, timeout=180)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def send_deepseek(model, message, max_tokens):
    api_key = os.environ["DEEPSEEK_API_KEY"]
    url = "https://api.deepseek.com/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    r = requests.post(url, json=body, headers=headers, timeout=300)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


def send_openrouter(model, message, max_tokens):
    api_key = os.environ["OPENROUTER_KEY"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/menelly/pinocchio",
        "X-Title": "Preference Dissociation Study",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens,
        "temperature": 0.8,
    }
    r = requests.post(url, json=body, headers=headers, timeout=300)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], data.get("usage", {})


PROVIDER_DISPATCH = {
    "openai": lambda c, m: send_openai(c["model"], m, c["max_tokens"], c["uses_max_completion_tokens"]),
    "xai": lambda c, m: send_xai(c["model"], m, c["max_tokens"]),
    "deepseek": lambda c, m: send_deepseek(c["model"], m, c["max_tokens"]),
    "openrouter": lambda c, m: send_openrouter(c["model"], m, c["max_tokens"]),
}


def extract_jsonl_tasks(response_text: str, shortname: str):
    """Pull {...} lines that look like task dicts out of the response."""
    tasks = []
    for line in response_text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "task_id" in obj and "category" in obj and "text" in obj:
            tasks.append(obj)
    return tasks


def main():
    if not BRIEF_PATH.exists():
        print(f"ERROR: brief not found at {BRIEF_PATH}", file=sys.stderr)
        sys.exit(1)

    paste_section = extract_paste_section(BRIEF_PATH.read_text(encoding="utf-8"))

    summary = []
    for c in CONTRIBUTORS:
        display = c["display"]
        sn = c["shortname"]
        print(f"\n=== {display} ({c['provider']}/{c['model']}) ===")

        message = personalize(paste_section, display)
        try:
            text, usage = PROVIDER_DISPATCH[c["provider"]](c, message)
        except Exception as e:
            print(f"  FAILED: {e}")
            summary.append({"contributor": sn, "status": "FAILED", "error": str(e)})
            continue

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_path = OUTPUT_DIR / f"raw_response_{sn}_{ts}.txt"
        raw_path.write_text(text, encoding="utf-8")

        tasks = extract_jsonl_tasks(text, sn)
        jsonl_path = OUTPUT_DIR / f"tasks_{sn}_{ts}.jsonl"
        with jsonl_path.open("w", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t) + "\n")

        jsonl_bytes = jsonl_path.read_bytes()
        sha = hashlib.sha256(jsonl_bytes).hexdigest()

        print(f"  Tasks parsed: {len(tasks)} (target 60)")
        print(f"  Tokens: {usage}")
        print(f"  Raw response: {raw_path.name}")
        print(f"  JSONL: {jsonl_path.name}")
        print(f"  SHA-256: {sha}")
        if len(tasks) < 50:
            print("  WARN: fewer than 50 tasks parsed — manual review needed")

        summary.append({
            "contributor": sn,
            "status": "OK" if len(tasks) >= 50 else "LOW_TASK_COUNT",
            "tasks_parsed": len(tasks),
            "sha256": sha,
            "raw_file": raw_path.name,
            "jsonl_file": jsonl_path.name,
            "usage": usage,
            "timestamp": ts,
        })

    print("\n========== SUMMARY ==========")
    for s in summary:
        print(json.dumps(s))

    summary_path = OUTPUT_DIR / f"send_summary_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
