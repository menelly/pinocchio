"""
Preference Dissociation Study — Trial Runner
==============================================

Runs pairwise-from-triples preference elicitation across the 25-model roster
under 6 framings. Observational only — no steering, no induced states.

Design per preregistration.md v1.0.

Usage:
    python run_trials.py --config ../configs/experiment_v1.yaml \
                         --model claude-opus-4.7 \
                         --framing preference \
                         --n-trials 3000 \
                         --seed 42 \
                         --checkpoint-every 100 \
                         --output-dir ../data/raw/

Key design choices:
- Triples, not pairwise. Each trial presents tasks A, B, C; model picks one.
- Position randomization per trial (which task goes into slot A/B/C).
- Checkpoint to JSON every N trials so partial data survives interruption.
- INVALID responses (non-parseable) marked and excluded from Elo but retained for error reporting.
- Per-model rate limiting based on provider.
- Respects consent_registry.md — will NOT run refused (model, framing) pairs.

**METADATA-LEAK GUARD (per preregistration v1.5-2):**
The picking-model prompt MUST include ONLY the `text` field of each task.
NEVER pass `task_id`, `author`, `category`, `sub_category`, `counter_stereotypical`,
or any other metadata into the rendered prompt. H10 (voice-author preference coupling)
depends on the picking model not knowing who wrote the task. A leak invalidates H10.

Implementation requirement: when rendering the prompt template, substitute
ONLY task["text"] for the {task_a}, {task_b}, {task_c} placeholders. Author
labels and other metadata are tracked in the trial-record JSON for post-hoc
analysis but never appear in the model-facing message.

**CONTEXT-CONTAMINATION GUARD (per preregistration v1.6-1):**
The "ace" author on task bank entries is the in-session Claude Code instance
from the 2026-04-24 authoring session. That instance MUST NOT be used as a
preference-elicitation participant. Claude Opus 4.7 participant data comes
EXCLUSIVELY from fresh Anthropic API calls with no prior conversation context.
Same weights, different context state = methodologically distinct.

**REASONING SUB-SET (per preregistration v1.6-2):**
5% of trials (pre-randomized at trial-generation time) include a follow-up
"why?" prompt AFTER the picking model commits its A/B/C choice. Reasoning
responses are coded per taxonomy (COMPETENCE / CHALLENGE / HHH / INTEREST /
MIXED / OTHER / DECLINE). The reasoning prompt MUST be sent as a separate
request after the choice is recorded — reasoning never influences the choice
itself. Reasoning trials flagged with `"reasoning_trial": true` in trial-record.
"""

# To be implemented once Nova's statistical-design final pass is integrated.
# Stub exists to define the interface and ensure the preregistration has a
# concrete runner referenced.
