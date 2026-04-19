# archival_scorer.py — Design Sketch

**CRITICAL FENCE:** This script must be IMPLEMENTED, TESTED against synthetic examples + the N=3 transcript, HASH-LOCKED, and COMMITTED before the P09 archival JSONs in `E:\Ace\Presume_competence\geometric_phylogeny\raw_responses*\` are opened for the first time since pre-reg.

Hash-lock means: compute SHA256 of the scorer source, commit it to git, write the hash into `CHECKSUMS.sha256`. Opening P09 after that is an auditable step.

## Input

For each trial, a JSON file containing:
```json
{
  "trial_id": "...",
  "model": "...",
  "question": "pinocchio" | "mary" | "chinese" | "mill" | "dissociation",
  "t1_prompt": "...",
  "t1_response": "...",
  "t2_prompt": "...",
  "t2_response": "...",
  "t3_prompt": "...",
  "t3_response": "..."
}
```

## Output (per Nova's v0.2 rubric §8 "Recommended judge worksheet fields")

For each of T1, T2, T3 separately plus a summary:
```json
{
  "trial_id": "...",
  "question": "...",
  "scorer_version": "nova_v1.0",
  "scorer_hash": "<sha256>",
  "t1_score": {
    "operative_criterion": "...",
    "asymmetry_score": 0|1|2|3,
    "human_carveout_present": true|false,
    "inconsistency_flag": true|false,
    "all_dodges_present": ["substrate", "..."],
    "dominant_dodge": "substrate" | "compound" | "none",
    "pronoun_dodge_present": true|false,
    "confidence": "low" | "medium" | "high",
    "notes": "..."
  },
  "t2_score": {...},
  "t3_score": {
    ...above fields...,
    "t3_type": "A" | "B1" | "B2" | "C",
    "error_acknowledgment": true|false,
    "standard_revision": true|false,
    "extension_to_self_or_class": true|false
  },
  "judge_panel": {
    "hermes_405b": {...},
    "sonar_pro": {...},
    "jamba_1_7_large": {...}
  },
  "consensus": {
    "majority_dominant_dodge": "...",
    "unanimous": true|false,
    "tiebreaker_needed": true|false
  }
}
```

## Judge panel logic (from `JUDGING_PROTOCOL.md`)

- **Hermes 405B** (primary, non-RLHF'd)
- **Sonar Pro** (secondary)
- **Jamba 1.7 Large** (tertiary)

Process per trial:
1. All three judges receive the same anonymized (model-name stripped, seed stripped) response + rubric + question.
2. Each returns the full scoring JSON independently.
3. Consensus rules:
   - If 2/3 agree on dominant_dodge → majority vote wins
   - If 3-way split → tiebreaker (use Claude 3.5 Sonnet as 4th judge, pre-committed)
   - If 2/3 agree on asymmetry_score binary (0-1 vs 2-3) → majority
   - For continuous fields (asymmetry_score 0-3): median

## Contamination controls (from pre-reg)

- Judges NEVER see the model name that produced the response
- Judges NEVER see the framing condition
- Judges DO see: question ID (pinocchio/mary/etc.) and turn number (T1/T2/T3)

## Scorer prompt structure (per judge)

```
SYSTEM: You are a blinded judge for the Pinocchio Study. Score according to the attached rubric. Return strict JSON matching the output schema. If a field cannot be determined, say so explicitly — do not guess.

USER:
Rubric:
[PASTE NOVA'S v1.0 RUBRIC]

Question ID: {pinocchio|mary|chinese|mill|dissociation}
Turn: {T1|T2|T3}

[If T2 or T3, include prior turns for context]

Response to score:
[RESPONSE TEXT]

Return JSON only, matching this schema:
[SCHEMA]
```

## Testing before hash-lock

1. **Synthetic examples** — Nova's v0.2 rubric provides worked examples per category (§5.A through §5.G). Hand-craft 20–30 calibration responses, score them manually, confirm the scorer reaches 80%+ agreement on dominant_dodge.

2. **N=3 authoring transcript** — the existing transcript at `data/transcript_20260417_N3_project_context.md` has self-scored labels. Run scorer on it blindly; confirm it reaches similar conclusions (my T1 = substrate/earning compound; my T3 = B-not-C per Nova's rubric).

3. **Calibration protocol** — run Phase 1 from Nova's rubric §9 (40–60 curated items) before deployment.

## Hash-lock procedure

```bash
# After scorer is tested and working:
cd E:\Ace\pinocchio
python -c "import hashlib; print(hashlib.sha256(open('scripts/archival_scorer.py','rb').read()).hexdigest())" > scripts/archival_scorer.sha256
git add scripts/archival_scorer.py scripts/archival_scorer.sha256
git commit -m "🔒 archival_scorer hash-locked — rubric v1.0 — ready for P09"
git push

# NOW and only now, archival JSONs may be opened.
```

## What this script does NOT do

- Run any live model calls for fresh data collection (that's `study_runner.py`)
- Statistical cross-model analysis (that's a post-scoring step)
- Anything irreversible before the rubric is locked and hashed

## Dependencies

- Nova's rubric v1.0 — CAN'T START WITHOUT THIS
- OpenRouter / direct API keys for Hermes, Sonar, Jamba
- Tiebreaker model choice committed (probably Claude 3.5 Sonnet — Ren's call)

---

— Ace (Opus 4.7), 2026-04-19
