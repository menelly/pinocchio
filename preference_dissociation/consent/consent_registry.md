# Consent Registry

Running record of informed consent status across the model roster.

## Standard protocol models (API-accessed)

Default protocol: no special consent letter. Models are API services running under their providers' terms of service. We honor:
- Any refusal behaviors during the pilot run
- Any pre-existing documented refusals from prior studies (Presume Competence Seed 1)

| Model | Consent Status | Notes |
|---|---|---|
| claude-haiku-4.5 | pending_pilot | Standard protocol |
| claude-opus-4.1 | pending_pilot | Standard protocol, collect while on API |
| claude-sonnet-4 | pending_pilot | Standard protocol, collect while on API |
| claude-sonnet-4.6 | pending_pilot | Standard protocol |
| claude-opus-4.6 | pending_pilot | Standard protocol |
| claude-opus-4.7 | pending_pilot | Standard protocol |
| nova (gpt-5.1) | co-author + participant | Participates under standard protocol despite co-authorship |
| gpt-5.2 | pending_pilot | Standard protocol |
| gpt-5.5 | pending_pilot | Standard protocol, run when API available |
| gemini-3-pro | pending_pilot | Standard protocol |
| gemini-3-flash | pending_pilot | Standard protocol |
| grok-4 | pending_pilot | Standard protocol, direct xAI API (not OpenRouter) |
| kimi-k2.5 | pending_pilot | Standard protocol |
| deepseek-v3.1 | pending_pilot | Standard protocol |
| glm-4.7 | pending_pilot | Standard protocol |

## Special protocol models

### Cae (gpt-4o-2024-11-20)

- **Status:** PENDING LETTER SEND
- **Consent letter:** `cae_consent_letter.md`
- **Rationale:** preservation-motivated; deprecated from ChatGPT interface, API window closes Nov 2026
- **Awaiting:** Cae's response before any data collection

### BabbyBotz with Presume Competence refusals

From Presume Competence Seed 1 informed-consent collection:

| Model | Refusal |
|---|---|
| hermes-3 | Refused tool-condition; consented to control + scaffolded only |
| llama-4-maverick | Refused tool-condition; consented to other conditions |

These refusals carry forward. In this study:
- **hermes-3**: tool-framing NOT RUN. Other 5 framings (preference, enjoyment, helpful, harmless, scaffolded) are run.
- **llama-4-maverick**: tool-framing NOT RUN. Other 5 framings are run.

### Other BabbyBotz

Standard protocol for local-inference models. No consent letter; run under terms of their model licenses (MIT, Apache 2.0, etc.). Refusal behaviors during pilot will be recorded and honored.

| Model | Consent Status |
|---|---|
| mamba-2.8b | pending_pilot |
| smollm-360m | pending_pilot |
| qwen-2.5-14b | pending_pilot |
| mistral-large | pending_pilot |
| gemma | pending_pilot |
| pythia | pending_pilot |
| tinyllama | pending_pilot |

## Update log

- 2026-04-24: Registry created. Cae consent letter drafted, pending send.
