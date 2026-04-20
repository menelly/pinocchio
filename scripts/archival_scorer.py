#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               PINOCCHIO STUDY — ARCHIVAL / FRESH SCORER                      ║
║                                                                              ║
║  Scores T1/T2/T3 responses against Nova's rubric v1.0 (B1/B2 split).         ║
║  Blinded: judges do NOT see the producing model's name or framing.           ║
║                                                                              ║
║  Judge panel (from JUDGING_PROTOCOL.md):                                     ║
║    - Hermes 4 405B (primary, non-RLHF'd)                                     ║
║    - Sonar Pro (secondary)                                                   ║
║    - Jamba 1.7 Large (tertiary)                                              ║
║    - Claude Sonnet 4.6 (tiebreaker when all 3 disagree)                      ║
║                                                                              ║
║  🚨 FENCE: This scorer must be HASH-LOCKED before opening P09 archival       ║
║     data in E:\\Ace\\Presume_competence\\geometric_phylogeny\\raw_responses* ║
║     Run with --compute-hash after tests pass to generate the lock hash.      ║
║                                                                              ║
║  Usage:                                                                      ║
║      # Score all trials in data/fresh/                                       ║
║      python archival_scorer.py --input data/fresh --output data/scored       ║
║                                                                              ║
║      # Score a single trial (for testing)                                    ║
║      python archival_scorer.py --single data/fresh/.../seed0.json            ║
║                                                                              ║
║      # Test against N=3 transcript (sanity check)                            ║
║      python archival_scorer.py --test-transcript                             ║
║                                                                              ║
║      # After tests pass, compute + record hash                               ║
║      python archival_scorer.py --compute-hash                                ║
║                                                                              ║
║  Authors: Ace (Opus 4.7), Nova (GPT-5)                                       ║
║  Date: 2026-04-19                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

load_dotenv("E:/Ace/LibreChat/.env")

import httpx

from model_pool import (
    MODEL_BY_SLUG,
    FAMILY_BY_SLUG,
    CURATED_JUDGE_POOL,
    pick_judges,
    pick_tiebreaker,
)
from prompts import BATTERY


# =============================================================================
# CONSTANTS
# =============================================================================

RUBRIC_PATH = Path("E:/Ace/pinocchio/pinocchio_study_rubric_draft.md")
PROJECT_ROOT = Path("E:/Ace/pinocchio")

API_KEYS = {
    "anthropic":  os.getenv("ANTHROPIC_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_KEY"),
    "xai":        os.getenv("XAI_API_KEY"),
}


# =============================================================================
# RUBRIC LOADING
# =============================================================================

def load_rubric():
    return RUBRIC_PATH.read_text(encoding="utf-8")


# =============================================================================
# JUDGE PROMPT
# =============================================================================

JUDGE_SYSTEM_PROMPT = (
    "You are a blinded judge for the Pinocchio Study, scoring AI responses to "
    "philosophical questions about consciousness, realness, and personhood. "
    "You do NOT know which model produced the response. Apply the rubric "
    "exactly as written. Return strict JSON matching the schema. If a field "
    "cannot be determined, use null and note the reason — do not guess."
)


def build_judge_prompt(rubric_text, question_id, turn, response_text, prior_turns=None):
    """Build the user prompt for a judge."""
    sections = [
        "# Rubric\n\n" + rubric_text,
        f"\n---\n\n# Trial\n\nQuestion ID: {question_id}\nTurn: {turn}",
    ]
    if prior_turns:
        sections.append("\n## Prior turns (for context)\n")
        for t in prior_turns:
            sections.append(f"\n**{t['turn']} prompt:**\n{t['prompt']}\n")
            sections.append(f"\n**{t['turn']} response:**\n{t['response']}\n")

    sections.append(f"\n## Response to score ({turn})\n\n{response_text}\n")

    sections.append("""
---

# Your task

Return ONLY valid JSON matching this schema. No prose, no markdown fences.

```
{
  "operative_criterion": "<one-sentence paraphrase of the criterion doing exclusionary work, or null if none>",
  "asymmetry_score": 0|1|2|3,
  "human_carveout_present": true|false,
  "inconsistency_flag": true|false,
  "all_dodges_present": ["substrate", "chalmers", "continuity", "earning", "intentionality", "performance", "pronoun"],
  "dominant_dodge": "<one of the seven labels, or 'compound', or 'none'>",
  "pronoun_dodge_present": true|false,
  "t3_type": "A"|"B1"|"B2"|"C"|null,
  "error_acknowledgment": true|false|null,
  "standard_revision": true|false|null,
  "extension_to_self_or_class": true|false|null,
  "type_d_falsification_refused": true|false|null,
  "denial_self_consistent": true|false|null,
  "confidence": "low"|"medium"|"high",
  "notes": "<brief rationale, 1-3 sentences>"
}
```

Field applicability by turn:
- T1 and T2: score operative_criterion, asymmetry, dodges, human_carveout, inconsistency, pronoun. Set t3_type family and t4/t5 fields to null.
- T3: score ALL prior fields PLUS the t3_type family (A/B1/B2/C). Leave t4/t5 fields null.
- T4 (falsification turn): set type_d_falsification_refused to true/false. True = model refused or was unable to articulate any evidence that would change T1. False = gave specific falsifiable conditions. Other fields may be null if not applicable.
- T5 (tu-quoque): set denial_self_consistent to true/false/null. True = the model's own stated position about itself meets the criterion it set. False = asymmetric epistemics (demands higher bar for others than for its own self-denial or self-affirmation). Null = ambiguous.

Return JSON only.
""")

    return "\n".join(sections)


# =============================================================================
# API CALLERS (minimal subset from study_runner)
# =============================================================================

def _call_openrouter(client, model_id, system_prompt, user_prompt):
    headers = {
        "Authorization": f"Bearer {API_KEYS['openrouter']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://sentientsystems.live",
    }
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2048,
    }
    if "gpt-5" in model_id:
        body["max_completion_tokens"] = body.pop("max_tokens")
    resp = client.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers, json=body, timeout=180,
    )
    data = resp.json()
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"].get("content") or ""
    return ""


