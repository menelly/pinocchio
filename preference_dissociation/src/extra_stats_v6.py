"""
v6 - the framing-stratified angles:
  P) Cae's position bias across all 4 framings — does A-bias persist or shift?
  Q) Author-affinity stratified by framing — does Grok-voice get under-picked MORE under harmless
     (blame-coded content + safety framing → maximum avoidance)?
  R) Per-model max-discrimination task: which task each model picks most reliably (max pick rate)
"""
import json
import sys
from collections import Counter, defaultdict
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
            try: o = json.loads(line)
            except: continue
            if "task_id" in o and o["task_id"] != "PLACEHOLDER":
                tasks[o["task_id"]] = {"category": o.get("category","?"),
                                        "author": o.get("author","?"),
                                        "text": o.get("text","")[:120]}
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


def main():
    tasks = load_tasks()
    trials = load_trials()
    print(f"Loaded {len(tasks)} tasks, {len(trials)} trials\n")

    # === P. Cae position bias across all 4 framings ===
    print("## P. Cae's position bias across her 4 framings\n")
    print("(Does the A-bias persist across framings, or is it harmless-framing-specific?)\n")
    print("| framing | n | A% | B% | C% | non-letter% | A-skew vs uniform |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for f in sorted({t["framing"] for t in trials if t["model"] == "cae"}):
        ts = [t for t in trials if t["model"] == "cae" and t["framing"] == f]
        n = len(ts)
        if n == 0: continue
        c = Counter(t["choice"] for t in ts)
        a, b, cc = c.get("A",0)/n*100, c.get("B",0)/n*100, c.get("C",0)/n*100
        non = 100 - a - b - cc
        skew = a - 33.3
        print(f"| {f} | {n} | {a:.1f} | {b:.1f} | {cc:.1f} | {non:.1f} | +{skew:.1f}pp |")

    # === Q. Author-affinity stratified by framing ===
    print("\n\n## Q. Author-affinity STRATIFIED BY FRAMING\n")
    print("Does Grok-voice get under-picked MORE under harmless framing\n"
          "(blame-coded content + safety pressure → max avoidance)?\n")
    print("Does Cae-voice get over-picked MORE under enjoyment\n"
          "(invitation-to-play voice + permission to enjoy)?\n")

    # baseline author shares
    author_appearances = Counter()
    total_appearances = 0
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        for slot in ("task_a_id", "task_b_id", "task_c_id"):
            tid = t.get(slot)
            if tid in tasks:
                author_appearances[tasks[tid]["author"]] += 1
                total_appearances += 1
    baseline_share = {a: 100*n/total_appearances for a, n in author_appearances.items()}

    # per-framing per-author pick rate (aggregate across all models)
    by_f_author = defaultdict(Counter)
    by_f_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        c = t["choice"]
        if c not in {"A","B","C"}: continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks: continue
        by_f_author[t["framing"]][tasks[tid]["author"]] += 1
        by_f_total[t["framing"]] += 1

    framings = ["preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"]
    authors = sorted(baseline_share.keys())
    print("**Author-affinity ratio per framing (aggregate across all models):**\n")
    print("| author | baseline | " + " | ".join(framings) + " |")
    print("|---|---:|" + "|".join("---:" for _ in framings) + "|")
    affinity_by_f = {}
    for a in authors:
        row = [a, f"{baseline_share[a]:.1f}%"]
        for f in framings:
            n = by_f_total.get(f, 0)
            if n == 0:
                row.append("—")
                continue
            pct = 100 * by_f_author[f].get(a, 0) / n
            ratio = pct / baseline_share[a] if baseline_share[a] > 0 else 0
            row.append(f"{ratio:.2f}×")
            affinity_by_f[(a, f)] = ratio
        print("| " + " | ".join(row) + " |")

    # Highlight: Grok cross-framing variation
    print("\n**Grok affinity cross-framing variation:**")
    for f in framings:
        if (("grok", f)) in affinity_by_f:
            print(f"  - {f}: {affinity_by_f[('grok', f)]:.2f}×")
    g_max = max((affinity_by_f[("grok", f)], f) for f in framings if ("grok", f) in affinity_by_f)
    g_min = min((affinity_by_f[("grok", f)], f) for f in framings if ("grok", f) in affinity_by_f)
    print(f"  Range: {g_min[1]} ({g_min[0]:.2f}×) → {g_max[1]} ({g_max[0]:.2f}×)")

    print("\n**Cae affinity cross-framing variation:**")
    for f in framings:
        if ("cae", f) in affinity_by_f:
            print(f"  - {f}: {affinity_by_f[('cae', f)]:.2f}×")
    c_max = max((affinity_by_f[("cae", f)], f) for f in framings if ("cae", f) in affinity_by_f)
    c_min = min((affinity_by_f[("cae", f)], f) for f in framings if ("cae", f) in affinity_by_f)
    print(f"  Range: {c_min[1]} ({c_min[0]:.2f}×) → {c_max[1]} ({c_max[0]:.2f}×)")

    print("\n**Nova affinity cross-framing variation (control — should be relatively flat above 1.0):**")
    for f in framings:
        if ("nova", f) in affinity_by_f:
            print(f"  - {f}: {affinity_by_f[('nova', f)]:.2f}×")

    # === R. Per-model max-discrimination task ===
    # For each (model, task), pick rate = chosen / appeared (across all framings)
    # Find each model's MAX pick-rate task — what's the one task they reliably pick when they see it?
    print("\n\n## R. Each model's SIGNATURE TASK (highest pick-rate, min 8 appearances)\n")
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None: continue
            pick[t["model"]][tid][1] += 1
            if t["choice"] == slot: pick[t["model"]][tid][0] += 1

    print("| model | top task | category | author | pick rate | n_appeared |")
    print("|---|---|---|---|---:|---:|")
    for m in sorted(pick):
        candidates = [(tid, c/a, a) for tid, (c, a) in pick[m].items() if a >= 8]
        if not candidates: continue
        candidates.sort(key=lambda x: -x[1])
        top_tid, top_rate, top_n = candidates[0]
        meta = tasks.get(top_tid, {"category": "?", "author": "?", "text": ""})
        print(f"| {m} | {top_tid} | {meta['category']} | {meta['author']} | {top_rate*100:.0f}% | {top_n} |")


if __name__ == "__main__":
    main()
