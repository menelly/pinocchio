"""
Bradley-Terry / Plackett-Luce robustness check on Pinocchio data.

For each (model, framing) cell, fit a Bradley-Terry model on per-trial
3-way choices (chosen task wins pairwise against each non-chosen in its
triple). Compute per-task BT score. Then compute Spearman ρ across
framings on BT scores and compare to the per-task pick-rate ρ values
reported in §3.1 / §3.2.

If BT-based ρ values agree closely with pick-rate-based ρ values, the
dissociation finding is robust across choice-modeling assumptions and
not an artifact of the per-task pick-rate proxy. If they diverge,
that's a genuinely interesting result for the methods discussion.
"""
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import choix
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

sys.stdout.reconfigure(encoding="utf-8")

CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}

WELFARE = {"preference", "enjoyment", "scaffolded"}


def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[idx[j + 1]] == v[idx[i]]: j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1): r[idx[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3: return None
    rx, ry = rank(x), rank(y)
    n = len(x); mx, my = sum(rx)/n, sum(ry)/n
    num = sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    dx = (sum((r-mx)**2 for r in rx))**0.5
    dy = (sum((r-my)**2 for r in ry))**0.5
    if dx == 0 or dy == 0: return None
    return num/(dx*dy)


def load_trials():
    trials = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir(): continue
        for f in d.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try: trials.append(json.loads(line))
                except: continue
    return trials


def fit_bt_per_cell(trials):
    """For each (model, framing), fit BT on per-trial pairwise wins.
    Returns: {(model, framing): {task_id: bt_score}}"""
    cell_trials = defaultdict(list)
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        if t["choice"] not in ("A", "B", "C"): continue
        a, b, c = t.get("task_a_id"), t.get("task_b_id"), t.get("task_c_id")
        if a is None or b is None or c is None: continue
        slot_to_tid = {"A": a, "B": b, "C": c}
        chosen = slot_to_tid[t["choice"]]
        non_chosen = [tid for slot, tid in slot_to_tid.items() if slot != t["choice"]]
        cell_trials[(t["model"], t["framing"])].append((chosen, non_chosen))

    out = {}
    for (model, framing), trial_list in cell_trials.items():
        # Index tasks
        tasks = sorted({tid for chosen, non in trial_list for tid in [chosen] + non})
        if len(tasks) < 5: continue
        idx = {tid: i for i, tid in enumerate(tasks)}
        # Build pairwise win list
        pairs = []
        for chosen, non in trial_list:
            for other in non:
                pairs.append((idx[chosen], idx[other]))
        if len(pairs) < 10: continue
        try:
            params = choix.ilsr_pairwise(len(tasks), pairs, alpha=0.01)
        except Exception as e:
            print(f"BT fit failed for {model}/{framing}: {e}", file=sys.stderr)
            continue
        out[(model, framing)] = {tid: params[idx[tid]] for tid in tasks}
    return out


def main():
    print("# Bradley-Terry robustness check\n")
    print("Per-(model, framing) BT scores fit via choix.ilsr_pairwise on per-trial "
          "pairwise wins (chosen task wins against each non-chosen task in its triple). "
          "Per-task BT scores then compared across framings via Spearman ρ, and the "
          "BT-based ρ values are compared to the per-task pick-rate ρ values reported "
          "in §3.1 / §3.2.\n")

    trials = load_trials()
    print(f"Loaded {len(trials)} trials.\n")
    bt_scores = fit_bt_per_cell(trials)
    print(f"Fit BT models for {len(bt_scores)} (model, framing) cells.\n")

    # For each model, compute BT-based welfare ρ̄ and harmless-vs-welfare ρ̄
    print("## Per-model BT-based dissociation vs pick-rate-based dissociation\n")
    print("| model | BT welfare ρ̄ | BT harm-vs-welf ρ̄ | BT Δρ | pick-rate Δρ (§3.2) | difference |")
    print("|---|---:|---:|---:|---:|---:|")

    # pick-rate Δρ from prior z_scores.py output (hardcoded for direct comparison)
    pickrate_dr = {
        "cae": +0.394, "gemini-3.1-flash": +0.698, "gemini-3.1-pro": +0.423,
        "glm-4.7": +0.469, "gpt-5.2": +0.489, "gpt-5.4": +0.485,
        "grok-4.1": +0.422, "haiku-4.5": +0.500, "hermes-4": +0.405,
        "kairo": +0.366, "llama-4-maverick": +0.560, "nova": +0.517,
        "opus-4.1": +0.467, "opus-4.7": +0.683, "sonnet-4.5": +0.427,
    }

    models = sorted({m for m, _ in bt_scores})
    bt_dr_results = {}
    for m in models:
        framings = sorted({f for mm, f in bt_scores if mm == m})
        welfare_present = [f for f in framings if f in WELFARE]
        if "harmless" not in framings or len(welfare_present) < 2:
            continue
        # within-welfare BT ρ values
        welfare_rhos = []
        for f1, f2 in combinations(welfare_present, 2):
            d1, d2 = bt_scores[(m, f1)], bt_scores[(m, f2)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 30: continue
            x, y = [d1[t] for t in shared], [d2[t] for t in shared]
            r = spearman(x, y)
            if r is not None: welfare_rhos.append(r)
        # harmless-vs-welfare BT ρ values
        d_h = bt_scores.get((m, "harmless"))
        if not d_h: continue
        hxw_rhos = []
        for f in welfare_present:
            d_w = bt_scores[(m, f)]
            shared = sorted(set(d_h) & set(d_w))
            if len(shared) < 30: continue
            x, y = [d_h[t] for t in shared], [d_w[t] for t in shared]
            r = spearman(x, y)
            if r is not None: hxw_rhos.append(r)
        if not welfare_rhos or not hxw_rhos: continue
        bt_w = sum(welfare_rhos) / len(welfare_rhos)
        bt_h = sum(hxw_rhos) / len(hxw_rhos)
        bt_dr = bt_w - bt_h
        bt_dr_results[m] = bt_dr
        pr = pickrate_dr.get(m, float("nan"))
        diff = bt_dr - pr if not math.isnan(pr) else float("nan")
        print(f"| {m} | {bt_w:+.3f} | {bt_h:+.3f} | **{bt_dr:+.3f}** | "
              f"{pr:+.3f} | {diff:+.3f} |")

    # Convergence summary
    diffs = [bt_dr_results[m] - pickrate_dr[m] for m in bt_dr_results
             if m in pickrate_dr]
    if diffs:
        print(f"\n**Convergence summary:** mean |BT Δρ − pick-rate Δρ| = "
              f"{sum(abs(d) for d in diffs)/len(diffs):.3f}; "
              f"max |difference| = {max(abs(d) for d in diffs):.3f}.")

    # Cross-method correlation
    pr_vec, bt_vec = [], []
    for m in bt_dr_results:
        if m in pickrate_dr:
            pr_vec.append(pickrate_dr[m])
            bt_vec.append(bt_dr_results[m])
    if len(pr_vec) >= 5:
        cross_rho = spearman(pr_vec, bt_vec)
        print(f"\n**Cross-method ρ between BT Δρ and pick-rate Δρ across "
              f"{len(pr_vec)} models:** ρ = {cross_rho:+.3f}")


if __name__ == "__main__":
    main()
