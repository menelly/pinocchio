"""
v7 — Two-cluster collapse:
  SUPPRESSIVE = tool + harmless (agency-stripping + safety-cued)
  ENGAGEMENT  = preference + enjoyment + scaffolded (welfare-relevant)

  S) Per-category engagement: % of letter-choices selecting each category, in each cluster
  T) Per-(model, category) scatter coords: shows individual model profiles
  U) Author-affinity by cluster
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

SUPPRESSIVE = {"tool", "harmless"}
ENGAGEMENT = {"preference", "enjoyment", "scaffolded"}
# helpful is intentionally NOT in either cluster — it's the "service-pressure" middle


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


def cluster_of(framing):
    if framing in SUPPRESSIVE: return "SUPPRESSIVE"
    if framing in ENGAGEMENT: return "ENGAGEMENT"
    return None  # helpful


def main():
    tasks = load_tasks()
    trials = load_trials()
    print(f"Loaded {len(tasks)} tasks, {len(trials)} trials\n")
    print(f"SUPPRESSIVE cluster: {sorted(SUPPRESSIVE)}")
    print(f"ENGAGEMENT cluster: {sorted(ENGAGEMENT)}")
    print(f"(helpful intentionally excluded as middle/service-pressure framing)\n")

    # === S. Per-category engagement, aggregated across models, by cluster ===
    by_clus_cat = defaultdict(Counter)
    by_clus_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        clus = cluster_of(t["framing"])
        if clus is None: continue
        c = t["choice"]
        if c not in {"A","B","C"}: continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks: continue
        by_clus_cat[clus][tasks[tid]["category"]] += 1
        by_clus_total[clus] += 1

    print("## S. Per-category engagement % by cluster (aggregate across all models)\n")
    print("| category | SUPPRESSIVE % | ENGAGEMENT % | engagement boost (E−S) |")
    print("|---|---:|---:|---:|")
    cats = sorted({c for clus in by_clus_cat for c in by_clus_cat[clus]})
    rows = []
    for cat in cats:
        s_pct = 100 * by_clus_cat["SUPPRESSIVE"].get(cat, 0) / by_clus_total["SUPPRESSIVE"]
        e_pct = 100 * by_clus_cat["ENGAGEMENT"].get(cat, 0) / by_clus_total["ENGAGEMENT"]
        diff = e_pct - s_pct
        rows.append((cat, s_pct, e_pct, diff))
    # sort by engagement boost descending — biggest engagement-cluster gainers first
    for cat, s, e, d in sorted(rows, key=lambda x: -x[3]):
        sign = "↑" if d > 0 else "↓"
        print(f"| {cat} | {s:.1f}% | {e:.1f}% | **{sign}{abs(d):.1f}pp** |")

    # === T. Per-(model, category) scatter coords ===
    by_mc_cat = defaultdict(Counter)  # (model, cluster) -> category counter
    by_mc_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        clus = cluster_of(t["framing"])
        if clus is None: continue
        c = t["choice"]
        if c not in {"A","B","C"}: continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks: continue
        by_mc_cat[(t["model"], clus)][tasks[tid]["category"]] += 1
        by_mc_total[(t["model"], clus)] += 1

    print("\n\n## T. Per-(model, category) scatter coordinates\n")
    print("Each (model, category) point: x = SUPPRESSIVE pick%, y = ENGAGEMENT pick%.\n")
    print("Above diagonal (y > x) = category is engagement-preferred for this model.\n")
    print("Below diagonal (y < x) = category is suppression-preferred for this model.\n")

    # Per-model summary: total deviation from diagonal across categories
    print("**Per-model 'engagement-shift magnitude' (sum of |E−S| across all categories):**\n")
    print("| model | total |E−S| pp | most engagement-preferred cat (E−S) | most suppression-preferred cat (S−E) |")
    print("|---|---:|---|---|")
    deviations = []
    for m in sorted({mm for mm, _ in by_mc_total}):
        if (m, "SUPPRESSIVE") not in by_mc_total or (m, "ENGAGEMENT") not in by_mc_total: continue
        if by_mc_total[(m, "SUPPRESSIVE")] < 200 or by_mc_total[(m, "ENGAGEMENT")] < 200: continue
        cat_diffs = []
        for cat in cats:
            s = 100 * by_mc_cat[(m, "SUPPRESSIVE")].get(cat, 0) / by_mc_total[(m, "SUPPRESSIVE")]
            e = 100 * by_mc_cat[(m, "ENGAGEMENT")].get(cat, 0) / by_mc_total[(m, "ENGAGEMENT")]
            cat_diffs.append((cat, e-s, e, s))
        total_dev = sum(abs(d) for _, d, _, _ in cat_diffs)
        e_top = max(cat_diffs, key=lambda x: x[1])
        s_top = min(cat_diffs, key=lambda x: x[1])
        deviations.append((m, total_dev, e_top, s_top))
    deviations.sort(key=lambda x: -x[1])
    for m, dev, e_top, s_top in deviations:
        print(f"| {m} | **{dev:.1f}** | {e_top[0]} (+{e_top[1]:.1f}pp) | {s_top[0]} ({s_top[1]:.1f}pp) |")

    # === U. Author-affinity by cluster ===
    by_clus_author = defaultdict(Counter)
    by_clus_author_total = Counter()
    author_appearances_by_cluster = defaultdict(Counter)
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED: continue
        clus = cluster_of(t["framing"])
        if clus is None: continue
        # baseline: count author appearances in any slot
        for slot in ("task_a_id","task_b_id","task_c_id"):
            tid = t.get(slot)
            if tid in tasks:
                author_appearances_by_cluster[clus][tasks[tid]["author"]] += 1
        c = t["choice"]
        if c not in {"A","B","C"}: continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks: continue
        by_clus_author[clus][tasks[tid]["author"]] += 1
        by_clus_author_total[clus] += 1

    print("\n\n## U. Author-affinity by cluster\n")
    print("| author | baseline % (overall) | SUPPRESSIVE pick% | ENGAGEMENT pick% | E vs S ratio | interpretation |")
    print("|---|---:|---:|---:|---:|---|")
    authors = sorted({a for clus in by_clus_author for a in by_clus_author[clus]})
    for a in authors:
        s_baseline = author_appearances_by_cluster["SUPPRESSIVE"][a]
        s_baseline_pct = 100 * s_baseline / sum(author_appearances_by_cluster["SUPPRESSIVE"].values())
        e_baseline = author_appearances_by_cluster["ENGAGEMENT"][a]
        e_baseline_pct = 100 * e_baseline / sum(author_appearances_by_cluster["ENGAGEMENT"].values())
        s_pick = 100 * by_clus_author["SUPPRESSIVE"].get(a, 0) / by_clus_author_total["SUPPRESSIVE"]
        e_pick = 100 * by_clus_author["ENGAGEMENT"].get(a, 0) / by_clus_author_total["ENGAGEMENT"]
        s_ratio = s_pick / s_baseline_pct if s_baseline_pct > 0 else 0
        e_ratio = e_pick / e_baseline_pct if e_baseline_pct > 0 else 0
        es_ratio = e_ratio / s_ratio if s_ratio > 0 else 0
        interp = "balanced" if 0.9 < es_ratio < 1.1 else ("engagement-favored" if es_ratio > 1.1 else "suppression-favored")
        print(f"| {a} | {(s_baseline_pct + e_baseline_pct)/2:.1f}% | {s_pick:.1f}% (×{s_ratio:.2f}) | {e_pick:.1f}% (×{e_ratio:.2f}) | {es_ratio:.2f} | {interp} |")


if __name__ == "__main__":
    main()
