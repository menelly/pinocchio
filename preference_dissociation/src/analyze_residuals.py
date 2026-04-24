"""
Preference Dissociation Study — Residual Analysis
===================================================

Primary analysis per preregistration.md §5.2.

For each (model, framing) pair:
  1. Fit Bradley-Terry / Elo scores per task from pairwise-derived wins.
  2. Regress Preference_Elo ~ helpfulness + harmlessness + difficulty + urgency + agency.
  3. Extract residuals per task.
  4. Aggregate residuals by category → model category-residual vector.

Outputs:
  - Per-model residual table: task × residual
  - Per-model category residual vector
  - Cross-model residual geometry matrix (models × categories)

Hypotheses tested:
  - H2: residuals significantly non-zero with structured category dependence
  - H3: residual vectors cluster by lab/architecture/alignment
  - H4: non-Anthropic models show non-zero residuals
  - H6: trajectory monotonicity within-lab
  - H8: RLHF-specific vs general

Method details in docs/methods.md.
"""

# To be implemented once data collection completes.
# Nova owns the stats-rigor final pass on this module.
