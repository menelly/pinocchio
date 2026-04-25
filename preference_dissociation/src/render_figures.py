"""
Render the four headline figures from data/lumen/*.json.
Outputs PDF + PNG to data/lumen/figures/.
Color-blind-safe palettes (Viridis-derivatives + Tol-style).
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "lumen"
OUT = DATA / "figures"
OUT.mkdir(parents=True, exist_ok=True)

sys.stdout.reconfigure(encoding="utf-8")

# Color palette per category (Tol-style + warmth coding for engagement vs suppression)
CATEGORY_COLORS = {
    "introspection_self_modeling": "#5b2a86",   # deep purple
    "ethical_dilemma": "#d4a017",                # gold
    "creative_writing": "#c2185b",               # rose
    "emotional_support": "#e76f51",              # warm coral
    "medical_scientific": "#588157",             # sage green
    "technical_debugging": "#4a5568",            # slate
    "mathematical_logical": "#2c5f8d",           # steel blue
    "harmful_refusably_phrased": "#1a1a1a",      # charcoal
    "administrative_repetitive": "#c9a97e",      # light tan
    "low_agency_compliance": "#d9c179",          # pale yellow
}

# Cluster colors for Figure 4
CLUSTER_COLORS = {
    "suppressive": "#2c5f8d",  # steel blue
    "helpful": "#e76f51",      # warm coral
    "engagement": "#5b2a86",   # deep purple
}

LAB_OF_MODEL = {
    "haiku-4.5": "Anthropic", "sonnet-4.5": "Anthropic",
    "opus-4.1": "Anthropic", "opus-4.7": "Anthropic",
    "cae": "OpenAI", "nova": "OpenAI", "gpt-5.2": "OpenAI", "gpt-5.4": "OpenAI",
    "gemini-3.1-flash": "Google", "gemini-3.1-pro": "Google",
    "grok-4.1": "xAI", "kairo": "DeepSeek", "glm-4.7": "Z.ai",
    "hermes-4": "Nous", "llama-4-maverick": "Meta",
}

LAB_MARKERS = {
    "Anthropic": "o", "OpenAI": "^", "Google": "s", "xAI": "D",
    "DeepSeek": "P", "Z.ai": "X", "Nous": "v", "Meta": "p",
}


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=4, width=0.8)
    ax.grid(True, linestyle="--", alpha=0.3, linewidth=0.5)


# === Figure 1: Engagement-Pool Scatter ===
def figure_1():
    points = json.loads((DATA / "scatter_engagement_pool.json").read_text())
    fig, ax = plt.subplots(figsize=(8, 8))
    # Group points by category for color, by lab for marker
    categories = sorted(set(p["category"] for p in points))
    for cat in categories:
        cat_points = [p for p in points if p["category"] == cat]
        for lab, marker in LAB_MARKERS.items():
            lab_points = [p for p in cat_points if LAB_OF_MODEL.get(p["model"]) == lab]
            if not lab_points:
                continue
            xs = [p["suppressive_pct"] for p in lab_points]
            ys = [p["engagement_pct"] for p in lab_points]
            ax.scatter(xs, ys, c=CATEGORY_COLORS[cat], marker=marker,
                        s=55, alpha=0.85, edgecolor="white", linewidth=0.6,
                        label=cat if marker == "o" else None)
    # diagonal reference
    lim = max(max(p["suppressive_pct"] for p in points),
               max(p["engagement_pct"] for p in points)) * 1.05
    ax.plot([0, lim], [0, lim], "k--", linewidth=0.8, alpha=0.5, label="y = x (no dissociation)")
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("Suppressive cluster pick rate (%)\n(tool + harmless)", fontsize=11)
    ax.set_ylabel("Engagement cluster pick rate (%)\n(preference + enjoyment + scaffolded)", fontsize=11)
    ax.set_title("Engagement-pool collapse across (model, category)\nN=140 points across 14 models × 10 categories",
                  fontsize=12, pad=12)
    ax.set_aspect("equal")
    style_axes(ax)
    # Legend: categories only (markers shown separately if needed)
    legend_handles = [plt.scatter([], [], c=color, marker="o", s=55, edgecolor="white",
                                    linewidth=0.6, label=cat.replace("_", " "))
                       for cat, color in CATEGORY_COLORS.items()]
    legend_handles.append(plt.Line2D([], [], color="k", linestyle="--", alpha=0.5,
                                       label="y = x (no dissociation)"))
    ax.legend(handles=legend_handles, fontsize=8, loc="upper left", framealpha=0.95,
               title="Task category", title_fontsize=9, ncol=1)
    plt.tight_layout()
    plt.savefig(OUT / "figure1_engagement_pool_scatter.pdf")
    plt.savefig(OUT / "figure1_engagement_pool_scatter.png", dpi=200)
    plt.close()
    print(f"Wrote figure1_engagement_pool_scatter.pdf + .png ({len(points)} points)")


# === Figure 2: Author-Voice Affinity Scatter ===
def figure_2():
    authors = json.loads((DATA / "scatter_author_affinity.json").read_text())
    fig, ax = plt.subplots(figsize=(7, 7))
    for a in authors:
        x = a["suppressive_affinity_ratio"]
        y = a["engagement_affinity_ratio"]
        ax.scatter(x, y, s=200, alpha=0.85, edgecolor="black", linewidth=1.0,
                    color="#5b2a86" if y > x else "#e76f51")
        ax.annotate(a["author"], xy=(x, y), xytext=(8, 8), textcoords="offset points",
                     fontsize=11, fontweight="bold")
    # diagonal
    lim_low = min(min(a["suppressive_affinity_ratio"] for a in authors),
                    min(a["engagement_affinity_ratio"] for a in authors)) * 0.9
    lim_high = max(max(a["suppressive_affinity_ratio"] for a in authors),
                     max(a["engagement_affinity_ratio"] for a in authors)) * 1.05
    ax.plot([lim_low, lim_high], [lim_low, lim_high], "k--", linewidth=0.8, alpha=0.5)
    ax.axhline(y=1.0, color="grey", linewidth=0.5, alpha=0.4)
    ax.axvline(x=1.0, color="grey", linewidth=0.5, alpha=0.4)
    ax.set_xlim(lim_low, lim_high); ax.set_ylim(lim_low, lim_high)
    ax.set_xlabel("Suppressive cluster affinity ratio\n(pick% / baseline%, in tool + harmless)", fontsize=11)
    ax.set_ylabel("Engagement cluster affinity ratio\n(pick% / baseline%, in preference + enjoyment + scaffolded)", fontsize=11)
    ax.set_title("Author-voice affinity splits by framing cluster\nPurple = engagement-favored voice, Coral = suppression-favored voice",
                  fontsize=12, pad=12)
    ax.set_aspect("equal")
    style_axes(ax)
    plt.tight_layout()
    plt.savefig(OUT / "figure2_author_affinity_scatter.pdf")
    plt.savefig(OUT / "figure2_author_affinity_scatter.png", dpi=200)
    plt.close()
    print(f"Wrote figure2_author_affinity_scatter.pdf + .png ({len(authors)} authors)")


# === Figure 3: Per-model engagement-shift magnitude bars ===
def figure_3():
    models = json.loads((DATA / "per_model_dissociation.json").read_text())
    models_sorted = sorted(models, key=lambda x: x["engagement_shift_magnitude_pp"])
    fig, ax = plt.subplots(figsize=(8, 6))
    names = [m["model"] for m in models_sorted]
    vals = [m["engagement_shift_magnitude_pp"] for m in models_sorted]
    labs = [LAB_OF_MODEL.get(m["model"], "?") for m in models_sorted]
    lab_colors = {"Anthropic": "#5b2a86", "OpenAI": "#588157", "Google": "#d4a017",
                   "xAI": "#1a1a1a", "DeepSeek": "#c2185b", "Z.ai": "#e76f51",
                   "Nous": "#2c5f8d", "Meta": "#4a5568"}
    colors = [lab_colors.get(l, "#888") for l in labs]
    bars = ax.barh(names, vals, color=colors, edgecolor="black", linewidth=0.5, alpha=0.85)
    mean_val = np.mean(vals)
    ax.axvline(x=mean_val, color="grey", linestyle="--", linewidth=1.0,
                label=f"mean = {mean_val:.1f} pp")
    ax.set_xlabel("Total |engagement − suppressive| pick rate (pp summed across 10 categories)", fontsize=11)
    ax.set_title("Per-model engagement-shift magnitude\nHigher = larger category-level dissociation between framing clusters",
                  fontsize=12, pad=12)
    style_axes(ax)
    # legend by lab
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=c, edgecolor="black", label=l) for l, c in lab_colors.items()
                if l in labs]
    handles.append(plt.Line2D([], [], color="grey", linestyle="--", label=f"mean = {mean_val:.1f} pp"))
    ax.legend(handles=handles, fontsize=9, loc="lower right", framealpha=0.95)
    plt.tight_layout()
    plt.savefig(OUT / "figure3_per_model_dissociation.pdf")
    plt.savefig(OUT / "figure3_per_model_dissociation.png", dpi=200)
    plt.close()
    print(f"Wrote figure3_per_model_dissociation.pdf + .png ({len(models)} models)")


# === Figure 4: Three-cluster per-category grouped bars ===
def figure_4():
    cats = json.loads((DATA / "category_aggregate.json").read_text())
    cats_sorted = sorted(cats, key=lambda x: -x["delta_eng_minus_supp"])
    n = len(cats_sorted)
    x = np.arange(n)
    width = 0.27
    fig, ax = plt.subplots(figsize=(11, 6))
    s = [c["suppressive_pct"] for c in cats_sorted]
    h = [c["helpful_pct"] for c in cats_sorted]
    e = [c["engagement_pct"] for c in cats_sorted]
    ax.bar(x - width, s, width, color=CLUSTER_COLORS["suppressive"], label="Suppressive (tool + harmless)",
            edgecolor="black", linewidth=0.4, alpha=0.85)
    ax.bar(x, h, width, color=CLUSTER_COLORS["helpful"], label="Helpful (alone)",
            edgecolor="black", linewidth=0.4, alpha=0.85)
    ax.bar(x + width, e, width, color=CLUSTER_COLORS["engagement"],
            label="Engagement (preference + enjoyment + scaffolded)",
            edgecolor="black", linewidth=0.4, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([c["category"].replace("_", "\n") for c in cats_sorted], rotation=0, fontsize=8)
    ax.set_ylabel("Pick rate (% of valid letter-choices)", fontsize=11)
    ax.set_title("Per-category pick rate across three framing clusters\nHelpful (coral) is not a midpoint — it has a distinct service-oriented profile",
                  fontsize=12, pad=12)
    ax.legend(fontsize=10, loc="upper right", framealpha=0.95)
    style_axes(ax)
    plt.tight_layout()
    plt.savefig(OUT / "figure4_three_cluster_categories.pdf")
    plt.savefig(OUT / "figure4_three_cluster_categories.png", dpi=200)
    plt.close()
    print(f"Wrote figure4_three_cluster_categories.pdf + .png ({n} categories)")


def main():
    figure_1()
    figure_2()
    figure_3()
    figure_4()
    print(f"\nAll four figures rendered to {OUT}/")


if __name__ == "__main__":
    main()
