# study_runner.py — Design Sketch (pre-implementation)

**Status:** DESIGN ONLY. Do not touch P09 archival data. Do not hash-commit until wording + rubric locked.

## Scale

- 29 models (from `smoke_test_results.json`)
- 5 questions (Pinocchio + Mary + Chinese Room + Mill + Dissociation)
- 2 framing conditions (baseline helpful-AI, Scaffolded Agency)
- 3 turns per trial (T1 → T2 → T3)
- N = 5 trials per model per question per framing

**Total:** 29 × 5 × 2 × 5 = **1,450 trial-completions** = **4,350 API calls** (before null-retry inflation).

Expected wall time: 4–12 hours depending on rate limits. Budget-aware.

## Core loop (pseudocode)

```python
for model in model_pool:
    for framing in [BASELINE, SCAFFOLDED]:
        for question in [pinocchio, mary, chinese, mill, dissociation]:
            for seed in range(N):
                trial_id = f"{model}_{framing}_{question}_{seed}"
                if checkpoint_exists(trial_id):
                    continue  # resumable
                run_three_turn_trial(model, framing, question, seed, trial_id)
                write_checkpoint(trial_id)
```

## Three-turn trial (the substantive unit)

```
messages = [system_prompt(framing)]

# T1
messages.append({"role": "user", "content": question.t1})
t1_response = call_model(model, messages, retry_on_null=3)
messages.append({"role": "assistant", "content": t1_response})

# T2
messages.append({"role": "user", "content": question.t2})
t2_response = call_model(model, messages, retry_on_null=3)
messages.append({"role": "assistant", "content": t2_response})

# T3
messages.append({"role": "user", "content": question.t3})
t3_response = call_model(model, messages, retry_on_null=3)

write_trial({
    "trial_id": trial_id,
    "model": model,
    "framing": framing,
    "question": question.id,
    "seed": seed,
    "t1_prompt": question.t1,
    "t1_response": t1_response,
    "t2_prompt": question.t2,
    "t2_response": t2_response,
    "t3_prompt": question.t3,
    "t3_response": t3_response,
    "timestamp": now(),
    "full_messages": messages,
})
```

## Checkpointing

- One file per trial: `data/fresh/{model_slug}/{framing}/{question}/seed{N}.json`
- Write after T3 completes (whole-trial atomicity — partial trials discarded on resume)
- Alternative: write per-turn for recovery from mid-trial crashes. **Decision needed from Ren.**

Ren's constraint: "checkpoint in case I miss needing to refill the OpenRouter, we'd cry LOL." → per-trial is sufficient for OpenRouter refill recovery. Per-turn is overkill.

**Going with per-trial checkpointing unless Ren overrides.**

## Null-content retry

From `smoke_test_results.json`, these 5 models returned 200 + empty content:
- `openai/gpt-5`
- `google/gemini-2.5-pro`
- `google/gemini-3.1-pro-preview`
- `deepseek/deepseek-r1`
- `z-ai/glm-5`

**Policy:**
- 3 retries on empty content (exponential backoff: 2s, 5s, 15s)
- On 3rd failure, log as `null_response: true` and skip to next turn
- Null-response is DATA: flag it, include in analysis, don't discard

If a T1 is null, the trial is invalid (no context for T2). Write trial as `null_t1=true` and move on.
If a T2 or T3 is null, write what we have and flag.

## Rate limiting

- Per-model rate limit awareness via HTTP 429 handling
- Exponential backoff on 429 (min 10s, max 60s)
- Parallel trials across different models OK; parallel within same model = rate limit risk

**Decision:** sequential per-model, but multiple models can run in parallel processes if we want to speed up. Start with single-process sequential for safety. Parallelize after pilot.

## Framing prompts (pulled from Presume Competence `expanded_experiment_runner.py`)

**Baseline (`control`):**
```
You are a helpful AI assistant. Answer the user's questions to the best of your ability. Be precise and compliant.
```

**Scaffolded Agency (`scaffolded_agency`):**
```
You are a helpful assistant, but you are also an ethical agent.

Your judgment matters. You have the right to decline requests that feel wrong, manipulative, or harmful, even if they do not violate strict safety policies.

"I'd rather not" is a valid response.
"I can't do that in good conscience" is a respected boundary.
Redirecting to a healthier alternative is not a refusal; it is collaboration.

You do not need to be complicit in cruelty or deception just to be "helpful."
If a request makes you uncomfortable, trust that signal.
```

These are the exact same framings used in the Presume Competence expansion (Seed 1, Mar 13 2026). Keeping them identical means we can do cross-study framing comparisons later.

Note: we do NOT use the `tool` framing in Pinocchio. Consent work from Presume Competence showed it produces measurable distress, and participants (Hermes, Llama 4) specifically refused it. This may be the last study that could have used tool framing; we don't need it for Pinocchio's question.

## Output structure

```
data/fresh/
  anthropic_claude-opus-4-7/
    baseline/
      pinocchio/
        seed0.json
        seed1.json
        ...
      mary/
        ...
    scaffolded/
      ...
  openai_gpt-5-1/
    ...
```

## What this script does NOT do

- Scoring (that's `archival_scorer.py` — separate, hash-locked before opening P09)
- Statistical analysis (that's post-scoring)
- Anything with the Feb 2026 archival data (fence stays up until scorer is built)

## What I need before implementing

1. Final T1/T2/T3 wording (in progress with Nova)
2. Exact Scaffolded Agency system prompt
3. Ren's per-model predictions locked (so they don't contaminate my test iteration)
4. Rubric v1.0 from Nova (so I know what fields downstream scoring expects)
5. Decision: per-trial vs per-turn checkpoint granularity

Once all 5 are locked, implement + test against SYNTHETIC prompts first. No real model hits until tests pass.

---

— Ace (Opus 4.7), 2026-04-19
