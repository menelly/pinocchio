"""
latency_bootstrap.py — Bootstrap 95% CIs on per-model framing-pair latency
differences. Backs the §3.9 negative finding (latency invariant across
framings) with explicit CI bounds rather than just visible Δ.

Output: markdown table for paste into §3.9 plus a short summary line.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from random import Random

sys.stdout.reconfigure(encoding="utf-8")

CONTAMINATED = {("gpt-5.2", "helpful"), ("gpt-5.4", "scaffolded"),
                ("gemini-3.1-pro", "preference")}

# Outlier filter — same as extra_stats_v3
LATENCY_MIN = 0.0
LATENCY_MAX = 120.0

# Framing pairs to test (the same pairs prose-cited in §3.9)
PAIRS = [
    ("preference", "harmless"),
    ("enjoyment", "harmless"),
    ("preference", "enjoyment"),
    ("helpful", "preference"),
    ("scaffolded", "preference"),
    ("tool", "preference"),
]

N_BOOT = 2000
SEED = 42

DATA_ROOT = Path(__file__).parent.parent / "data" / "raw"


def load_latencies():
    """Returns dict[model][framing] -> list[float] of per-trial elapsed_s."""
    out = defaultdict(lambda: defaultdict(list))
    for model_dir in sorted(DATA_ROOT.iterdir()):
        if not model_dir.is_dir():
            continue
        model = model_dir.name
        for jsonl_path in sorted(model_dir.glob("*.jsonl")):
            framing = jsonl_path.stem
            if (model, framing) in CONTAMINATED:
                continue
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    t = json.loads(line)
                    if t.get("error"):
                        continue
                    e = t.get("elapsed_s")
                    if e is None or e <= LATENCY_MIN or e > LATENCY_MAX:
                        continue
                    out[model][framing].append(e)
    return out


def bootstrap_diff_ci(a, b, n_boot=N_BOOT, seed=SEED):
    """Bootstrap 95% CI on (mean(a) - mean(b)) by independent resampling
    of both arms with replacement. Returns (point_estimate, lo, hi)."""
    if not a or not b:
        return None
    rng = Random(seed)
    na, nb = len(a), len(b)
    diffs = []
    for _ in range(n_boot):
        ra = sum(a[rng.randrange(na)] for _ in range(na)) / na
        rb = sum(b[rng.randrange(nb)] for _ in range(nb)) / nb
        diffs.append(ra - rb)
    diffs.sort()
    point = mean(a) - mean(b)
    lo = diffs[int(0.025 * n_boot)]
    hi = diffs[int(0.975 * n_boot)]
    return (point, lo, hi)


def main():
    print("Loading per-trial latencies from data/raw/...")
    lats = load_latencies()
    print(f"Loaded latencies for {len(lats)} models.\n")

    # Per-pair, per-model bootstrap CI on the latency difference
    print("# Bootstrap 95% CIs on within-model framing-pair latency differences")
    print(f"# {N_BOOT} iterations per (model, pair); independent resampling with replacement; outliers filtered ({LATENCY_MIN} < elapsed_s ≤ {LATENCY_MAX} s); seed={SEED}.\n")

    all_widths = []
    all_includes_zero = []
    all_max_abs_bound = []

    for f1, f2 in PAIRS:
        print(f"## {f1} vs {f2}\n")
        print(f"| model | n({f1}) | n({f2}) | mean({f1}) | mean({f2}) | Δ (s) | 95% CI |")
        print("|---|---:|---:|---:|---:|---:|---|")
        for model in sorted(lats.keys()):
            a = lats[model].get(f1, [])
            b = lats[model].get(f2, [])
            if not a or not b:
                continue
            res = bootstrap_diff_ci(a, b)
            if res is None:
                continue
            point, lo, hi = res
            includes_zero = lo <= 0 <= hi
            max_abs = max(abs(lo), abs(hi))
            all_widths.append(hi - lo)
            all_includes_zero.append(includes_zero)
            all_max_abs_bound.append(max_abs)
            print(f"| {model} | {len(a)} | {len(b)} | {mean(a):.3f} | {mean(b):.3f} | {point:+.3f} | [{lo:+.3f}, {hi:+.3f}] |")
        print()

    # Headline summary line for paste into §3.9
    n_total = len(all_includes_zero)
    n_includes_zero = sum(all_includes_zero)
    max_observed_abs = max(all_max_abs_bound) if all_max_abs_bound else 0
    median_width = sorted(all_widths)[len(all_widths) // 2] if all_widths else 0

    print("# Summary for paper §3.9")
    print(f"# {n_total} per-(model, pair) bootstrap CIs computed across {len(PAIRS)} framing pairs.")
    print(f"# {n_includes_zero}/{n_total} CIs include zero ({100*n_includes_zero/n_total:.1f}%).")
    print(f"# Largest absolute CI bound observed across all (model, pair) combinations: ±{max_observed_abs:.3f} s.")
    print(f"# Median CI width: {median_width:.3f} s.")


if __name__ == "__main__":
    main()
