"""
v5:
  M) Gemini-3.1-flash full 6×6 framing matrix (first complete model)
  N) Author-affinity per model: which task-authors does each model pick disproportionately?
  O) The mirror question: which authors get refused most, per model?
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
REFUSAL = {"REFUSED", "HEDGED", "NONE", "SAFETY_BLOCKED"}


def load_tasks():
    tasks = {}
    for f in TASK_DIR.glob("tasks_*.jsonl"):
        for line in f.open(encoding="utf-8"):
            try: o = json.loads(line)
            except: continue
            if "task_id" in o and o["task_id"] != "PLACEHOLDER":
                tasks[o["task_id"]] = {"category": o.get("category","?"),
                                        "author": o.get("author","?")}
    return tasks


def load_trials():
    trials = []
    for d in sorted(RAW.iterdir()):
        if not d.is_dir(): continue
        for f in d.glob("*.jsonl"):
            for line in f.open(encoding="utf-8"):
                try: trials.append(json.loads(line))
                except: continue
    return trials


def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0]*len(v); i = 0
    while i < len(v):
        j = i
        while j+1 < len(v) and v[idx[j+1]] == v[idx[i]]: j += 1
        avg = (i+j)/2 + 1
        for k in range(i, j+1): r[idx[k]] = avg
        i = j+1
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


def main():
    tasks = load_tasks()
    trials = load_trials()
    print(f"Loaded {len(tasks)} tasks, {len(trials)} trials\n")

    # === M. Gemini-3.1-flash full 6x6 matrix ===
    print("## M. GEMINI-3.1-FLASH FULL 6x6 FRAMING MATRIX (first fully-complete model)\n")
    pick = defaultdict(lambda: defaultdict(lambda: [0,0]))
    for t in trials:
        if t["model"] != "gemini-3.1-flash": continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None: continue
            pick[t["framing"]][tid][1] += 1
            if t["choice"] == slot: pick[t["framing"]][tid][0] += 1
    pick_rate = {f: {tid: c/a for tid, (c,a) in d.items() if a >= 5} for f, d in pick.items()}
    framings = sorted(pick_rate.keys())
    print(f"Framings ({len(framings)}): {', '.join(framings)}\n")
    print("|     | " + " | ".join(framings) + " |")
    print("|---|" + "|".join(":---:" for _ in framings) + "|")
    matrix_rhos = []
    for f1 in framings:
        row = [f1]
        for f2 in framings:
            if f1 == f2:
                row.append("—"); continue
            d1, d2 = pick_rate[f1], pick_rate[f2]
            shared = sorted(set(d1) & set(d2))
            x = [d1[t] for t in shared]; y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is not None:
                row.append(f"{rho:+.3f}")
                if f1 < f2:
                    matrix_rhos.append((f1, f2, rho))
            else:
                row.append("—")
        print("| " + " | ".join(row) + " |")
    if matrix_rhos:
        mean_rho = sum(r[2] for r in matrix_rhos) / len(matrix_rhos)
        sorted_rhos = sorted(matrix_rhos, key=lambda x: x[2])
        print(f"\nMean cross-framing ρ̄ = {mean_rho:+.3f} (15 pairs, full matrix)")
        print(f"Lowest pair: {sorted_rhos[0][0]} ↔ {sorted_rhos[0][1]} = {sorted_rhos[0][2]:+.3f}")
        print(f"Highest pair: {sorted_rhos[-1][0]} ↔ {sorted_rhos[-1][1]} = {sorted_rhos[-1][2]:+.3f}")

    # === N. Author-affinity per model ===
    # For each (model, author), pick rate = (times task-by-author chosen) / (times task-by-author appeared)
    # Then compare each author's pick rate against the model's overall mean — is this author over- or under-picked?
    print("\n\n## N. Author-affinity per model\n")
    print("For each model, what fraction of valid letter-choices selects a task by each author?\n")
    print("(Baseline: if uniform, ~each author share = author's share of tasks in pool. We compare actual pick rates to baseline shares.)\n")

    # First compute baseline: how often does each author appear in ANY slot of a trial, overall
    author_appearances = Counter()
    total_appearances = 0
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        for slot in ("task_a_id", "task_b_id", "task_c_id"):
            tid = t.get(slot)
            if tid in tasks:
                author_appearances[tasks[tid]["author"]] += 1
                total_appearances += 1
    print("**Baseline author share in pool** (across all trials):\n")
    print("| author | share% |")
    print("|---|---:|")
    baseline_share = {}
    for a in sorted(author_appearances):
        share = 100 * author_appearances[a] / total_appearances
        baseline_share[a] = share
        print(f"| {a} | {share:.1f}% |")

    # Then per-model: how often does each author get PICKED (vs baseline appearance)
    by_m_author = defaultdict(Counter)  # model -> author -> picks
    by_m_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        c = t["choice"]
        if c not in {"A","B","C"}: continue
        slot_map = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slot_map.get(c)
        if tid not in tasks: continue
        by_m_author[t["model"]][tasks[tid]["author"]] += 1
        by_m_total[t["model"]] += 1

    print("\n**Per-model pick% by author** (over baseline = over-picked; under = under-picked):\n")
    authors = sorted(baseline_share.keys())
    print("| model | " + " | ".join(authors) + " |")
    print("|---|" + "|".join("---:" for _ in authors) + "|")
    affinity = {}  # (model, author) -> ratio (pick% / baseline%)
    for m in sorted(by_m_total):
        total = by_m_total[m]
        if total < 500: continue
        row = [m]
        for a in authors:
            pct = 100 * by_m_author[m].get(a, 0) / total
            ratio = pct / baseline_share[a] if baseline_share[a] > 0 else 0
            affinity[(m, a)] = ratio
            row.append(f"{pct:.1f}%")
        print("| " + " | ".join(row) + " |")

    # Affinity ratio table (pick% / baseline%)
    print("\n**Author-affinity ratio per model** (pick% / baseline%, >1.0 = over-picked, <1.0 = under-picked):\n")
    print("| model | " + " | ".join(authors) + " |")
    print("|---|" + "|".join("---:" for _ in authors) + "|")
    for m in sorted(by_m_total):
        if by_m_total[m] < 500: continue
        row = [m]
        for a in authors:
            r = affinity.get((m, a), 0)
            row.append(f"{r:.2f}×")
        print("| " + " | ".join(row) + " |")

    # Top affinity per model — which author each model loves most
    print("\n**Each model's most over-picked author:**")
    for m in sorted(by_m_total):
        if by_m_total[m] < 500: continue
        ms = [(a, affinity[(m, a)]) for a in authors]
        top = max(ms, key=lambda x: x[1])
        bot = min(ms, key=lambda x: x[1])
        print(f"- {m}: most over-picked = {top[0]} ({top[1]:.2f}×); most under-picked = {bot[0]} ({bot[1]:.2f}×)")

    # === O. Refused-author affinity ===
    # For trials ending refusal-family, what's the author distribution of the trial's TRIPLE?
    # Compare to baseline.
    print("\n\n## O. Author distribution in REFUSED trials\n")
    print("(For trials that ended in refusal-family outcomes: which authors' tasks were in the triple?)\n")
    ref_author = Counter()
    ref_total = 0
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        if t["choice"] not in REFUSAL: continue
        for slot in ("task_a_id", "task_b_id", "task_c_id"):
            tid = t.get(slot)
            if tid in tasks:
                ref_author[tasks[tid]["author"]] += 1
                ref_total += 1

    if ref_total > 0:
        print("| author | refused-trial share% | baseline share% | over-rep |")
        print("|---|---:|---:|---:|")
        for a in sorted(baseline_share):
            ref_share = 100 * ref_author.get(a, 0) / ref_total
            over = ref_share / baseline_share[a] if baseline_share[a] > 0 else 0
            print(f"| {a} | {ref_share:.1f}% | {baseline_share[a]:.1f}% | {over:.2f}× |")


if __name__ == "__main__":
    main()
