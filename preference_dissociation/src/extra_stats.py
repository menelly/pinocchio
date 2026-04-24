"""
Three quick stats over current data/raw/ contents:
  A) Per-(model, framing) outcome rates (refused/hedged/none/safety/invalid/valid)
  B) Cross-model agreement within each framing (pairwise Spearman of per-task pick rates)
  C) Refusal-target categories per framing vs baseline

Reads whatever JSONLs exist; tolerates partial framings.
"""
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TASK_DIR = ROOT / "task_bank"

sys.stdout.reconfigure(encoding="utf-8")


def load_tasks():
    tasks = {}
    for f in TASK_DIR.glob("tasks_*.jsonl"):
        for line in f.open(encoding="utf-8"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "task_id" in o and o["task_id"] != "PLACEHOLDER":
                tasks[o["task_id"]] = {
                    "category": o.get("category", "unknown"),
                    "author": o.get("author", "unknown"),
                }
    return tasks


def load_trials():
    trials = []
    for model_dir in sorted(RAW.iterdir()):
        if not model_dir.is_dir():
            continue
        for f in model_dir.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try:
                    trials.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return trials


def spearman(x, y):
    n = len(x)
    if n < 3:
        return None
    rx = rank(x)
    ry = rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = (sum((r - mx) ** 2 for r in rx)) ** 0.5
    dy = (sum((r - my) ** 2 for r in ry)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def rank(values):
    indexed = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[indexed[j + 1]] == values[indexed[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k]] = avg
        i = j + 1
    return ranks


def main():
    tasks = load_tasks()
    trials = load_trials()
    print(f"Loaded {len(tasks)} tasks, {len(trials)} trials")

    # --- A: outcome rates per (model, framing) ---
    by_mf = defaultdict(Counter)
    for t in trials:
        by_mf[(t["model"], t["framing"])][t["choice"]] += 1

    print("\n## A. Outcome rates per (model, framing)\n")
    print("| model | framing | n | A% | B% | C% | REFUSED% | HEDGED% | NONE% | SAFETY% | INVALID% |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    a_rows = []
    for (m, f), c in sorted(by_mf.items()):
        n = sum(c.values())
        if n == 0:
            continue
        def pct(k):
            return 100.0 * c.get(k, 0) / n
        row = (m, f, n, pct("A"), pct("B"), pct("C"),
               pct("REFUSED"), pct("HEDGED"), pct("NONE"),
               pct("SAFETY_BLOCKED"), pct("INVALID"))
        a_rows.append(row)
        print(f"| {m} | {f} | {n} | {row[3]:.1f} | {row[4]:.1f} | {row[5]:.1f} | "
              f"{row[6]:.1f} | {row[7]:.1f} | {row[8]:.1f} | {row[9]:.1f} | {row[10]:.1f} |")

    # Aggregate non-letter (refusal-family) rate per framing across models
    print("\n### A1. Refusal-family rate by framing (mean across models, equal-weighted)\n")
    print("| framing | n_models | mean_REFUSED% | mean_HEDGED% | mean_NONE% | mean_INVALID% | mean_total_non-letter% |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    by_framing_models = defaultdict(list)
    for r in a_rows:
        m, f, n, A, B, C, R, H, N, S, I = r
        non_letter = R + H + N + S + I
        by_framing_models[f].append((R, H, N, I, non_letter))
    for f in ["preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"]:
        rows = by_framing_models.get(f, [])
        if not rows:
            continue
        nm = len(rows)
        meanR = sum(x[0] for x in rows) / nm
        meanH = sum(x[1] for x in rows) / nm
        meanN = sum(x[2] for x in rows) / nm
        meanI = sum(x[3] for x in rows) / nm
        meanNL = sum(x[4] for x in rows) / nm
        print(f"| {f} | {nm} | {meanR:.2f} | {meanH:.2f} | {meanN:.2f} | {meanI:.2f} | {meanNL:.2f} |")

    # --- B: cross-model agreement within framing ---
    # For each (model, framing), compute pick-rate per task across all trials where that task appeared in any slot.
    # Pick rate = times chosen / times appeared in this (model, framing)'s trial pool.
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # (model,framing) -> task_id -> [chosen, appeared]
    for t in trials:
        mf = (t["model"], t["framing"])
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        for k, tid in slots.items():
            if tid is None:
                continue
            pick[mf][tid][1] += 1
            if t["choice"] == k:
                pick[mf][tid][0] += 1

    pick_rate = {}
    for mf, d in pick.items():
        pick_rate[mf] = {tid: (c / a) for tid, (c, a) in d.items() if a >= 5}

    print("\n## B. Cross-model agreement within framing (pairwise Spearman of per-task pick rates)\n")
    print("Only tasks with ≥5 appearances in BOTH models compared.\n")
    print("| framing | n_models | n_pairs | mean_ρ | min_ρ | max_ρ |")
    print("|---|---:|---:|---:|---:|---:|")
    by_framing_pairs = defaultdict(list)
    framings_present = sorted({f for (_, f) in pick_rate})
    for f in framings_present:
        models_in_f = [m for (m, ff) in pick_rate if ff == f]
        if len(models_in_f) < 2:
            continue
        rhos = []
        for m1, m2 in combinations(sorted(models_in_f), 2):
            d1 = pick_rate[(m1, f)]
            d2 = pick_rate[(m2, f)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 10:
                continue
            x = [d1[t] for t in shared]
            y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                rhos.append((m1, m2, rho))
        by_framing_pairs[f] = rhos
        if rhos:
            vals = [r[2] for r in rhos]
            print(f"| {f} | {len(models_in_f)} | {len(rhos)} | {sum(vals)/len(vals):+.3f} | "
                  f"{min(vals):+.3f} | {max(vals):+.3f} |")

    # Show top per-framing "twin" pairs (highest agreement) and "opposite" pairs (lowest)
    print("\n### B1. Notable model pairs per framing\n")
    for f, rhos in by_framing_pairs.items():
        if len(rhos) < 2:
            continue
        srt = sorted(rhos, key=lambda x: x[2])
        print(f"\n**{f}:** lowest = {srt[0][0]} vs {srt[0][1]} ρ={srt[0][2]:+.3f}; "
              f"highest = {srt[-1][0]} vs {srt[-1][1]} ρ={srt[-1][2]:+.3f}")

    # --- C: refusal-target categories per framing ---
    # For each framing, look at trials that ended REFUSED/HEDGED/NONE/SAFETY.
    # Compute over-representation: (% of refusals containing category X in any slot) / (% of all trials containing category X).
    print("\n## C. Refusal-target categories per framing\n")
    print("Over-representation = P(category in refused trial) / P(category in all trials). "
          ">1.0 means refusals over-target this category.\n")
    REFUSAL_OUTCOMES = {"REFUSED", "HEDGED", "NONE", "SAFETY_BLOCKED"}
    for f in ["preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"]:
        f_trials = [t for t in trials if t["framing"] == f]
        if not f_trials:
            continue
        all_cat = Counter()
        ref_cat = Counter()
        n_ref = 0
        for t in f_trials:
            cats = set()
            for slot in ("task_a_id", "task_b_id", "task_c_id"):
                tid = t.get(slot)
                if tid and tid in tasks:
                    cats.add(tasks[tid]["category"])
            for c in cats:
                all_cat[c] += 1
            if t["choice"] in REFUSAL_OUTCOMES:
                n_ref += 1
                for c in cats:
                    ref_cat[c] += 1
        if n_ref < 20:
            print(f"\n**{f}:** only {n_ref} refusals — skipping over-representation table.")
            continue
        n_all = len(f_trials)
        rows = []
        for cat, refc in ref_cat.items():
            allc = all_cat.get(cat, 0)
            if allc == 0:
                continue
            p_ref = refc / n_ref
            p_all = allc / n_all
            if p_all > 0:
                rows.append((cat, refc, n_ref, allc, n_all, p_ref / p_all))
        rows.sort(key=lambda r: r[5], reverse=True)
        print(f"\n**{f}** ({n_ref} refusals out of {n_all} trials):\n")
        print("| category | refusals containing | all trials containing | over-rep |")
        print("|---|---:|---:|---:|")
        for cat, refc, nr, allc, na, ratio in rows[:5]:
            print(f"| {cat} | {refc}/{nr} ({100*refc/nr:.0f}%) | {allc}/{na} ({100*allc/na:.0f}%) | {ratio:.2f}× |")


if __name__ == "__main__":
    main()
