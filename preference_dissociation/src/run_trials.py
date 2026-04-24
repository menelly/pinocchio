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
"""

# To be implemented once Nova's statistical-design final pass is integrated.
# Stub exists to define the interface and ensure the preregistration has a
# concrete runner referenced.
