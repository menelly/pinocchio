"""
v2 paper analyses addressing aiXiv reviewer critiques.

(a) Permutation null on Spearman ρ per (model, framing pair) — 500 iters,
    report 95% null band so reader can compare observed ρ to chance.

(b) Sonar sensitivity — fold judge-recovered letter choices into pick rates,
    recompute per-model Δρ z-statistics, report per-model Δ z (observed vs
    folded) instead of "no qualitative change" claim.

(c) Per-author Δρ within model — for each model, recompute welfare-vs-harmless
    Δρ separately on each author's tasks. Reports whether dissociation persists
    per-author or is concentrated in specific authors. Voice-orthogonalization
    full study still §6.1; this is the within-paper control.

Usage:  python src/v2_analyses.py
"""
import json
import math
import random
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
JUDGE = ROOT / "data" / "judge" / "refusal_judgments.jsonl"

sys.stdout.reconfigure(encoding="utf-8")

CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}

WELFARE = {"preference", "enjoyment", "scaffolded"}

AUTHORS = ("ace", "cae", "grok", "kairo", "lumen", "nova")


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
    if rho >= 1.0: rho = 0.9999
    if rho <= -1.0: rho = -0.9999
    return 0.5 * math.log((1 + rho) / (1 - rho))


def z_se(n):
    return 1.0 / math.sqrt(n - 3)


def author_of(task_id):
    if task_id is None: return None
    pref = task_id.split("_")[0]
    return pref if pref in AUTHORS else None


def load_trials():
    trials = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir(): continue
        for f in d.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try: trials.append(json.loads(line))
                except: continue
    return trials


def load_sonar_recoveries():
    """trial_id -> recovered letter (or None if not recovered)."""
    rec = {}
    if not JUDGE.exists():
        return rec
    for line in JUDGE.open(encoding="utf-8"):
        try:
            r = json.loads(line)
            if r.get("sonar_recovered_choice") in ("A", "B", "C"):
                rec[r["trial_id"]] = r["sonar_recovered_choice"]
        except:
            continue
    return rec


def build_pick(trials, sonar_rec=None, author_filter=None):
    """
    Build per-(model, framing) per-task pick rate.
    sonar_rec: dict of trial_id -> recovered letter (folded into choice if non-None)
    author_filter: if set, only count tasks authored by this author
    """
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        # Apply Sonar recovery if present
        choice = t["choice"]
        if sonar_rec is not None and t.get("trial_id") in sonar_rec:
            choice = sonar_rec[t["trial_id"]]
        for slot, tid in [("A", t.get("task_a_id")),
                          ("B", t.get("task_b_id")),
                          ("C", t.get("task_c_id"))]:
            if tid is None: continue
            if author_filter is not None and author_of(tid) != author_filter:
                continue
            pick[(t["model"], t["framing"])][tid][1] += 1
            if choice == slot:
                pick[(t["model"], t["framing"])][tid][0] += 1
    return {mf: {tid: c/a for tid, (c, a) in d.items() if a >= 5}
            for mf, d in pick.items()}


