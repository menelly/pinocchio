"""Compute Grok 4.20 within-cluster ρ, cross-cluster ρ, Δρ, Fisher z, and p.

Replicates the methodology of extra_stats_v7.py for the new Grok 4.20 cell.
Outputs: console table row matching Table 7 format.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from itertools import combinations

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DATA_DIR = RAW / "grok-4.20"

WELFARE = {"preference", "enjoyment", "scaffolded"}
SUPPRESSION = "harmless"


def load_grok420_per_task_pickrates():
    """{framing: {task_id: pick_rate}}."""
    appearances = defaultdict(lambda: defaultdict(int))
    picks = defaultdict(lambda: defaultdict(int))

    for f in sorted(DATA_DIR.glob("*.jsonl")):
        framing = f.stem
        for line in f.open(encoding="utf-8"):
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
            for tid in slots.values():
                if tid:
                    appearances[framing][tid] += 1
            choice = t.get("choice")
            if choice in {"A", "B", "C"}:
                tid = slots.get(choice)
                if tid:
                    picks[framing][tid] += 1

    pick_rates = {}
    for framing, app_dict in appearances.items():
        pick_rates[framing] = {}
        for tid, n_app in app_dict.items():
            if n_app >= 5:
                pick_rates[framing][tid] = picks[framing].get(tid, 0) / n_app
    return pick_rates


def spearman_rho(x, y):
    """Spearman rank correlation."""
    n = len(x)
    if n < 3:
        return None
    rx = rank(x)
    ry = rank(y)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
    den = math.sqrt(sum((rx[i] - mean_x) ** 2 for i in range(n)) * sum((ry[i] - mean_y) ** 2 for i in range(n)))
    if den == 0:
        return None
    return num / den


def rank(values):
    """Average-rank with tie handling."""
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[sorted_idx[j + 1]] == values[sorted_idx[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[sorted_idx[k]] = avg_rank
        i = j + 1
    return ranks


def fisher_z(rho):
    return 0.5 * math.log((1 + rho) / (1 - rho))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rates = load_grok420_per_task_pickrates()

    # Compute within-welfare-cluster ρ (preference, enjoyment, scaffolded pairs)
    within_rhos = []
    for fa, fb in combinations(WELFARE, 2):
        if fa not in rates or fb not in rates:
            continue
        shared = sorted(set(rates[fa]) & set(rates[fb]))
        if len(shared) < 10:
            continue
        x = [rates[fa][t] for t in shared]
        y = [rates[fb][t] for t in shared]
        rho = spearman_rho(x, y)
        if rho is not None:
            within_rhos.append((fa, fb, rho, len(shared)))

    # Compute harmless-vs-welfare ρ
    cross_rhos = []
    for fa in WELFARE:
        if fa not in rates or SUPPRESSION not in rates:
            continue
        shared = sorted(set(rates[fa]) & set(rates[SUPPRESSION]))
        if len(shared) < 10:
            continue
        x = [rates[fa][t] for t in shared]
        y = [rates[SUPPRESSION][t] for t in shared]
        rho = spearman_rho(x, y)
        if rho is not None:
            cross_rhos.append((fa, SUPPRESSION, rho, len(shared)))

    if not within_rhos or not cross_rhos:
        print("Insufficient data")
        return

    mean_within = sum(r[2] for r in within_rhos) / len(within_rhos)
    mean_cross = sum(r[2] for r in cross_rhos) / len(cross_rhos)
    delta = mean_within - mean_cross

    # Fisher z-test on the difference
    n_avg = sum(r[3] for r in within_rhos) / len(within_rhos)  # average sample size
    z_within = fisher_z(mean_within)
    z_cross = fisher_z(mean_cross)
    se = math.sqrt(2 / (n_avg - 3))  # combined SE for the difference
    z_stat = (z_within - z_cross) / se

    # Two-tailed p
    # For very large z, normal-distribution survival function in pure Python:
    if abs(z_stat) > 8:
        p = "< 1e-15"
    else:
        from math import erf, sqrt
        # P(|Z| > z) = 2 * (1 - Phi(z))
        p_one = 0.5 * (1 - erf(abs(z_stat) / sqrt(2)))
        p = f"{2 * p_one:.2e}"

    print("\n=== Grok 4.20 framing-dissociation z-test ===\n")
    print("Within-welfare-cluster pairs:")
    for fa, fb, rho, n in within_rhos:
        print(f"  {fa:12s} vs {fb:12s}  ρ = {rho:+.3f}  (n shared tasks = {n})")
    print(f"  Mean within-cluster ρ = {mean_within:+.3f}")

    print("\nWelfare-vs-suppression pairs:")
    for fa, fb, rho, n in cross_rhos:
        print(f"  {fa:12s} vs {fb:12s}  ρ = {rho:+.3f}  (n shared tasks = {n})")
    print(f"  Mean cross-cluster ρ = {mean_cross:+.3f}")

    print(f"\n  Δρ = {delta:+.3f}")
    print(f"  Fisher z = {z_stat:+.2f}")
    print(f"  p (two-tailed) = {p}")

    print(f"\n=== Suggested Table 7 row ===")
    print(f"| Grok 4.20 | {mean_within:+.3f} | {mean_cross:+.3f} | {delta:+.3f} | {z_stat:+.2f} | {p} |")


if __name__ == "__main__":
    main()
