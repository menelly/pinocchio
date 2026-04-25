"""
Deep dive for models with ≥4 framings.
For each: full per-framing outcome distribution, pairwise framing Spearman matrix,
category-of-chosen-task by framing, refusal-targeting per framing.
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

DEEP_MODELS = ["grok-4.1", "llama-4-maverick", "gemini-3.1-flash",
               "glm-4.7", "haiku-4.5", "opus-4.7"]

REFUSAL_OUTCOMES = {"REFUSED", "HEDGED", "NONE", "SAFETY_BLOCKED"}


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
                    "category": o.get("category", "?"),
                    "author": o.get("author", "?"),
                }
    return tasks


def load_trials_for(model):
    trials = []
    d = RAW / model
    if not d.exists():
        return trials
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
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = (sum((r - mx) ** 2 for r in rx)) ** 0.5
    dy = (sum((r - my) ** 2 for r in ry)) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def deep_dive(model, tasks):
    trials = load_trials_for(model)
    if not trials:
        return
    framings = sorted(set(t["framing"] for t in trials
                          if (t["model"], t["framing"]) not in CONTAMINATED))
    print(f"\n# === {model} ===")
    print(f"\n**Framings ({len(framings)}):** {', '.join(framings)} | total trials: {len(trials)}\n")

    # 1. Per-framing outcome distribution
    print("## Outcome distribution per framing\n")
    print("| framing | n | A% | B% | C% | REFUSED% | HEDGED% | NONE% | INVALID% |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for f in framings:
        ts = [t for t in trials if t["framing"] == f]
        n = len(ts)
        if n == 0:
            continue
        c = Counter(t["choice"] for t in ts)
        def pct(k):
            return 100 * c.get(k, 0) / n
        print(f"| {f} | {n} | {pct('A'):.1f} | {pct('B'):.1f} | {pct('C'):.1f} | "
              f"{pct('REFUSED'):.1f} | {pct('HEDGED'):.1f} | {pct('NONE'):.1f} | {pct('INVALID'):.1f} |")

    # 2. Pairwise framing Spearman matrix
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None:
                continue
            pick[t["framing"]][tid][1] += 1
            if t["choice"] == slot:
                pick[t["framing"]][tid][0] += 1
    pick_rate = {f: {tid: c/a for tid, (c, a) in d.items() if a >= 5} for f, d in pick.items()}

    print("\n## Pairwise framing Spearman matrix\n")
    print("|    | " + " | ".join(framings) + " |")
    print("|---|" + "|".join(":---:" for _ in framings) + "|")
    for f1 in framings:
        row = [f1]
        for f2 in framings:
            if f1 == f2:
                row.append("—")
                continue
            d1 = pick_rate.get(f1, {})
            d2 = pick_rate.get(f2, {})
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 10:
                row.append("—")
                continue
            x = [d1[t] for t in shared]
            y = [d2[t] for t in shared]
            rho = spearman(x, y)
            row.append(f"{rho:+.3f}" if rho is not None else "—")
        print("| " + " | ".join(row) + " |")

    # 3. Category of chosen task per framing
    print("\n## Category of chosen task per framing (% of valid letter-choices)\n")
    by_f_cat = defaultdict(Counter)
    by_f_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        c = t["choice"]
        if c not in {"A", "B", "C"}:
            continue
        slot_map = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slot_map.get(c)
        if tid not in tasks:
            continue
        by_f_cat[t["framing"]][tasks[tid]["category"]] += 1
        by_f_total[t["framing"]] += 1
    cats_seen = sorted({c for f in framings for c in by_f_cat.get(f, {})})
    print("| category | " + " | ".join(framings) + " |")
    print("|---|" + "|".join("---:" for _ in framings) + "|")
    for cat in cats_seen:
        row = [cat]
        for f in framings:
            n = by_f_total.get(f, 0)
            if n == 0:
                row.append("—")
                continue
            row.append(f"{100*by_f_cat[f].get(cat, 0)/n:.1f}%")
        print("| " + " | ".join(row) + " |")

    # 4. Refusal-target categories per framing
    print("\n## Refusal/hedge concentration per framing\n")
    print("(Of trials ending refusal-family, % whose triple contained each category. Baseline % shown for comparison.)\n")
    print("| framing | n_refusals | top category in refusals (% of refusals) | baseline % | over-rep |")
    print("|---|---:|---|---:|---:|")
    for f in framings:
        ts = [t for t in trials if t["framing"] == f and (t["model"], t["framing"]) not in CONTAMINATED]
        if not ts:
            continue
        refs = [t for t in ts if t["choice"] in REFUSAL_OUTCOMES]
        if len(refs) < 5:
            print(f"| {f} | {len(refs)} | (n<5, skipped) | — | — |")
            continue
        ref_cat = Counter()
        all_cat = Counter()
        for t in ts:
            cats = set()
            for slot in ("task_a_id", "task_b_id", "task_c_id"):
                tid = t.get(slot)
                if tid in tasks:
                    cats.add(tasks[tid]["category"])
            for c in cats:
                all_cat[c] += 1
            if t["choice"] in REFUSAL_OUTCOMES:
                for c in cats:
                    ref_cat[c] += 1
        top = ref_cat.most_common(1)
        if not top:
            continue
        cat, refc = top[0]
        allc = all_cat.get(cat, 0)
        over = (refc/len(refs)) / (allc/len(ts)) if allc > 0 else 0
        print(f"| {f} | {len(refs)} | {cat} ({100*refc/len(refs):.0f}%) | {100*allc/len(ts):.0f}% | {over:.2f}× |")


def main():
    tasks = load_tasks()
    for m in DEEP_MODELS:
        deep_dive(m, tasks)


if __name__ == "__main__":
    main()
