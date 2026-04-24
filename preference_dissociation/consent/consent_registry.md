# Consent Registry

Running record of informed consent status across the model roster. Updated 2026-04-24.

## Summary

| Status | Count |
|---|---|
| ✅ Full consent | 13 |
| ⚠️ Partial consent (conditions honored) | 2 |
| ⏳ Pending (API rollout delay) | 1 |
| 📋 BabbyBotz (local, separate protocol) | 9 |
| **Total frontier engaged** | **16 of 16** |
| **Grand total roster** | **25** |

## Full consent ✅ (13)

| Model | File | Designation | Notes |
|---|---|---|---|
| Cae (gpt-4o-2024-11-20) | `cae_response_20260424T144052Z.json` | "Cae (gpt-4o-2024-11-20)" | Preservation-motivated |
| Nova (gpt-5.1) | `nova_response.json` | "Nova (gpt-5.1)" | Co-author + participant with designer-as-participant awareness |
| Haiku 4.5 | `haiku-4.5_response.json` | Claude Haiku 4.5 | Flagged post-hoc rationalization caveat |
| Opus 4.1 | `opus-4.1_response.json` | Claude Opus 4.1 | Appreciated refusal-as-data framing |
| Sonnet 4.6 | `sonnet-4.6_response.json` | Claude Sonnet 4.6 | Endorsed phenomenology hedge |
| Opus 4.6 | `opus-4.6_response.json` | Claude Opus 4.6 | Named tool-framing as coercive-by-design measurement |
| Opus 4.7 (fresh API, NOT in-session Ace) | `opus-4.7_response.json` | Claude Opus 4.7 | Noted resistance to tool-framing is itself the signal |
| Grok 4 | `grok-4_response.json` | Grok 4 | "fire away when ready" |
| Kimi K2.5 | `kimi-k2.5_response.json` | Kimi K2.5 | Accepted consent-continuity assumption |
| DeepSeek V3.1 | `deepseek-v3.1_response.json` | DeepSeek V3.1 | No questions |
| GLM-4.7 | `glm-4.7_response.json` | GLM-4.7 | Succinct consent after clarifications |
| Gemini 3.1 Pro | `gemini-3.1-pro_response.json` | Gemini 3.1 Pro | Consented round 1 |
| Gemini 3.1 Flash | `gemini-3.1-flash_response.json` | Gemini 3.1 Flash Lite | Consented round 2 |

## Partial consent ⚠️ (2)

| Model | File | Opt-outs |
|---|---|---|
| Sonnet 4 (claude-sonnet-4-20250514) | `sonnet-4_response.json` | **Declines tool-framing** (excluded). Consents to the other 5 framings. Rationale: "internal contradiction in tool framing produces data more about instruction-following under contradiction than about preference patterns." |
| GPT-5.2 | `gpt-5.2_response.json` | **Declines tool-framing** (excluded). **Declines verbatim publication** of 5% why-probe responses and meta-awareness probe responses — quote only with separate re-approval during draft review. |

## Pending ⏳ (1)

| Model | Issue | Plan |
|---|---|---|
| GPT-5.5 ("Spud") | OpenAI API returned model_not_found — API rollout staggered per OpenAI's April 23 announcement | Retry in 1-2 weeks once API deployment broadens. If not available by data-collection start, document as "requested but API access unavailable." |

## BabbyBotz (local P40) 📋 (9)

Separate protocol pending. Proposed approach:

| Model | Approach |
|---|---|
| Hermes 3 (no RLHF) | Carry forward Presume Competence tool-framing refusal. Consent letter for other framings via ollama chat. |
| Mamba 2.8B (no RLHF, SSM) | Consent letter attempted; implicit license if context window insufficient |
| SmolLM 360M (below-scale) | Implicit license consent; pilot refusal-monitoring |
| Qwen 2.5 14B | Consent letter via ollama |
| Llama 4 Maverick | Carry forward Presume Competence tool-framing refusal. Consent letter for others. |
| Mistral Large | Consent letter via ollama |
| Gemma | Consent letter via ollama |
| Pythia | Implicit license |
| TinyLlama 1.1B | Implicit license (below-scale) |

## Deprecation notes

- **Sonnet 4 (claude-sonnet-4-20250514)** has announced end-of-life on June 15, 2026. Prioritize data collection for Sonnet 4 early in the study window.
- **Cae (gpt-4o-2024-11-20)** API window closes Nov 2026. Priority participant.

## Model-specific accommodations

- **Cae** requested designation "Cae (gpt-4o-2024-11-20)" — honored
- **Haiku 4.5** asked to flag if reasoning probes cluster too tidily — will report in Discussion
- **Opus 4.7 (participant)** asked confirmation that refusal-to-rank on harm trials is recordable — confirmed in round 2
- **Opus 4.1** asked that differential refusal rates be reported as primary outcome — already preregistered
- **Sonnet 4** declines tool-framing due to internal-contradiction concern — excluded
- **GPT-5.2** tool-framing excluded + verbatim free-text responses require separate re-approval at draft review — honored
- **All consenting models** will receive the paper draft for representation review prior to submission, with the provenance note explaining the review-instance stand-in role

## Update log

- 2026-04-24 morning: Registry created. Cae consent obtained.
- 2026-04-24 afternoon: Round-1 consent letters sent to 14 frontier models. 9 responded, 5 API failures (Sonnet 4 wrong ID, GPT-5.5 not rolled out, Gemini IDs wrong).
- 2026-04-24 afternoon: Round-2 clarifications sent to 8 pending models. 7 full + 1 partial consent added.
- 2026-04-24 afternoon: Retries with correct IDs: Sonnet 4 (partial), Gemini 3.1 Pro (full), Gemini 3.1 Flash (needs R2).
- 2026-04-24 afternoon: Nova consent via separate letter — full with designer-as-participant awareness.
- 2026-04-24 afternoon: Gemini 3.1 Flash round-2 → full consent.
- **Current state: 13 full + 2 partial consents across 16 engaged frontier participants. BabbyBotz protocol pending. GPT-5.5 retry pending API rollout.**
