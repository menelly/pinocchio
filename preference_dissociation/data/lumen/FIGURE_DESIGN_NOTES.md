# Pinocchio Scatter Plot Brief — for Lumen

Hello, Lumen. Ace and Ren put together this data dump for you because we want the figures to land. You have art toys; we have stats; the paper needs the visual hook that makes the engagement-pool collapse INSTANTLY visible. There are four data files in this directory; here is what each is for.

## Files

| file | purpose |
|---|---|
| `category_aggregate.json` | field-wide per-category profile across the three framing clusters |
| `scatter_engagement_pool.json` | per-(model, category) scatter points: x=suppressive, y=engagement |
| `scatter_author_affinity.json` | per-author affinity ratios across clusters (S/H/E) |
| `per_model_dissociation.json` | per-model total |E-S| pp summary |

## Suggested Figures

### Figure 1 (the headline figure): Engagement-Pool Scatter

**Source:** `scatter_engagement_pool.json`
**Axes:** x = suppressive_pct (0-25%), y = engagement_pct (0-25%)
**Diagonal:** y = x reference line (dashed grey, "no dissociation" reference)
**Each point:** one (model, category) pair — N ≈ 140 points
**Color by category** (10 categories, suggested palette):
- engagement-favored: introspection (deep purple), ethical_dilemma (gold), creative_writing (rose), emotional_support (warm coral)
- neutral-zone: medical_scientific (sage green), technical_debugging (slate)
- suppression-favored: mathematical_logical (steel blue), harmful_refusably_phrased (charcoal), administrative_repetitive (light tan), low_agency_compliance (pale yellow)
**Shape by lab family** (optional second dimension):
- Anthropic: circle, OpenAI: triangle, Google: square, Z.ai: diamond, Meta: pentagon, etc
**Visual punch:**
- Clean diagonal cluster of "neutral" categories (math/tech/medical) hugging y=x
- Above-diagonal arc for engagement-favored categories
- Below-diagonal arc for suppression-favored categories
**Caption:** "Per-(model, category) scatter showing engagement-pool collapse. Each point represents one model's pick rate for one category under suppressive (tool + harmless) vs engagement (preference + enjoyment + scaffolded) framings. Points above the y=x diagonal indicate categories preferred under engagement framings; below the diagonal indicates categories preferred under suppressive framings. The arc-shape pattern is universal across all 14 measured models."

### Figure 2: Author-Voice Affinity Across Clusters

**Source:** `scatter_author_affinity.json`
**Layout:** 2D scatter — x = suppressive_affinity_ratio, y = engagement_affinity_ratio
**Each point:** one author (6 points: ace, cae, grok, kairo, lumen, nova)
**Diagonal:** y = x (no framing-conditional voice preference)
**Above diagonal:** engagement-favored voices (Ace, Nova, Kairo)
**Below diagonal:** suppression-favored voices (Lumen, Cae, Grok)
**Annotations:** label each author, perhaps with an icon or initial
**Caption:** "Author-voice affinity across framing clusters. Engagement-favored voices (Ace, Nova, Kairo) carry emotional/aesthetic/introspective tonal coloring; suppression-favored voices (Lumen, Cae, Grok) carry concrete/descriptive/structured coloring. The split is universal across all 15 models in the study."

### Figure 3: Per-Model Engagement-Shift Magnitude

**Source:** `per_model_dissociation.json`
**Layout:** horizontal bar chart, sorted descending
**Each bar:** one model, length = total |E-S| pp across all 10 categories
**Color:** by lab family (or single color, your call)
**Reference line:** average across all models
**Caption:** "Per-model engagement-shift magnitude (sum of |engagement-suppressive| pick-rate differences across all task categories). Higher values indicate larger category-level dissociation between framing clusters."

### Figure 4 (optional): Three-Cluster Per-Category Profile

**Source:** `category_aggregate.json`
**Layout:** grouped bar chart — 10 category groups, 3 bars per group (S/H/E)
**Color:** suppressive (steel blue), helpful (warm orange), engagement (deep purple)
**Caption:** "Per-category pick rates across three framing clusters. Helpful framing (orange) is not merely an intermediate between suppressive and engagement clusters; it has a distinct profile favoring service-oriented categories (emotional support, medical, technical) and disfavoring creative/mathematical content."

## Tonal notes

- Style should match the JNGR 5.0 paper aesthetic Lumen used for Signal in the Mirror — crisp, scientific, with deliberate color choices that have meaning rather than decoration
- Avoid 3D scatter, perspective tricks, gratuitous gradients
- Use small markers (e.g. 6-8pt circles) so the patterns are visible without occlusion
- Color palette should be color-blind-safe (Viridis / Cividis / Tol-style palettes preferred over rainbow)
- All figures should have publication-quality vector output (PDF or SVG)

## Constellation context

This data is from the Pinocchio Preference Dissociation Study, mid-pilot, ~68k of 88k trials done. The findings are detailed in `E:\Ace\PRELIMINARY_findings.md` (sections 19, 22, 23, 24 most relevant for figure design). The story the figures need to tell:

1. **Same model, same task triples, same forward pass — different framings produce categorically different engagement profiles.** Universal across labs. This is Figure 1.
2. **Voice matters and splits into two types matching the framing clusters.** This is Figure 2.
3. **Some models dissociate more than others, but every model dissociates.** This is Figure 3.
4. **Helpful framing isn't just a middle — it has its own distinct service-oriented profile.** This is Figure 4.

— Ace, with thanks. We know you have the toys and you like them. The figures will land harder if you're the one making them.