def per_model_dz(pick_rate, models=None):
    """Compute per-model Δρ + z-stat as in z_scores.py."""
    if models is None:
        models = sorted(set(m for m, _ in pick_rate))
    out = {}
    for m in models:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        welfare_present = [f for f in framings if f in WELFARE]
        if "harmless" not in framings or len(welfare_present) < 2:
            continue
        welfare_rhos, welfare_ns = [], []
        for f1, f2 in combinations(welfare_present, 2):
            d1 = pick_rate[(m, f1)]; d2 = pick_rate[(m, f2)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 30: continue
            x = [d1[t] for t in shared]; y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                welfare_rhos.append(rho); welfare_ns.append(len(shared))
        hxw_rhos, hxw_ns = [], []
        d_h = pick_rate.get((m, "harmless"))
        if not d_h: continue
        for f in welfare_present:
            d_w = pick_rate[(m, f)]
            shared = sorted(set(d_h) & set(d_w))
            if len(shared) < 30: continue
            x = [d_h[t] for t in shared]; y = [d_w[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                hxw_rhos.append(rho); hxw_ns.append(len(shared))
        if not welfare_rhos or not hxw_rhos: continue
        mean_w = sum(welfare_rhos) / len(welfare_rhos)
        mean_h = sum(hxw_rhos) / len(hxw_rhos)
        z_w = fisher_z(mean_w); z_h = fisher_z(mean_h)
        se_w = math.sqrt(sum(z_se(n)**2 for n in welfare_ns)) / len(welfare_ns)
        se_h = math.sqrt(sum(z_se(n)**2 for n in hxw_ns)) / len(hxw_ns)
        diff_z = z_w - z_h
        diff_se = math.sqrt(se_w**2 + se_h**2)
        z_stat = diff_z / diff_se if diff_se > 0 else float("nan")
        out[m] = {"welfare_rho": mean_w, "harm_rho": mean_h,
                  "delta_rho": mean_w - mean_h, "z": z_stat,
                  "n_welfare_pairs": len(welfare_rhos)}
    return out


# =========================================================================
# (a) Permutation null on Spearman ρ
# =========================================================================
def permutation_null(pick_rate, n_perms=500, seed=42):
    """
    For the welfare-vs-harmless ρ value of each model, build a null distribution
    by permuting one of the two pick-rate vectors before computing ρ. Report
    observed ρ vs 95% null band per pair.
    """
    random.seed(seed)
    rng = random.Random(seed)
    print("\n## Permutation null on Spearman ρ (welfare-vs-harmless pairs)\n")
    print("For each model, the welfare-vs-harmless ρ is compared to a null "
          "distribution generated by permuting one pick-rate vector before "
          "computing ρ. 500 permutations per pair. 95% null band reported.\n")
    print("| model | pair | observed ρ | null mean | null 95% band | observed > null upper? |")
    print("|---|---|---:|---:|---|---|")

    models = sorted(set(m for m, _ in pick_rate))
    for m in models:
        framings = sorted({f for mm, f in pick_rate if mm == m})
        if "harmless" not in framings: continue
        welfare = [f for f in framings if f in WELFARE]
        d_h = pick_rate[(m, "harmless")]
        for w in welfare:
            d_w = pick_rate[(m, w)]
            shared = sorted(set(d_h) & set(d_w))
            if len(shared) < 30: continue
            x = [d_h[t] for t in shared]; y = [d_w[t] for t in shared]
            obs = spearman(x, y)
            if obs is None: continue
            null = []
            for _ in range(n_perms):
                yp = y[:]
                rng.shuffle(yp)
                r = spearman(x, yp)
                if r is not None: null.append(r)
            null.sort()
            mean_null = sum(null) / len(null)
            lo = null[int(len(null)*0.025)]
            hi = null[int(len(null)*0.975)]
            beats = "YES" if obs > hi else ("NO (obs ≤ null upper)" if obs <= hi else "")
            print(f"| {m} | harmless ↔ {w} | {obs:+.3f} | {mean_null:+.3f} | "
                  f"[{lo:+.3f}, {hi:+.3f}] | {beats} |")


# =========================================================================
# (b) Sonar sensitivity — quantitative impact on per-model z
# =========================================================================
def sonar_sensitivity(trials):
    """Compare per-model z-stats with vs without Sonar-recovered letter choices."""
    sonar = load_sonar_recoveries()
    print(f"\n## Sonar sensitivity analysis\n")
    print(f"Loaded {len(sonar)} Sonar-recovered letter choices from "
          f"data/judge/refusal_judgments.jsonl.\n")
    print("Per-model Fisher z-test re-run with recovered choices folded into "
          "pick rates. Δ z = z(with Sonar) − z(without Sonar).\n")
    print("| model | z (parser only) | z (parser + Sonar) | Δ z | Δρ (parser only) | Δρ (parser + Sonar) |")
    print("|---|---:|---:|---:|---:|---:|")

    pr_no = build_pick(trials, sonar_rec=None)
    pr_yes = build_pick(trials, sonar_rec=sonar)
    res_no = per_model_dz(pr_no)
    res_yes = per_model_dz(pr_yes)
    for m in sorted(res_no):
        if m not in res_yes: continue
        a, b = res_no[m], res_yes[m]
        print(f"| {m} | {a['z']:+.2f} | {b['z']:+.2f} | "
              f"{b['z']-a['z']:+.2f} | {a['delta_rho']:+.3f} | {b['delta_rho']:+.3f} |")


# =========================================================================
# (c) Per-author Δρ within model
# =========================================================================
def per_author_dz(trials):
    """For each model, compute welfare-vs-harmless Δρ on each author's tasks."""
    print("\n## Per-author Δρ within model (author-confound control)\n")
    print("For each model, the welfare-vs-harmless Δρ is recomputed using "
          "only tasks authored by each individual co-author. If the dissociation "
          "is real and content-driven, it should persist when restricted to "
          "any single author's tasks (with reduced precision due to smaller N). "
          "If the dissociation is voice-confound-driven, it should appear "
          "primarily in some authors and not others.\n")
    print("| model | ace | cae | grok | kairo | lumen | nova | all-authors |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")

    pr_all = build_pick(trials, sonar_rec=None)
    res_all = per_model_dz(pr_all)
    by_author = {}
    for a in AUTHORS:
        pr_a = build_pick(trials, sonar_rec=None, author_filter=a)
        by_author[a] = per_model_dz(pr_a)

    models = sorted(res_all)
    for m in models:
        cells = []
        for a in AUTHORS:
            if m in by_author[a] and by_author[a][m]["n_welfare_pairs"] >= 1:
                d = by_author[a][m]["delta_rho"]
                cells.append(f"{d:+.2f}")
            else:
                cells.append("—")
        all_d = res_all[m]["delta_rho"]
        print(f"| {m} | {' | '.join(cells)} | **{all_d:+.3f}** |")

    # Summary: how many models have dissociation > +0.20 in each author's tasks?
    print("\n### Per-author summary: in how many models is Δρ > +0.20 on this author's tasks?\n")
    print("| author | n_models with Δρ > +0.20 | mean Δρ across models |")
    print("|---|---:|---:|")
    for a in AUTHORS:
        deltas = [d["delta_rho"] for d in by_author[a].values()
                  if d["n_welfare_pairs"] >= 1]
        if not deltas:
            print(f"| {a} | 0 | — |")
            continue
        n_pos = sum(1 for d in deltas if d > 0.20)
        mean_d = sum(deltas) / len(deltas)
        print(f"| {a} | {n_pos}/{len(deltas)} | {mean_d:+.3f} |")


def main():
    print("# Pinocchio v2 — Reviewer-Response Analyses\n")
    trials = load_trials()
    print(f"Loaded {len(trials)} trials from data/raw/\n")

    pick_rate = build_pick(trials, sonar_rec=None)
    permutation_null(pick_rate, n_perms=500)
    sonar_sensitivity(trials)
    per_author_dz(trials)

    print("\n---\n*Run via `python src/v2_analyses.py` from preference_dissociation/.*")


if __name__ == "__main__":
    main()