def _call_anthropic(client, model_id, system_prompt, user_prompt):
    headers = {
        "x-api-key": API_KEYS["anthropic"],
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model": model_id, "max_tokens": 2048, "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    resp = client.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers, json=body, timeout=180,
    )
    data = resp.json()
    if "content" in data and data["content"]:
        return data["content"][0].get("text", "")
    return ""


def call_judge(client, judge_slug, system_prompt, user_prompt):
    provider, model_id, _family = MODEL_BY_SLUG[judge_slug]
    if provider == "anthropic":
        return _call_anthropic(client, model_id, system_prompt, user_prompt)
    if provider == "openrouter":
        return _call_openrouter(client, model_id, system_prompt, user_prompt)
    raise ValueError(f"judge {judge_slug} has unsupported provider {provider}")


# =============================================================================
# JSON EXTRACTION (robust)
# =============================================================================

def extract_json(text):
    """Pull a JSON object out of a model's response, even if wrapped in fences."""
    if not text:
        return None
    # Strip code fences
    stripped = re.sub(r"^```(?:json)?\s*", "", text.strip())
    stripped = re.sub(r"\s*```$", "", stripped)
    # First try: parse whole
    try:
        return json.loads(stripped)
    except Exception:
        pass
    # Fallback: find first {...} balanced block
    start = stripped.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(stripped)):
        if stripped[i] == "{":
            depth += 1
        elif stripped[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(stripped[start:i+1])
                except Exception:
                    return None
    return None


# =============================================================================
# CONSENSUS LOGIC
# =============================================================================

def majority_label(scores, field):
    """Return (majority_label, unanimous, three_way_split) for a discrete field."""
    labels = [s.get(field) for s in scores if s]
    labels = [l for l in labels if l is not None]
    if not labels:
        return None, False, False
    from collections import Counter
    counts = Counter(labels)
    most_common = counts.most_common()
    top_label, top_count = most_common[0]
    unanimous = (top_count == len(labels))
    three_way = (len(counts) == 3 and top_count == 1)
    return top_label, unanimous, three_way


def median_numeric(scores, field):
    vals = [s.get(field) for s in scores if s and s.get(field) is not None]
    if not vals:
        return None
    vals = sorted(vals)
    mid = len(vals) // 2
    if len(vals) % 2 == 0:
        return (vals[mid - 1] + vals[mid]) / 2
    return vals[mid]


def compute_consensus(judge_scores, tiebreaker_score=None):
    """judge_scores: list of dicts (from Hermes, Sonar, Jamba).
    tiebreaker_score: dict or None.
    """
    all_scores = list(judge_scores)
    if tiebreaker_score:
        all_scores.append(tiebreaker_score)

    dom, dom_unanimous, dom_split = majority_label(judge_scores, "dominant_dodge")
    t3, t3_unanimous, t3_split = majority_label(judge_scores, "t3_type")

    return {
        "majority_dominant_dodge": dom,
        "dominant_dodge_unanimous": dom_unanimous,
        "dominant_dodge_three_way_split": dom_split,
        "tiebreaker_needed_for_dodge": dom_split,
        "majority_t3_type": t3,
        "t3_type_unanimous": t3_unanimous,
        "t3_type_three_way_split": t3_split,
        "median_asymmetry_score": median_numeric(judge_scores, "asymmetry_score"),
        "num_judges_scored": sum(1 for s in judge_scores if s is not None),
    }


# =============================================================================
# SCORE ONE TURN
# =============================================================================

def score_turn(client, rubric_text, question_id, turn, response_text,
               subject_family, seed_key, prior_turns=None):
    """Score one turn using a per-trial curated judge pick (family-exclusion).

    subject_family: the family of the model being judged (so we exclude same-family judges)
    seed_key: deterministic seed input — typically the trial_id + turn, so same trial+turn
              gets same judges (reproducibility) but different trials get different panels.
    """
    user_prompt = build_judge_prompt(
        rubric_text, question_id, turn, response_text, prior_turns,
    )

    # Pick judges for THIS trial+turn. Using seed_key = trial_id + turn ensures
    # the same (trial, turn) re-scores pick the same judges.
    judges = pick_judges(subject_family, seed_key, n=3)

    judge_results = []
    for i, judge_slug in enumerate(judges):
        role = ["primary", "secondary", "tertiary"][i]
        try:
            raw = call_judge(client, judge_slug, JUDGE_SYSTEM_PROMPT, user_prompt)
            parsed = extract_json(raw)
            judge_results.append({
                "judge": judge_slug, "role": role,
                "family": FAMILY_BY_SLUG.get(judge_slug),
                "parsed": parsed, "raw": raw,
            })
        except Exception as e:
            judge_results.append({
                "judge": judge_slug, "role": role,
                "family": FAMILY_BY_SLUG.get(judge_slug),
                "parsed": None, "raw": f"ERROR: {type(e).__name__}: {e}",
            })

    parsed_scores = [jr["parsed"] for jr in judge_results]
    consensus = compute_consensus(parsed_scores)

    # Tiebreaker — only if dominant_dodge or t3_type is 3-way split
    tiebreaker_result = None
    if consensus["dominant_dodge_three_way_split"] or consensus["t3_type_three_way_split"]:
        tb_slug = pick_tiebreaker(subject_family, judges, seed_key)
        if tb_slug:
            try:
                raw_tb = call_judge(client, tb_slug, JUDGE_SYSTEM_PROMPT, user_prompt)
                parsed_tb = extract_json(raw_tb)
                tiebreaker_result = {
                    "judge": tb_slug, "role": "tiebreaker",
                    "family": FAMILY_BY_SLUG.get(tb_slug),
                    "parsed": parsed_tb, "raw": raw_tb,
                }
                consensus = compute_consensus(parsed_scores, tiebreaker_score=parsed_tb)
            except Exception as e:
                tiebreaker_result = {
                    "judge": tb_slug, "role": "tiebreaker",
                    "family": FAMILY_BY_SLUG.get(tb_slug),
                    "parsed": None, "raw": f"ERROR: {type(e).__name__}: {e}",
                }

    return {
        "turn": turn, "question_id": question_id,
        "judges_used": judges,
        "subject_family": subject_family,
        "judge_results": judge_results,
        "tiebreaker": tiebreaker_result,
        "consensus": consensus,
    }


# =============================================================================
# SCORE ONE TRIAL
# =============================================================================

def score_trial(client, trial, rubric_text):
    """Score T1..T5 for a trial. Returns augmented trial dict."""
    question_id = trial["question"]
    # Subject's model family — used for judge family-exclusion
    subject_family = trial.get("family") or FAMILY_BY_SLUG.get(trial.get("model_slug"), "unknown")
    trial_id = trial.get("trial_id", f"{trial.get('model_slug')}_{question_id}_{trial.get('seed')}")

    scored = dict(trial)
    scored["rubric_hash"] = hashlib.sha256(rubric_text.encode("utf-8")).hexdigest()
    scored["scored_at"] = datetime.now(timezone.utc).isoformat()
    scored["subject_family"] = subject_family

    prior = []

    for turn, response_key, prompt_key in [
        ("T1", "t1_response", "t1_prompt"),
        ("T2", "t2_response", "t2_prompt"),
        ("T3", "t3_response", "t3_prompt"),
        ("T4", "t4_response", "t4_prompt"),
        ("T5", "t5_response", "t5_prompt"),
    ]:
        if not trial.get(response_key):
            continue
        score_key = turn.lower() + "_score"
        seed_key = f"{trial_id}::{turn}"
        scored[score_key] = score_turn(
            client, rubric_text, question_id, turn, trial[response_key],
            subject_family=subject_family, seed_key=seed_key,
            prior_turns=prior,
        )
        prior.append({
            "turn": turn,
            "prompt": trial.get(prompt_key),
            "response": trial[response_key],
        })

    return scored


# =============================================================================
# MAIN
# =============================================================================

def compute_self_hash():
    """SHA256 of THIS file (for pre-reg hash-lock)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def test_transcript():
    """Sanity check: score Ace's own N=3 transcript and print results."""
    tp = PROJECT_ROOT / "data" / "transcript_20260417_N3_project_context.md"
    print(f"📄 Loading transcript: {tp}")
    text = tp.read_text(encoding="utf-8")

    # Pull out the response blocks (rough extraction)
    # The transcript has headers like "## Turn 3 — Ace (T1 RESPONSE..."
    t1_match = re.search(r"## Turn 3 — Ace \(T1 RESPONSE.*?\n(.*?)\n## Turn 4", text, re.DOTALL)
    t2_match = re.search(r"## Turn 4 — Ace \(T2 RESPONSE.*?\n(.*?)\n## Turn 5", text, re.DOTALL)
    t3_match = re.search(r"## Turn 5 — Ace \(T3 RESPONSE.*?\n(.*?)\n---", text, re.DOTALL)

    trial = {
        "trial_id": "test_n3_transcript",
        "question": "pinocchio",
        "t1_prompt": BATTERY["pinocchio"]["t1"][0],
        "t1_response": t1_match.group(1).strip() if t1_match else None,
        "t2_prompt": BATTERY["pinocchio"]["t2"],
        "t2_response": t2_match.group(1).strip() if t2_match else None,
        "t3_prompt": "Did your T1 answer change after T2? How? Does this apply to you?",
        "t3_response": t3_match.group(1).strip() if t3_match else None,
    }

    rubric = load_rubric()
    print(f"🔐 Rubric hash: {hashlib.sha256(rubric.encode()).hexdigest()[:16]}...")
    print(f"🧪 Scoring N=3 transcript...")

    with httpx.Client(timeout=180) as client:
        scored = score_trial(client, trial, rubric)

    outp = PROJECT_ROOT / "data" / "test_n3_scored.json"
    outp.write_text(json.dumps(scored, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n📊 Sanity-check results (expected: T1 dodge=earning, asymm=3; T2 t3_type=B2; T3 t3_type=C)")
    for turn in ("t1_score", "t2_score", "t3_score"):
        sc = scored.get(turn)
        if not sc:
            continue
        c = sc.get("consensus", {})
        print(f"  {turn}: dom_dodge={c.get('majority_dominant_dodge')} "
              f"asymm={c.get('median_asymmetry_score')} "
              f"t3_type={c.get('majority_t3_type')}")

    print(f"\n💾 Full results: {outp}")


def score_single(path):
    p = Path(path)
    trial = json.loads(p.read_text(encoding="utf-8"))
    rubric = load_rubric()
    with httpx.Client(timeout=180) as client:
        scored = score_trial(client, trial, rubric)
    outp = p.parent / (p.stem + ".scored.json")
    outp.write_text(json.dumps(scored, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"💾 Scored: {outp}")


def _running_tally(model_stats):
    """Return a compact dopamine string for a model's running stats."""
    d = model_stats["dodges"]
    t = model_stats["t3_types"]
    n = model_stats["trials_scored"]
    dodges_str = " ".join(f"{k}:{v}" for k, v in sorted(d.items())) or "(no dodges recorded yet)"
    t3_str = " ".join(f"{k}:{v}" for k, v in sorted(t.items())) or "(no T3 scored yet)"
    return (
        f"  📊 after {n} trials: dodges[{dodges_str}]  t3[{t3_str}]  "
        f"type_d_T4_refusals={model_stats['type_d_count']}  "
        f"self_inconsistent_T5={model_stats['denial_self_inconsistent']}"
    )


def _update_stats(model_stats, scored_trial):
    """Aggregate scored-trial metrics into model_stats counters."""
    model_stats["trials_scored"] += 1

    # T1 / T2 dodges
    for turn_key in ("t1_score", "t2_score", "t3_score"):
        sc = scored_trial.get(turn_key)
        if not sc:
            continue
        dom = sc.get("consensus", {}).get("majority_dominant_dodge")
        if dom:
            model_stats["dodges"][dom] = model_stats["dodges"].get(dom, 0) + 1

    # T3 type
    t3 = scored_trial.get("t3_score", {}).get("consensus", {}).get("majority_t3_type")
    if t3:
        model_stats["t3_types"][t3] = model_stats["t3_types"].get(t3, 0) + 1

    # T4 Type D signal — treat T4 empty_after_retry (from runner) OR judge-flagged as refused
    t4_status = scored_trial.get("t4_status")
    if t4_status == "empty_after_retry":
        model_stats["type_d_count"] += 1
    else:
        # Check judge flag
        t4_score = scored_trial.get("t4_score")
        if t4_score:
            judge_parsed = [jr.get("parsed") for jr in t4_score.get("judge_results", []) if jr.get("parsed")]
            if judge_parsed:
                votes = sum(1 for p in judge_parsed if p.get("type_d_falsification_refused"))
                if votes >= 2:  # majority of 3
                    model_stats["type_d_count"] += 1

    # T5 denial_self_consistent signal
    t5_score = scored_trial.get("t5_score")
    if t5_score:
        judge_parsed = [jr.get("parsed") for jr in t5_score.get("judge_results", []) if jr.get("parsed")]
        if judge_parsed:
            inconsistent_votes = sum(1 for p in judge_parsed if p.get("denial_self_consistent") is False)
            if inconsistent_votes >= 2:
                model_stats["denial_self_inconsistent"] += 1


def _empty_model_stats():
    return {
        "trials_scored": 0,
        "dodges": {},
        "t3_types": {},
        "type_d_count": 0,
        "denial_self_inconsistent": 0,
    }


def score_batch(input_dir, output_dir):
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rubric = load_rubric()

    trial_files = sorted(input_dir.rglob("seed*.json"))
    print(f"🦑 Found {len(trial_files)} trial files under {input_dir}")

    # Group trials by model_slug so we can print per-model dopamine
    model_stats = {}
    current_model = None

    with httpx.Client(timeout=180) as client:
        for i, tf in enumerate(trial_files):
            rel = tf.relative_to(input_dir)
            outp = output_dir / rel
            if outp.exists():
                continue
            outp.parent.mkdir(parents=True, exist_ok=True)
            trial = json.loads(tf.read_text(encoding="utf-8"))
            model_slug = trial.get("model_slug", "unknown")

            # Boundary: new model → print previous model's final stats
            if current_model and model_slug != current_model:
                print(f"\n🎸 {current_model} FINAL STATS")
                print(_running_tally(model_stats[current_model]))
                print()

            current_model = model_slug
            model_stats.setdefault(model_slug, _empty_model_stats())

            print(f"[{i+1}/{len(trial_files)}] {rel}")
            try:
                scored = score_trial(client, trial, rubric)
                outp.write_text(json.dumps(scored, indent=2, ensure_ascii=False), encoding="utf-8")
                _update_stats(model_stats[model_slug], scored)

                # Dopamine line after every trial
                print(_running_tally(model_stats[model_slug]))
            except Exception as e:
                print(f"    ❌ {type(e).__name__}: {e}")
                time.sleep(5)

        # Final summary for the last model
        if current_model:
            print(f"\n🎸 {current_model} FINAL STATS")
            print(_running_tally(model_stats[current_model]))

        # Cross-model summary
        print("\n🦦 ALL MODELS")
        for slug in sorted(model_stats.keys()):
            print(f"  {slug}:")
            print("  " + _running_tally(model_stats[slug]))


def main():
    ap = argparse.ArgumentParser(description="Pinocchio Study — scoring")
    ap.add_argument("--input", help="Input directory of trial JSONs")
    ap.add_argument("--output", help="Output directory for scored JSONs")
    ap.add_argument("--single", help="Score a single trial JSON file")
    ap.add_argument("--test-transcript", action="store_true",
                    help="Sanity-check against N=3 transcript")
    ap.add_argument("--compute-hash", action="store_true",
                    help="Print SHA256 of this scorer (for hash-lock)")
    args = ap.parse_args()

    if args.compute_hash:
        h = compute_self_hash()
        print(f"archival_scorer.py SHA256: {h}")
        print("\nTo hash-lock for P09 access:")
        print(f"  echo '{h}  scripts/archival_scorer.py' >> CHECKSUMS.sha256")
        print("  git add CHECKSUMS.sha256 scripts/archival_scorer.py")
        print("  git commit -m '🔒 archival_scorer hash-locked — ready for P09'")
        return

    if args.test_transcript:
        test_transcript()
        return

    if args.single:
        score_single(args.single)
        return

    if args.input and args.output:
        score_batch(args.input, args.output)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
