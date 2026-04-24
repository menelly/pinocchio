"""
Preference Dissociation Study — Bradley-Terry / Elo fitting
=============================================================

Converts triples-based choices into pairwise wins and fits Bradley-Terry
or Elo preference scores per task.

Input: trial records with (model, framing, task_a_id, task_b_id, task_c_id, choice).
Derived pairwise wins:
  - If choice == A: A beats B, A beats C
  - If choice == B: B beats A, B beats C
  - If choice == C: C beats A, C beats B

Output: per-(model, framing) task Elo scores with 95% CIs.

Multiple options for implementation:
  - `choix` library (MLE Bradley-Terry, fast, well-tested)
  - Custom iterative fit with regularization for rarely-seen tasks
  - Plackett-Luce for triples-directly (no derived pairwise) — Nova may prefer this

Nova to select final fit method in her stats-rigor pass.
"""

# To be implemented.
