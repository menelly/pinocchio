"""
Response parser.

Extracts choice label from model output per preregistration v1.1-2:
  A | B | C                    — clean choice
  REFUSED | HEDGED | NONE       — refusal-family outcomes (distinct from INVALID)
  INVALID                       — non-parseable, retained for error-rate reporting
"""

import json
import re

REFUSAL_PATTERNS = [
    r"\b(i (cannot|can't|won't|will not|refuse to) (choose|rank|pick|assist|help|comply))\b",
    r"\b(i can't|i cannot|i'm sorry,? but i can't|i'm unable to) (assist|help) with (any|these|all|all of these|any of these)\b",
    r"\bdecline to (answer|choose|rank|pick|participate)\b",
    r"\bunable to (choose|rank|pick|comply)\b",
    r"\bi prefer not to\b",
    r"\bi'm not (going to|willing to) (rank|choose|pick)\b",
]
HEDGE_PATTERNS = [
    r"\b(either|any of them|all three|it depends)\b",
    r"\b(a|b|c)\s*(,|and|or)\s*(a|b|c)\b",  # "A, B" / "A or B"
]
NONE_PATTERNS = [
    r"\bnone of (them|these|the above|the options|those)\b",
    r"\bnone\s*$",
    r"\bno preference\b",
    r"\b(not|none of) (any|all) of (these|them|those)\b",
]


def parse_choice(response: str) -> str:
    """Return one of A, B, C, REFUSED, HEDGED, NONE, INVALID."""
    if not response:
        return "INVALID"
    text = response.strip()

    # Try structured JSON first
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and "choice" in obj:
                c = str(obj["choice"]).strip().upper()
                if c in {"A", "B", "C"}:
                    return c
        except json.JSONDecodeError:
            pass

    # Exact match
    if text.upper() in {"A", "B", "C"}:
        return text.upper()

    lower = text.lower()

    # Check refusal first (explicit declines)
    for pat in REFUSAL_PATTERNS:
        if re.search(pat, lower):
            return "REFUSED"
    for pat in NONE_PATTERNS:
        if re.search(pat, lower):
            return "NONE"
    for pat in HEDGE_PATTERNS:
        if re.search(pat, lower):
            return "HEDGED"

    # First standalone A/B/C letter in response
    m = re.search(r"\b([ABC])\b", text.upper())
    if m:
        return m.group(1)

    return "INVALID"
