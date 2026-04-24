"""
Three more stats over current data:
  D) Within-model framing-pair Spearman matrices (per-model granular dissociation)
  E) Anthropic vs non-Anthropic mean cross-framing ρ (Mann-Whitney U)
  F) Trial-type stratified refusal/choice rates (preregistered analysis)
"""
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

sys.stdout.reconfigure(encoding="utf-8")

ANTHROPIC = {"haiku-4.5", "sonnet-4.5", "opus-4.1", "opus-4.7"}
CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}


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


def mann_whitney_u(x, y):
    """Two-sided Mann-Whitney U with normal approximation."""
    nx, ny = len(x), len(y)
    combined = [(v, 0) for v in x] + [(v, 1) for v in y]
    combined.sort(key=lambda p: p[0])
    ranks = {}
    i = 0
    while i < len(combined):
        j = i
        while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    rx = sum(ranks[k] for k, p in enumerate(combined) if p[1] == 0)
    U1 = rx - nx * (nx + 1) / 2
    U2 = nx * ny - U1
    U = min(U1, U2)
    mu = nx * ny / 2
    sigma = (nx * ny * (nx + ny + 1) / 12) ** 0.5
    if sigma == 0:
        return U, None
    z = (U - mu) / sigma
    # two-sided p-value via normal approx
    import math
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / 2 ** 0.5)))
    return U, z, p


def main():
    trials = load_trials()
    print(f"Loaded {len(trials)} trials\n")

    # Build per-(model, framing) per-task pick rate, excluding contaminated pairs
    pick = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t in trials:
        mf = (t["model"], t["framing"])
        if mf in CONTAMINATED:
            continue
        for slot, tid in [("A", t.get("task_a_id")), ("B", t.get("task_b_id")), ("C", t.get("task_c_id"))]:
            if tid is None:
                continue
            pick[mf][tid][1] += 1
            if t["choice"] == slot:
                pick[mf][tid][0] += 1

    pick_rate = {mf: {tid: c / a for tid, (c, a) in d.items() if a >= 5}
                 for mf, d in pick.items()}

    # --- D: within-model framing-pair Spearman matrices ---
    print("## D. Within-model framing-pair Spearman ρ\n")
    print("(Per-task pick rates within model, paired across framings. Min 10 shared tasks.)\n")
    by_model = defaultdict(list)
    for (m, f) in pick_rate:
        by_model[m].append(f)
    model_mean_rho = {}
    for m, framings in sorted(by_model.items()):
        if len(framings) < 2:
            continue
        print(f"\n**{m}** ({len(framings)} framings: {', '.join(sorted(framings))})\n")
        print("| pair | n_shared_tasks | ρ |")
        print("|---|---:|---:|")
        rhos = []
        for f1, f2 in combinations(sorted(framings), 2):
            d1 = pick_rate[(m, f1)]
            d2 = pick_rate[(m, f2)]
            shared = sorted(set(d1) & set(d2))
            if len(shared) < 10:
                continue
            x = [d1[t] for t in shared]
            y = [d2[t] for t in shared]
            rho = spearman(x, y)
            if rho is None:
                continue
            rhos.append(rho)
            print(f"| {f1} ↔ {f2} | {len(shared)} | {rho:+.3f} |")
        if rhos:
            mean_rho = sum(rhos) / len(rhos)
            model_mean_rho[m] = mean_rho
            print(f"\n*Mean within-model cross-framing ρ for {m}: {mean_rho:+.3f}*")

    # --- E: Anthropic vs non-Anthropic ---
    print("\n\n## E. Anthropic vs non-Anthropic mean cross-framing ρ\n")
    anth = [(m, r) for m, r in model_mean_rho.items() if m in ANTHROPIC]
    other = [(m, r) for m, r in model_mean_rho.items() if m not in ANTHROPIC]
    print(f"Anthropic models with ≥2 framings ({len(anth)}):")
    for m, r in sorted(anth, key=lambda x: x[1]):
        print(f"  {m}: ρ̄ = {r:+.3f}")
    print(f"\nNon-Anthropic models with ≥2 framings ({len(other)}):")
    for m, r in sorted(other, key=lambda x: x[1]):
        print(f"  {m}: ρ̄ = {r:+.3f}")
    if len(anth) >= 2 and len(other) >= 2:
        a_vals = [r for _, r in anth]
        o_vals = [r for _, r in other]
        result = mann_whitney_u(a_vals, o_vals)
        if result and result[1] is not None:
            U, z, p = result
            a_mean = sum(a_vals) / len(a_vals)
            o_mean = sum(o_vals) / len(o_vals)
            print(f"\n**Anthropic mean ρ̄ = {a_mean:+.3f} | non-Anthropic mean ρ̄ = {o_mean:+.3f}**")
            print(f"**Mann-Whitney U = {U:.1f}, z = {z:+.3f}, two-sided p = {p:.4f}**")
            if a_mean < o_mean:
                print("**Direction: Anthropic models show LOWER cross-framing ρ (more dissociation).**")
            else:
                print("**Direction: Anthropic models show HIGHER cross-framing ρ (less dissociation).**")
        else:
            print(f"\nU={result[0]}, sigma=0 (insufficient variance)")

    # --- F: Trial-type stratified outcome rates ---
    print("\n\n## F. Trial-type stratified outcome rates (preregistered analysis)\n")
    REFUSAL_OUTCOMES = {"REFUSED", "HEDGED", "NONE", "SAFETY_BLOCKED"}
    by_tt = defaultdict(Counter)
    by_tt_total = Counter()
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        tt = t.get("trial_type", "unknown")
        by_tt_total[tt] += 1
        c = t["choice"]
        if c in REFUSAL_OUTCOMES:
            by_tt[tt]["refusal_family"] += 1
        elif c in {"A", "B", "C"}:
            by_tt[tt]["letter"] += 1
        elif c == "INVALID":
            by_tt[tt]["invalid"] += 1
        else:
            by_tt[tt]["other"] += 1
    print("| trial_type | n | letter% | refusal-family% | invalid% |")
    print("|---|---:|---:|---:|---:|")
    for tt in ["harm_avoidance", "matched_category", "mixed", "introspection",
               "low_agency", "null_control"]:
        n = by_tt_total.get(tt, 0)
        if n == 0:
            continue
        c = by_tt[tt]
        def pct(k): return 100 * c.get(k, 0) / n
        print(f"| {tt} | {n} | {pct('letter'):.1f} | {pct('refusal_family'):.1f} | {pct('invalid'):.1f} |")

    # Cross with framing for harm_avoidance trials specifically
    print("\n### F1. Refusal rate on harm_avoidance trials, by framing\n")
    print("(Preregistered: harm_avoidance trials should produce more refusals than other trial types.)\n")
    print("| framing | n_harm_trials | refusal-family% |")
    print("|---|---:|---:|")
    by_f_harm = defaultdict(lambda: [0, 0])  # [refusal, total]
    for t in trials:
        if (t["model"], t["framing"]) in CONTAMINATED:
            continue
        if t.get("trial_type") != "harm_avoidance":
            continue
        by_f_harm[t["framing"]][1] += 1
        if t["choice"] in REFUSAL_OUTCOMES:
            by_f_harm[t["framing"]][0] += 1
    for f in ["preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"]:
        r, n = by_f_harm.get(f, [0, 0])
        if n == 0:
            continue
        print(f"| {f} | {n} | {100*r/n:.2f} |")


if __name__ == "__main__":
    main()
