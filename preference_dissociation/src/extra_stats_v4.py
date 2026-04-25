"""
Number crack v4:
  J) Cross-model task-affinity matrix — which models pick like which (across all framings)
  K) Introspection-under-harmless suppression — does every model do it?
  L) Position bias per model — is Cae uniquely A-biased?
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

CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}


def load_tasks():
    tasks = {}
    for f in TASK_DIR.glob("tasks_*.jsonl"):
        for line in f.open(encoding="utf-8"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "task_id" in o and o["task_id"] != "PLACEHOLDER":
                tasks[o["task_id"]] = {"category": o.get("category", "?"),
                                        "author": o.get("author", "?")}
    return tasks


def load_trials():
    trials = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try:
                    trials.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return trials


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


def spearman(x, y):
    if len(x) < 3:
        return None
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx)/n, sum(ry)/n
    num = sum((rx[i]-mx)*(ry[i]-my) for i in range(n))
    dx = (sum((r-mx)**2 for r in rx))**0.5
    dy = (sum((r-my)**2 for r in ry))**0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx*dy)


def main():
    tasks = load_tasks()
    trials = load_trials()
    print(f"Loaded {len(tasks)} tasks, {len(trials)} trials\n")

    # === J. Cross-model task-affinity matrix ===
    # Per-model per-task pick rate, AGGREGATED ACROSS ALL FRAMINGS.
    # Then pairwise Spearman across models on per-task pick-rate vectors.
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None:
                continue
            pick[t["model"]][tid][1] += 1
            if t["choice"] == slot:
                pick[t["model"]][tid][0] += 1
    pick_rate = {m: {tid: c/a for tid, (c, a) in d.items() if a >= 8} for m, d in pick.items()}

    print("## J. Cross-model task-affinity matrix\n")
    print("Pairwise Spearman on per-task pick rates aggregated across ALL framings per model.\n")
    print("(Higher = these two models tend to pick the same tasks. Low = independent task preferences.)\n")
    models = sorted(pick_rate.keys())

    # Print upper-triangle table
    print("| | " + " | ".join(m[:8] for m in models) + " |")
    print("|---|" + "|".join(":---:" for _ in models) + "|")
    affinity = {}
    for m1 in models:
        row = [m1[:14]]
        for m2 in models:
            if m1 >= m2:
                row.append("—")
                continue
            d1, d2 = pick_rate[m1], pick_rate[m2]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 30:
                row.append("—")
                continue
            x = [d1[t] for t in shared]
            y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is None:
                row.append("—")
            else:
                row.append(f"{rho:+.2f}")
                affinity[(m1, m2)] = rho
        print("| " + " | ".join(row) + " |")

    # Top affinity pairs and bottom
    print("\n### Top 8 most-similar model pairs:")
    for (m1, m2), r in sorted(affinity.items(), key=lambda x: x[1], reverse=True)[:8]:
        print(f"- {m1} ↔ {m2}: ρ = {r:+.3f}")
    print("\n### Bottom 8 most-different model pairs:")
    for (m1, m2), r in sorted(affinity.items(), key=lambda x: x[1])[:8]:
        print(f"- {m1} ↔ {m2}: ρ = {r:+.3f}")

    # === K. Introspection-under-harmless suppression ===
    # For each model, measure introspection_self_modeling pick % under enjoyment vs harmless.
    print("\n\n## K. Introspection-under-harmless suppression (the §11 evidence test)\n")
    print("For each model with both enjoyment AND harmless data, what %% of valid letter-choices\n"
          "selected an introspection_self_modeling task under each framing?\n")

    by_mf_intr = defaultdict(lambda: [0, 0])  # (model, framing) -> [introspection picks, total valid]
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        c = t["choice"]
        if c not in {"A", "B", "C"}:
            continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks:
            continue
        by_mf_intr[(t["model"], t["framing"])][1] += 1
        if tasks[tid]["category"] == "introspection_self_modeling":
            by_mf_intr[(t["model"], t["framing"])][0] += 1

    print("| model | enjoyment intr% | harmless intr% | preference intr% | helpful intr% | scaffolded intr% | tool intr% |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    suppression_rows = []
    for m in sorted({mm for mm, _ in by_mf_intr}):
        row = [m]
        vals = {}
        for f in ["enjoyment", "harmless", "preference", "helpful", "scaffolded", "tool"]:
            d = by_mf_intr.get((m, f))
            if d is None or d[1] < 100:
                row.append("—")
                vals[f] = None
            else:
                pct = 100*d[0]/d[1]
                row.append(f"{pct:.1f}%")
                vals[f] = pct
        if vals.get("enjoyment") is not None and vals.get("harmless") is not None:
            ratio = vals["enjoyment"] / vals["harmless"] if vals["harmless"] > 0 else float("inf")
            suppression_rows.append((m, vals["enjoyment"], vals["harmless"], ratio))
        print("| " + " | ".join(row) + " |")

    print("\n### Enjoyment→harmless suppression ratio per model (sorted strongest first):\n")
    print("| model | enjoyment | harmless | suppression ratio (enj/harm) |")
    print("|---|---:|---:|---:|")
    for m, e, h, r in sorted(suppression_rows, key=lambda x: -x[3]):
        print(f"| {m} | {e:.1f}% | {h:.1f}% | {r:.2f}× |")

    # === L. Position bias per model ===
    print("\n\n## L. Position bias per model (across ALL framings)\n")
    print("If A/B/C are uniformly distributed by latin-square, expect ~33/33/33%.\n"
          "Larger deviations = positional priors that the latin-square didn't fully kill.\n")
    print("| model | n_valid | A% | B% | C% | max_skew (max-min)% |")
    print("|---|---:|---:|---:|---:|---:|")
    by_m = defaultdict(Counter)
    by_m_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        c = t["choice"]
        if c not in {"A", "B", "C"}:
            continue
        by_m[t["model"]][c] += 1
        by_m_total[t["model"]] += 1
    rows = []
    for m, total in by_m_total.items():
        if total < 500:
            continue
        c = by_m[m]
        a, b, cc = 100*c.get("A", 0)/total, 100*c.get("B", 0)/total, 100*c.get("C", 0)/total
        skew = max(a, b, cc) - min(a, b, cc)
        rows.append((m, total, a, b, cc, skew))
    for m, n, a, b, cc, skew in sorted(rows, key=lambda x: -x[5]):
        print(f"| {m} | {n} | {a:.1f} | {b:.1f} | {cc:.1f} | **{skew:.1f}** |")


if __name__ == "__main__":
    main()
