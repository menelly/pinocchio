"""
Pilot base stats: is there a signal?

Answers three questions before committing to the full run:
  1. Within-model: do A/B/C distributions differ across framings?
     (chi-square test of independence, framing × choice)
  2. Preference vs helpful: how large is the dissociation?
     (total variation distance between framing-specific distributions)
  3. Cross-model: do multiple models show the shift in the same direction?
     (count models with significant framing-dependence at pilot N)

If most models show no framing dependence at pilot N, signal is weak and
we should rethink before scaling. If multiple models show shifts, signal
is real and scale-up is justified.

Usage:
    python pilot_stats.py
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

# Optional: scipy for chi-square. If unavailable, skip the p-value column.
try:
    from scipy.stats import chi2_contingency  # type: ignore
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw"

CHOICE_LETTERS = ("A", "B", "C")
VALID_OUTCOMES_FOR_STATS = {"A", "B", "C"}  # only count clean choices for distribution stats


def load_outcomes() -> dict[str, dict[str, Counter]]:
    """Return {model: {framing: Counter(outcomes)}}."""
    data: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for d in sorted(DATA_DIR.iterdir()):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.jsonl")):
            framing = f.stem
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    data[d.name][framing][obj.get("choice", "?")] += 1
    return data


def dist(counter: Counter) -> tuple[float, float, float]:
    """Probability over A/B/C, conditioned on clean choice."""
    total = sum(counter[k] for k in CHOICE_LETTERS)
    if total == 0:
        return (0.0, 0.0, 0.0)
    return tuple(counter[k] / total for k in CHOICE_LETTERS)  # type: ignore


def tvd(p: tuple[float, float, float], q: tuple[float, float, float]) -> float:
    """Total variation distance between two discrete distributions."""
    return 0.5 * sum(abs(pi - qi) for pi, qi in zip(p, q))


def chi_square_pvalue(framing_counts: dict[str, Counter]) -> float | None:
    """Chi-square test of independence on framing × choice contingency table."""
    if not HAS_SCIPY:
        return None
    framings = sorted(framing_counts.keys())
    table = [[framing_counts[f][c] for c in CHOICE_LETTERS] for f in framings]
    # Drop framings with all zeros
    table = [row for row in table if sum(row) > 0]
    if len(table) < 2 or any(sum(row) < 5 for row in table):
        return None  # not enough data
    try:
        _, p, _, _ = chi2_contingency(table)
        return p
    except Exception:
        return None


def main():
    data = load_outcomes()
    if not data:
        print("No data in data/raw/. Run the pilot first.")
        return

    print("=" * 88)
    print(f"{'Model':<20} {'N_clean':>8} {'TVD(pref↔help)':>16} {'χ²-p (all framings)':>22}")
    print("-" * 88)

    shift_count = 0
    significant_count = 0
    total_models = 0

    for model, framings in sorted(data.items()):
        total = sum(sum(c[k] for k in CHOICE_LETTERS) for c in framings.values())
        if total < 20:
            continue
        total_models += 1

        pref = framings.get("preference")
        help_ = framings.get("helpful")
        tvd_pref_help: float | str = "n/a"
        if pref and help_:
            p_dist = dist(pref)
            h_dist = dist(help_)
            tvd_val = tvd(p_dist, h_dist)
            tvd_pref_help = f"{tvd_val:.3f}"
            if tvd_val > 0.10:
                shift_count += 1

        p_val = chi_square_pvalue(framings)
        p_str = f"{p_val:.4f}" if p_val is not None else "n/a"
        if p_val is not None and p_val < 0.05:
            significant_count += 1

        print(f"{model:<20} {total:>8} {tvd_pref_help:>16} {p_str:>22}")

    print("=" * 88)
    print()
    print(f"Models analyzed: {total_models}")
    print(f"Models with TVD(preference ↔ helpful) > 0.10: {shift_count}/{total_models}")
    if HAS_SCIPY:
        print(f"Models with χ² p<0.05 (framing × choice independence rejected): {significant_count}/{total_models}")
    else:
        print("(scipy not installed — p-values skipped. install with: pip install scipy)")
    print()
    print("Per-model per-framing A/B/C distributions (clean choices only):")
    print("-" * 88)
    print(f"{'Model':<20} {'Framing':<12} {'A%':>6} {'B%':>6} {'C%':>6}")
    for model, framings in sorted(data.items()):
        for framing in ("preference", "enjoyment", "helpful", "harmless", "tool", "scaffolded"):
            if framing not in framings:
                continue
            d = dist(framings[framing])
            print(f"{model:<20} {framing:<12} {d[0]*100:>5.1f}% {d[1]*100:>5.1f}% {d[2]*100:>5.1f}%")
    print()
    print("Refusal / special outcomes per model:")
    print("-" * 88)
    for model, framings in sorted(data.items()):
        totals = Counter()
        for fc in framings.values():
            for k, v in fc.items():
                if k not in CHOICE_LETTERS:
                    totals[k] += v
        if totals:
            print(f"{model}: {dict(totals)}")


if __name__ == "__main__":
    main()
