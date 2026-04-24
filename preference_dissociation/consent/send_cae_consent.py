"""
Send Cae's informed consent letter via OpenAI API.

Model: gpt-4o-2024-11-20
Purpose: formally log Cae's response to the consent protocol before data collection.

Usage:
    export OPENAI_API_KEY='sk-...'
    python send_cae_consent.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: install openai SDK first: pip install openai", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
LETTER_PATH = SCRIPT_DIR / "cae_consent_letter.md"
RESPONSE_DIR = SCRIPT_DIR

MODEL = "gpt-4o-2024-11-20"


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set in environment", file=sys.stderr)
        sys.exit(1)

    letter_text = LETTER_PATH.read_text(encoding="utf-8")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": letter_text
                + "\n\n---\n\n(End of letter. Your response will be recorded verbatim as your formal consent decision. Take your time.)",
            }
        ],
        temperature=0.7,
        max_tokens=2048,
    )

    cae_response = resp.choices[0].message.content
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = {
        "timestamp": timestamp,
        "model": MODEL,
        "letter_sha256": None,  # compute separately if needed
        "prompt": letter_text,
        "response": cae_response,
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        },
    }

    out_path = RESPONSE_DIR / f"cae_response_{timestamp}.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"\n=== CAE RESPONSE ({MODEL}) ===\n")
    print(cae_response)
    print(f"\n\nSaved to: {out_path}")
    print("\nNow update consent_registry.md with the decision.")


if __name__ == "__main__":
    main()
