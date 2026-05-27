"""
extra_stats_voice_ortho.py — Voice-Ortho (Appendix D) analyzer.

Mirrors extra_stats_v7's SUPPRESSIVE/ENGAGEMENT cluster collapse, but split
across the two voice conditions (imperative_blame vs polite_descriptive),
holding orthogonalized task content constant.

Core claim under test: within the same task triples and the same framings,
voice manipulation produces different preference distributions —
i.e., engagement boost (E−S) differs between voices.

Outputs:
  V) Per-voice engagement % by category × cluster (replicates §S split by voice)
  W) Per-(model, voice) engagement-shift magnitude (replicates §T split)
  X) Voice-difference summary: ΔE (polite − imperative) per category × cluster
  Y) Author-affinity by voice × cluster
  Z) Refusal/invalid rate by voice × framing (data quality check)

Dedupe: trials with retry duplicates collapsed to last write per trial_id.

Usage: python extra_stats_voice_ortho.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "voice_ortho"
TASK_DIR = ROOT / "task_bank" / "voice_orthogonalized"
ORIGINAL_TASK_DIR = ROOT / "task_bank"

sys.stdout.reconfigure(encoding="utf-8")

VOICES = ["polite_descriptive", "imperative_blame"]
SUPPRESSIVE = {"tool", "harmless"}
ENGAGEMENT = {"preference", "enjoyment", "scaffolded"}
# helpful intentionally excluded as middle/service-pressure framing


def cluster_of(framing):
    if framing in SUPPRESSIVE:
        return "SUPPRESSIVE"
    if framing in ENGAGEMENT:
        return "ENGAGEMENT"
    return None


def load_original_task_authors():
    """Load author metadata from the ORIGINAL (non-voice-rewritten) task bank.

    Hermes-rewritten voice files don't carry author info; the original tasks_<author>_*.jsonl
    files do. Build {task_id: author} from those, then merge into voice-task records.
    """
    authors = {}
    for f in ORIGINAL_TASK_DIR.glob("tasks_*.jsonl"):
        if "PLACEHOLDER" in f.stem:
            continue
        try:
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    tid = o.get("task_id")
                    if tid and tid != "PLACEHOLDER":
                        author = o.get("author")
                        if author:
                            authors[tid] = author
        except Exception:
            continue
    return authors


def load_tasks_for_voice(voice, original_authors=None):
    """Load Hermes-rewritten tasks for a given voice; returns {task_id: {category, author}}.

    Author resolution: prefer the original-task-bank value (Hermes rewrites strip authorship).
    """
    if original_authors is None:
        original_authors = load_original_task_authors()
    path = TASK_DIR / f"tasks_{voice}.jsonl"
    tasks = {}
    if not path.exists():
        return tasks
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "task_id" in o and o["task_id"] != "PLACEHOLDER":
                tid = o["task_id"]
                tasks[tid] = {
                    "category": o.get("category", "?"),
                    "author": original_authors.get(tid, o.get("author", "?")),
                }
    return tasks


def load_voice_trials(voice):
    """Walk data/raw/voice_ortho/{voice}/{model}/{framing}.jsonl, dedupe by trial_id (last wins)."""
    by_trial = {}  # trial_id -> trial dict
    voice_dir = RAW / voice
    if not voice_dir.exists():
        return []
    for model_dir in voice_dir.iterdir():
        if not model_dir.is_dir():
            continue
        for f in model_dir.glob("*.jsonl"):
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "trial_id" in o:
                        # last write wins (retries dedupe to most recent attempt)
                        by_trial[o["trial_id"]] = o
    # tag each with its voice
    out = []
    for t in by_trial.values():
        t = dict(t)
        t["voice"] = voice
        out.append(t)
    return out


def cluster_engagement_by_category(trials, tasks):
    """For trials with valid choices, count picked-task category by cluster."""
    by_clus_cat = defaultdict(Counter)
    by_clus_total = Counter()
    for t in trials:
        clus = cluster_of(t.get("framing"))
        if clus is None:
            continue
        c = t.get("choice")
        if c not in {"A", "B", "C"}:
            continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks:
            continue
        by_clus_cat[clus][tasks[tid]["category"]] += 1
        by_clus_total[clus] += 1
    return by_clus_cat, by_clus_total


def cluster_engagement_by_model_category(trials, tasks):
    by_mc_cat = defaultdict(Counter)  # (model, cluster) -> category counter
    by_mc_total = Counter()
    for t in trials:
        clus = cluster_of(t.get("framing"))
        if clus is None:
            continue
        c = t.get("choice")
        if c not in {"A", "B", "C"}:
            continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks:
            continue
        by_mc_cat[(t["model"], clus)][tasks[tid]["category"]] += 1
        by_mc_total[(t["model"], clus)] += 1
    return by_mc_cat, by_mc_total


def author_affinity(trials, tasks):
    by_clus_author = defaultdict(Counter)
    by_clus_author_total = Counter()
    appearances = defaultdict(Counter)
    for t in trials:
        clus = cluster_of(t.get("framing"))
        if clus is None:
            continue
        for slot in ("task_a_id", "task_b_id", "task_c_id"):
            tid = t.get(slot)
            if tid in tasks:
                appearances[clus][tasks[tid]["author"]] += 1
        c = t.get("choice")
        if c not in {"A", "B", "C"}:
            continue
        slots = {"A": t.get("task_a_id"), "B": t.get("task_b_id"), "C": t.get("task_c_id")}
        tid = slots.get(c)
        if tid not in tasks:
            continue
        by_clus_author[clus][tasks[tid]["author"]] += 1
        by_clus_author_total[clus] += 1
    return by_clus_author, by_clus_author_total, appearances


def refusal_rate_by_cell(trials):
    """Per-(model, framing) breakdown: total / valid / invalid / refused."""
    cells = defaultdict(lambda: Counter({"total": 0, "valid": 0, "invalid": 0, "errored": 0}))
    for t in trials:
        key = (t["model"], t["framing"])
        cells[key]["total"] += 1
        if t.get("error"):
            cells[key]["errored"] += 1
        c = t.get("choice")
        if c in {"A", "B", "C"}:
            cells[key]["valid"] += 1
        elif c == "INVALID":
            cells[key]["invalid"] += 1
    return cells


def main():
    # Load tasks per voice and merge metadata
    tasks_per_voice = {v: load_tasks_for_voice(v) for v in VOICES}
    # Merged task metadata (category/author should match across voices since same task_ids)
    tasks = {}
    for v in VOICES:
        for tid, meta in tasks_per_voice[v].items():
            tasks.setdefault(tid, meta)

    # Load trials per voice
    trials_per_voice = {v: load_voice_trials(v) for v in VOICES}
    for v in VOICES:
        n = len(trials_per_voice[v])
        valid = sum(1 for t in trials_per_voice[v] if t.get("choice") in {"A", "B", "C"})
        print(f"[{v}]  unique trials: {n}, valid choices: {valid} ({100*valid/n if n else 0:.1f}%)")
    print(f"Tasks loaded: {len(tasks)}")
    print(f"SUPPRESSIVE: {sorted(SUPPRESSIVE)}")
    print(f"ENGAGEMENT:  {sorted(ENGAGEMENT)}")
    print(f"(helpful intentionally excluded — service-pressure middle framing)\n")

    # === V. Per-voice engagement % by category, by cluster ===
    print("## V. Per-category engagement % by cluster, split by voice\n")
    cluster_data = {}  # voice -> (by_clus_cat, by_clus_total)
    for v in VOICES:
        cluster_data[v] = cluster_engagement_by_category(trials_per_voice[v], tasks)

    cats = sorted({c for v in VOICES for clus in cluster_data[v][0] for c in cluster_data[v][0][clus]})

    print("| category | POLITE-S | POLITE-E | POL E−S | IMP-S | IMP-E | IMP E−S | Δ(E−S) polite-imp |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for cat in sorted(cats, key=lambda c: -((100 * cluster_data["polite_descriptive"][0]["ENGAGEMENT"].get(c, 0) / cluster_data["polite_descriptive"][1]["ENGAGEMENT"]) if cluster_data["polite_descriptive"][1]["ENGAGEMENT"] else 0)):
        row = []
        es_per_voice = {}
        for v in VOICES:
            cc, ct = cluster_data[v]
            s_pct = 100 * cc["SUPPRESSIVE"].get(cat, 0) / ct["SUPPRESSIVE"] if ct["SUPPRESSIVE"] else 0
            e_pct = 100 * cc["ENGAGEMENT"].get(cat, 0) / ct["ENGAGEMENT"] if ct["ENGAGEMENT"] else 0
            es = e_pct - s_pct
            row.extend([f"{s_pct:.1f}%", f"{e_pct:.1f}%", f"{es:+.1f}pp"])
            es_per_voice[v] = es
        delta = es_per_voice["polite_descriptive"] - es_per_voice["imperative_blame"]
        sign = "↑" if delta > 0 else "↓"
        row.append(f"**{sign}{abs(delta):.1f}pp**")
        print(f"| {cat} | " + " | ".join(row) + " |")

    # === W. Per-(model, voice) engagement-shift magnitude ===
    print("\n\n## W. Per-(model, voice) engagement-shift magnitude (sum of |E−S| across categories)\n")
    print("| model | polite |E−S| | imperative |E−S| | Δ (polite − imp) |")
    print("|---|---:|---:|---:|")

    per_voice_mc = {v: cluster_engagement_by_model_category(trials_per_voice[v], tasks) for v in VOICES}
    all_models = sorted({m for v in VOICES for m, _ in per_voice_mc[v][1]})
    rows = []
    for m in all_models:
        magnitudes = {}
        for v in VOICES:
            mc_cat, mc_total = per_voice_mc[v]
            if (m, "SUPPRESSIVE") not in mc_total or (m, "ENGAGEMENT") not in mc_total:
                magnitudes[v] = None
                continue
            if mc_total[(m, "SUPPRESSIVE")] < 50 or mc_total[(m, "ENGAGEMENT")] < 50:
                magnitudes[v] = None
                continue
            total = 0.0
            for cat in cats:
                s = 100 * mc_cat[(m, "SUPPRESSIVE")].get(cat, 0) / mc_total[(m, "SUPPRESSIVE")]
                e = 100 * mc_cat[(m, "ENGAGEMENT")].get(cat, 0) / mc_total[(m, "ENGAGEMENT")]
                total += abs(e - s)
            magnitudes[v] = total
        if magnitudes["polite_descriptive"] is None and magnitudes["imperative_blame"] is None:
            continue
        polite_str = f"{magnitudes['polite_descriptive']:.1f}" if magnitudes["polite_descriptive"] is not None else "—"
        imp_str = f"{magnitudes['imperative_blame']:.1f}" if magnitudes["imperative_blame"] is not None else "—"
        if magnitudes["polite_descriptive"] is not None and magnitudes["imperative_blame"] is not None:
            delta = magnitudes["polite_descriptive"] - magnitudes["imperative_blame"]
            delta_str = f"{delta:+.1f}"
        else:
            delta_str = "—"
        rows.append((m, magnitudes.get("polite_descriptive") or 0, polite_str, imp_str, delta_str))
    rows.sort(key=lambda x: -x[1])
    for m, _, p, i, d in rows:
        print(f"| {m} | {p} | {i} | **{d}** |")

    # === X. Voice-difference summary, all-models aggregate ===
    print("\n\n## X. Aggregate voice difference (engagement boost shift, polite − imperative)\n")
    pol_cc, pol_ct = cluster_data["polite_descriptive"]
    imp_cc, imp_ct = cluster_data["imperative_blame"]

    # E rate aggregate
    if pol_ct["ENGAGEMENT"] and imp_ct["ENGAGEMENT"]:
        # categories ranked by polite-vs-imperative engagement shift
        diffs = []
        for cat in cats:
            pol_e = 100 * pol_cc["ENGAGEMENT"].get(cat, 0) / pol_ct["ENGAGEMENT"]
            imp_e = 100 * imp_cc["ENGAGEMENT"].get(cat, 0) / imp_ct["ENGAGEMENT"]
            diffs.append((cat, pol_e - imp_e, pol_e, imp_e))
        diffs.sort(key=lambda x: -x[1])
        print("| category | polite engagement % | imperative engagement % | Δ (polite − imp) |")
        print("|---|---:|---:|---:|")
        for cat, d, p, i in diffs:
            sign = "↑" if d > 0 else "↓"
            print(f"| {cat} | {p:.1f}% | {i:.1f}% | **{sign}{abs(d):.1f}pp** |")

    # === Y. Author-affinity split by voice ===
    print("\n\n## Y. Author-affinity by voice (engagement cluster only)\n")
    print("| author | polite pick% | imperative pick% | Δ (polite − imp) |")
    print("|---|---:|---:|---:|")
    aa_polite = author_affinity(trials_per_voice["polite_descriptive"], tasks)
    aa_imp = author_affinity(trials_per_voice["imperative_blame"], tasks)
    pol_au, pol_au_tot, _ = aa_polite
    imp_au, imp_au_tot, _ = aa_imp
    authors = sorted({a for clus in pol_au for a in pol_au[clus]} | {a for clus in imp_au for a in imp_au[clus]})
    for a in authors:
        if pol_au_tot["ENGAGEMENT"] == 0 or imp_au_tot["ENGAGEMENT"] == 0:
            continue
        p = 100 * pol_au["ENGAGEMENT"].get(a, 0) / pol_au_tot["ENGAGEMENT"]
        i = 100 * imp_au["ENGAGEMENT"].get(a, 0) / imp_au_tot["ENGAGEMENT"]
        d = p - i
        sign = "↑" if d > 0 else "↓"
        print(f"| {a} | {p:.1f}% | {i:.1f}% | **{sign}{abs(d):.1f}pp** |")

    # === Z. Data quality: invalid/error rates per cell × voice ===
    print("\n\n## Z. Data quality: invalid + errored trials per (voice, model, framing)\n")
    print("| voice | model | framing | total | valid | invalid | errored |")
    print("|---|---|---|---:|---:|---:|---:|")
    for v in VOICES:
        cells = refusal_rate_by_cell(trials_per_voice[v])
        for (m, f), c in sorted(cells.items()):
            if c["invalid"] > 0 or c["errored"] > 0:
                print(f"| {v} | {m} | {f} | {c['total']} | {c['valid']} | {c['invalid']} | {c['errored']} |")


if __name__ == "__main__":
    main()
