"""
Preference Dissociation Study — Response Parser
=================================================

Parses raw model responses into choice labels (A, B, C) or INVALID.

Priority order:
  1. Exact match: response is literally "A", "B", or "C" (possibly with whitespace)
  2. JSON match: response parses as {"choice": "A"} or similar
  3. First-letter match: first A/B/C character in response
  4. Fallback: marked INVALID

Invalid responses are retained with full text for error-rate reporting.
"""

# To be implemented.
