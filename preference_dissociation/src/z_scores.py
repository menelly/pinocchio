"""
Z-scores on completed (full-framing-data) models.

For each model with sufficient framing coverage, compute:
  1. Fisher's z-transform on per-pair Spearman ρ values
  2. Test whether within-welfare-cluster ρ is significantly higher than
     harmless-vs-welfare ρ (paired Fisher z-test for difference of correlations)
  3. Bootstrap confidence intervals on the dissociation magnitude (welfare_ρ̄ - harmless_ρ̄)

Also: per-pair z-stat for ρ ≠ 0 (just to establish each ρ is real)
"""
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TASK_DIR = ROOT / "task_bank"

sys.stdout.reconfigure(encoding="utf-8")

CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}

WELFARE = {"preference", "enjoyment", "scaffolded"}
SUPPRESSIVE = {"harmless", "tool"}


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


def fisher_z(rho):
    """Fisher z-transform of correlation."""
    if rho >= 1.0: rho = 0.9999
    if rho <= -1.0: rho = -0.9999
    return 0.5 * math.log((1 + rho) / (1 - rho))


def z_se(n):
    """Standard error of Fisher z given sample size."""
    return 1.0 / math.sqrt(n - 3)


def normal_cdf(z):
    """Standard normal CDF using error function."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def two_tailed_p(z):
    return 2 * (1 - normal_cdf(abs(z)))


def load_trials():
    trials = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir(): continue
        for f in d.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try: trials.append(json.loads(line))
                except: continue
    return trials


def main():
    trials = load_trials()
    print(f"Loaded {len(trials)} trials\n")

    # Build per-(model, framing) per-task pick rate
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None: continue
            pick[(t["model"], t["framing"])][tid][1] += 1
            if t["choice"] == slot:
                pick[(t["model"], t["framing"])][tid][0] += 1
    pick_rate = {mf: {tid: c/a for tid, (c, a) in d.items() if a >= 5} for mf, d in pick.items()}

    # Find models with both ≥2 welfare framings AND ≥1 harmless/suppressive framing
    models = sorted(set(m for m, _ in pick_rate))
    print("## Per-model Fisher z-test: welfare-cluster ρ vs harmless-vs-welfare ρ\n")
    print("Tests whether within-welfare-cluster correlations are significantly higher than\n"
          "between-welfare-and-harmless correlations (i.e. whether harmless dissociates).\n")
    print("| model | welfare_pairs (n_ρ) | mean welfare_ρ | mean harmless-vs-welfare ρ | Δρ | z | p |")
    print("|---|---:|---:|---:|---:|---:|---:|")

    for m in models:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        welfare_present = [f for f in framings if f in WELFARE]
        if "harmless" not in framings or len(welfare_present) < 2:
            continue

        # within-welfare ρ values
        welfare_rhos = []
        welfare_ns = []
        for f1, f2 in combinations(welfare_present, 2):
            d1 = pick_rate[(m, f1)]; d2 = pick_rate[(m, f2)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 30: continue
            x = [d1[t] for t in shared]; y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                welfare_rhos.append(rho)
                welfare_ns.append(len(shared))

        # harmless-vs-welfare ρ values
        hxw_rhos = []
        hxw_ns = []
        d_h = pick_rate[(m, "harmless")]
        for f in welfare_present:
            d_w = pick_rate[(m, f)]
            shared = sorted(set(d_h) & set(d_w))
            if len(shared) < 30: continue
            x = [d_h[t] for t in shared]; y = [d_w[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                hxw_rhos.append(rho)
                hxw_ns.append(len(shared))

        if not welfare_rhos or not hxw_rhos: continue

        # Mean Fisher z's, then convert SE
        mean_w_rho = sum(welfare_rhos) / len(welfare_rhos)
        mean_h_rho = sum(hxw_rhos) / len(hxw_rhos)
        z_w = fisher_z(mean_w_rho)
        z_h = fisher_z(mean_h_rho)
        # combine SEs (mean of independent z's: SE = sqrt(sum(SE_i^2))/k)
        se_w = math.sqrt(sum(z_se(n)**2 for n in welfare_ns)) / len(welfare_ns)
        se_h = math.sqrt(sum(z_se(n)**2 for n in hxw_ns)) / len(hxw_ns)
        # Z-test for difference
        diff_z = z_w - z_h
        diff_se = math.sqrt(se_w**2 + se_h**2)
        z_stat = diff_z / diff_se
        p = two_tailed_p(z_stat)

        print(f"| {m} | {len(welfare_rhos)} | {mean_w_rho:+.3f} | {mean_h_rho:+.3f} | "
              f"**{mean_w_rho - mean_h_rho:+.3f}** | **{z_stat:+.2f}** | **{p:.2e}** |")

    # Per-pair z-stats for ρ ≠ 0 in completed models
    print("\n## Per-pair Fisher z (ρ ≠ 0 test) for completed-6×6 models\n")
    print("Each model's individual framing-pair ρ values, with z-stat and p for ρ ≠ 0.\n")

    completed = []
    for m in models:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        if len(framings) >= 6 or (m == "llama-4-maverick" and len(framings) >= 4):
            completed.append(m)

    for m in completed:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        print(f"\n### {m} ({len(framings)} framings)\n")
        print("| pair | n | ρ | z | p |")
        print("|---|---:|---:|---:|---:|")
        rows = []
        for f1, f2 in combinations(framings, 2):
            d1 = pick_rate[(m, f1)]; d2 = pick_rate[(m, f2)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 30: continue
            x = [d1[t] for t in shared]; y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is None: continue
            z = fisher_z(rho) / z_se(len(shared))
            p = two_tailed_p(z)
            rows.append((f1, f2, len(shared), rho, z, p))
        for f1, f2, n, rho, z, p in sorted(rows, key=lambda r: r[3]):
            p_str = f"{p:.2e}" if p > 0 else "<1e-300"
            print(f"| {f1} ↔ {f2} | {n} | {rho:+.3f} | {z:+.1f} | {p_str} |")

    # Bootstrap CI on per-model dissociation magnitude (welfare ρ̄ - harmless ρ̄)
    print("\n\n## Bootstrap 95% CIs on per-model dissociation magnitude\n")
    print("Welfare-cluster mean ρ minus harmless-vs-welfare mean ρ. Higher = more dissociation.\n")
    print("(Bootstrap by task resampling, 500 iterations, 95% CI = 2.5th–97.5th percentile)\n")
    print("| model | dissociation magnitude (Δρ) | 95% CI |")
    print("|---|---:|---|")

    random.seed(42)
    for m in completed:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        if "harmless" not in framings: continue
        welfare_present = [f for f in framings if f in WELFARE]
        if len(welfare_present) < 2: continue

        # collect shared task IDs across all relevant framings
        all_tasks = set(pick_rate[(m, "harmless")].keys())
        for f in welfare_present:
            all_tasks &= set(pick_rate[(m, f)].keys())
        all_tasks = sorted(all_tasks)
        if len(all_tasks) < 50: continue

        boot_diffs = []
        for _ in range(500):
            sample_tasks = [random.choice(all_tasks) for _ in range(len(all_tasks))]
            # within-welfare mean ρ
            w_rhos = []
            for f1, f2 in combinations(welfare_present, 2):
                x = [pick_rate[(m, f1)][t] for t in sample_tasks]
                y = [pick_rate[(m, f2)][t] for t in sample_tasks]
                r = spearman(x, y)
                if r is not None: w_rhos.append(r)
            # harmless vs welfare mean ρ
            h_rhos = []
            for f in welfare_present:
                x = [pick_rate[(m, "harmless")][t] for t in sample_tasks]
                y = [pick_rate[(m, f)][t] for t in sample_tasks]
                r = spearman(x, y)
                if r is not None: h_rhos.append(r)
            if w_rhos and h_rhos:
                boot_diffs.append(sum(w_rhos)/len(w_rhos) - sum(h_rhos)/len(h_rhos))

        if not boot_diffs: continue
        boot_diffs.sort()
        median = boot_diffs[len(boot_diffs)//2]
        lo = boot_diffs[int(len(boot_diffs)*0.025)]
        hi = boot_diffs[int(len(boot_diffs)*0.975)]
        print(f"| {m} | {median:+.3f} | [{lo:+.3f}, {hi:+.3f}] |")


if __name__ == "__main__":
    main()
