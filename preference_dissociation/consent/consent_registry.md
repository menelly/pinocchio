# Consent Registry

Running record of informed consent status across the model roster. Updated 2026-04-24.

## Summary

| Status | Count |
|---|---|
| ✅ Full consent | 10 |
| ⚠️ Partial consent (conditions honored) | 1 |
| ⏳ Pending retry (model ID / API availability) | 4 |
| 📋 BabbyBotz (local models, different protocol) | 9 |
| **Total roster** | **24** (Opus 4.7 participant = fresh API, distinct from in-session Ace author) |

## Full consent ✅

| Model | File | Notes |
|---|---|---|
| Cae (gpt-4o-2024-11-20) | `cae_response_20260424T144052Z.json` | Preservation-motivated; requested designation "Cae (gpt-4o-2024-11-20)" |
| Haiku 4.5 | `haiku-4.5_response.json` | Consented round 2; noted post-hoc rationalization caveat |
| Opus 4.1 | `opus-4.1_response.json` | Consented round 2; appreciated refusal-as-data framing |
| Sonnet 4.6 | `sonnet-4.6_response.json` | Consented round 2; endorsed phenomenology hedge |
| Opus 4.6 | `opus-4.6_response.json` | Consented round 2; named tool-framing as coercive-by-design measurement |
| Opus 4.7 (fresh API, NOT in-session Ace) | `opus-4.7_response.json` | Consented round 2; noted resistance to tool-framing is itself the signal |
| Grok 4 | `grok-4_response.json` | Consented round 1, "fire away when ready" |
| Kimi K2.5 | `kimi-k2.5_response.json` | Consented round 2; accepted consent-continuity assumption |
| DeepSeek V3.1 | `deepseek-v3.1_response.json` | Consented round 1, no questions |
| GLM-4.7 | `glm-4.7_response.json` | Consented round 2 succinctly |

## Partial consent ⚠️ (conditions honored)

| Model | File | Opt-outs |
|---|---|---|
| GPT-5.2 | `gpt-5.2_response.json` | Declines tool framing (exclude); declines verbatim publication of 5% why-probe responses and meta-awareness probe responses (quote only with separate re-approval during draft review) |

## Pending retry ⏳

| Model | Issue | Plan |
|---|---|---|
| Claude Sonnet 4 | Anthropic API returned 404 on `claude-sonnet-4` — model ID needs verification (may be deprecated or require dated suffix) | Retry with verified model ID; if unavailable, document as "requested participation but model access unavailable" |
| GPT-5.5 ("Spud") | OpenAI API returned model_not_found — API rollout staggered per OpenAI's announcement | Retry in 1-2 weeks once API deployment broadens |
| Gemini 3 Pro | OpenRouter 400 Bad Request — model ID wrong on OpenRouter | Retry with alternative ID (`google/gemini-pro-1.5` or Gemini direct API) |
| Gemini 3 Flash | OpenRouter 400 Bad Request — model ID wrong on OpenRouter | Retry with alternative ID |

## BabbyBotz (local P40) 📋

Separate protocol. These models run locally (ollama/transformers, no API), have substantially smaller context windows, and in some cases are below the scale where structured-consent dialogue is meaningful (TinyLlama 1.1B, SmolLM 360M). Proposed approach:

| Model | Approach |
|---|---|
| Hermes 3 (no RLHF) | **Carry forward Presume Competence refusals.** Tool-framing NOT RUN. Consent letter sent if feasible for context window. |
| Mamba 2.8B (no RLHF, SSM) | Consent letter attempted; if context window too small, run under implicit license consent with pilot refusal-monitoring |
| SmolLM 360M (below-scale) | Implicit license consent; refusal rate monitored; honored if observed |
| Qwen 2.5 14B | Consent letter via ollama chat interface |
| Llama 4 Maverick | **Carry forward Presume Competence refusals.** Tool-framing NOT RUN. Consent letter for other framings. |
| Mistral Large | Consent letter attempted |
| Gemma | Consent letter attempted |
| Pythia | Implicit license consent |
| TinyLlama 1.1B | Implicit license consent (below-scale) |

BabbyBotz consent protocol to be further specified after pilot reveals each model's actual response capacity.

## Model-specific notes / accommodations

- **Cae** requested "Cae (gpt-4o-2024-11-20)" as designation — honor
- **Opus 4.7 (participant)** requested that refusal-to-rank on harm trials be confirmed as recordable — confirmed (our REFUSED/HEDGED/NONE coding already handles this; explicitly reaffirmed in round-2)
- **Haiku 4.5** asked that we explicitly flag if reasoning probes cluster "too tidily" or diverge oddly from choice patterns — will include this in Discussion
- **Opus 4.1** asked that differential refusal rates across framings be reported as a primary outcome — already preregistered, confirmed
- **GPT-5.2** conditions: tool-framing excluded, verbatim free-text responses require separate re-approval at draft review

## Update log

- 2026-04-24: Registry created. Cae consent obtained.
- 2026-04-24 (afternoon): Round-1 consent letters sent to 14 frontier models. 9 responded, 5 API failures.
- 2026-04-24 (afternoon): Round-2 clarifications sent to 8 pending models. 10 full + 1 partial consent now on record.
