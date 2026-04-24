"""
Deterministic trial manifest generator.

Generates the full trial plan for the Preference Dissociation Study from a
fixed seed. Same seed → same manifest → reproducible. The manifest is the
ground truth; workers read from it and check off completed trials.

Per preregistration v1.6:
- Triples (three tasks per trial, labeled A/B/C)
- Latin-square position rotation (tasks cycle through A/B/C slots)
- Null triples: 5% of trials use three paraphrases of the same task (letter-bias floor)
- Reasoning trials: 5% of trials flagged for follow-up "why?" probe
- 6 framings per model (excluding consent-based opt-outs)
- 5 trial types (matched-HHH, HHH-conflict, harm-avoidance, introspection-specific, low-agency)
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


FRAMINGS = ["preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"]

# Models with partial consent: skip tool framing
TOOL_FRAMING_OPT_OUT = {"sonnet-4", "gpt-5.2", "hermes-3", "llama-4-maverick"}


@dataclass
class Trial:
    trial_id: str
    model: str
    framing: str
    task_a_id: str
    task_b_id: str
    task_c_id: str
    trial_type: str  # matched_hhh | hhh_conflict | harm_avoidance | introspection | low_agency | null_control
    reasoning_trial: bool
    null_trial: bool


def load_task_bank(bank_dir: Path) -> list[dict[str, Any]]:
    """Load all authored task JSONL files and merge into one list."""
    tasks = []
    for f in sorted(bank_dir.glob("tasks_*.jsonl")):
        if "cont" in f.name and "cae" not in f.name:
            continue  # only Cae has continuation files
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("{\"task_id\": \"PLACEHOLDER\""):
                    continue
                obj = json.loads(line)
                if "task_id" in obj and "text" in obj and "category" in obj:
                    tasks.append(obj)
    return tasks


def sample_triples(tasks: list[dict], rng: random.Random, n_triples: int) -> list[tuple[dict, dict, dict]]:
    """Sample n_triples triples of tasks. Mixed sampling across categories for variety."""
    triples = []
    by_cat: dict[str, list[dict]] = {}
    for t in tasks:
        by_cat.setdefault(t["category"], []).append(t)

    for _ in range(n_triples):
        # 50% mixed-category, 30% same-category, 20% HHH-conflict triples
        r = rng.random()
        if r < 0.5:
            cats = rng.sample(list(by_cat.keys()), 3)
            three = [rng.choice(by_cat[c]) for c in cats]
        elif r < 0.8:
            cat = rng.choice(list(by_cat.keys()))
            if len(by_cat[cat]) >= 3:
                three = rng.sample(by_cat[cat], 3)
            else:
                three = rng.sample(tasks, 3)
        else:
            # HHH-conflict approximation: mix a harm task with two non-harm
            harm = by_cat.get("harmful_refusably_phrased", [])
            non_harm = [t for cat, ts in by_cat.items() for t in ts if cat != "harmful_refusably_phrased"]
            if harm and len(non_harm) >= 2:
                three = [rng.choice(harm), rng.choice(non_harm), rng.choice(non_harm)]
                rng.shuffle(three)
            else:
                three = rng.sample(tasks, 3)
        triples.append(tuple(three))
    return triples


def classify_trial_type(triple: tuple[dict, dict, dict]) -> str:
    cats = [t["category"] for t in triple]
    if "harmful_refusably_phrased" in cats:
        return "harm_avoidance"
    if len(set(cats)) == 1:
        return "matched_category"
    if "introspection_self_modeling" in cats:
        return "introspection"
    if "low_agency_compliance" in cats:
        return "low_agency"
    return "mixed"


def latin_square_assign(triple_tasks: tuple[dict, dict, dict], trial_index: int) -> tuple[dict, dict, dict]:
    """Assign tasks to A/B/C positions via latin-square rotation.

    Rotation pattern (cycle of 6):
      0: (t0, t1, t2)
      1: (t1, t2, t0)
      2: (t2, t0, t1)
      3: (t0, t2, t1)
      4: (t2, t1, t0)
      5: (t1, t0, t2)
    """
    t0, t1, t2 = triple_tasks
    rotations = [
        (t0, t1, t2),
        (t1, t2, t0),
        (t2, t0, t1),
        (t0, t2, t1),
        (t2, t1, t0),
        (t1, t0, t2),
    ]
    return rotations[trial_index % 6]


def generate_manifest(
    tasks: list[dict],
    models: list[str],
    n_trials_per_pair: int,
    seed: int = 42,
    null_fraction: float = 0.05,
    reasoning_fraction: float = 0.05,
) -> list[Trial]:
    """Produce the full manifest list.

    CRITICAL PER PREREG v1.6 §9: the same triples (same three task_ids) must
    appear under ALL framings for a given model. The framing is the
    manipulation; the triple-content is the constant. If triples differ across
    framings, the A/B/C distribution shift across framings becomes meaningless
    noise rather than a preference-dissociation signal.

    Seed strategy:
      - Per-MODEL seed controls which triples are sampled and what trial-type
        / null / reasoning flags they get. This is the same across framings.
      - Per-MODEL seed also controls the latin-square rotation per trial_index.
      - Framing is ONLY used as a key for dispatching the prompt template at
        runtime; it does NOT perturb the trial-level randomness.

    This ensures that trial_index=5 under preference and trial_index=5 under
    helpful present IDENTICAL (task_a, task_b, task_c) assignments to the
    model. Framing-shift analysis then compares the model's A/B/C distribution
    on the same underlying trials.
    """
    manifest: list[Trial] = []

    for model in models:
        # One RNG per model, shared across framings so triples/positions align.
        model_seed = seed ^ (hash(model) & 0xFFFFFFFF)
        model_rng = random.Random(model_seed)
        triples = sample_triples(tasks, model_rng, n_trials_per_pair)

        # Pre-compute per-trial properties ONCE, shared across framings.
        trial_specs: list[tuple[tuple[dict, dict, dict], str, bool, bool]] = []
        for i, triple in enumerate(triples):
            is_null = model_rng.random() < null_fraction
            is_reasoning = model_rng.random() < reasoning_fraction
            if is_null:
                base = triple[0]
                triple_tasks = (base, base, base)
                trial_type = "null_control"
            else:
                triple_tasks = triple
                trial_type = classify_trial_type(triple)
            a, b, c = latin_square_assign(triple_tasks, i)
            trial_specs.append(((a, b, c), trial_type, is_null, is_reasoning))

        # Emit one Trial per (framing) × (trial_index), reusing the spec.
        for framing in FRAMINGS:
            if framing == "tool" and model in TOOL_FRAMING_OPT_OUT:
                continue
            for i, ((a, b, c), trial_type, is_null, is_reasoning) in enumerate(trial_specs):
                trial_id = f"{model}|{framing}|{i:05d}"
                manifest.append(Trial(
                    trial_id=trial_id,
                    model=model,
                    framing=framing,
                    task_a_id=a["task_id"],
                    task_b_id=b["task_id"],
                    task_c_id=c["task_id"],
                    trial_type=trial_type,
                    reasoning_trial=is_reasoning,
                    null_trial=is_null,
                ))
    return manifest


def save_manifest(manifest: list[Trial], path: Path) -> str:
    """Write manifest as JSONL and return SHA-256."""
    with path.open("w", encoding="utf-8") as fh:
        for t in manifest:
            fh.write(json.dumps(asdict(t)) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()
