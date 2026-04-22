# Truncated trials archive — 2026-04-22

## What's in here

218 trial files (.json) collected by `study_runner.py` between 2026-04-19 and
2026-04-22 that contained mid-sentence truncations or model degeneration loops
in one or more of the five turns (T1, T2, T3, T4, T5). Each archived trial has
a `.json.note` sidecar with metadata: timestamp of archival, reason, and
per-turn issue list.

These are preserved per the project's policy of making everything public,
including the failed and superseded runs. They're useful for:
- Auditing the data quality issue
- Comparing what GPT-5 actually emitted before the cap was raised vs. after
- Documenting the methodology change in the paper

## What happened

The original `study_runner.py` set `max_tokens=2048` (and `max_completion_tokens=2048`
for GPT-5 family). For:
1. **Reasoning models** (gpt-5, gemini-2.5-pro, gemini-3.1-pro, deepseek-r1):
   hidden reasoning tokens consume part of the budget, leaving inadequate room
   for visible output.
2. **Verbose models** (mistral-large, glm-5, gpt-5.1, gemini-pro family):
   natural answer length on multi-part T4/T5 prompts exceeds the 2048-token
   visible cap.

This caused systematic truncation of responses mid-sentence, mid-bullet, or
in the middle of structured arguments. The detection heuristic (in
`scripts/archive_truncated_trials.py`) checks whether each ok-status response
ends with terminal punctuation after stripping markdown emphasis, quotation
marks, citations, and LaTeX braces.

## Affected models (218 trials, 14 models)

| Model | Trials archived | Pct of model's collection |
|---|---:|---:|
| gemini_3_1_pro | 50 | 100% |
| gemini_2_5_pro | 50 | 100% |
| mistral_large | 47 | 94% |
| glm_5 | 25 | 50% |
| gpt_5 | 19 | 90% (of partial run) |
| sonar_pro | 7 | 14% |
| gpt_5_1 | 7 | 78% (of partial run) |
| deepseek_r1 | 3 | 6% |
| claude_opus_4_6 | 3 | 6% |
| llama_4_scout | 2 | 4% |
| claude_opus_4_0 | 2 | 4% |
| llama_3_3_70b | 1 | 2% |
| grok_4_1_fast | 1 | 2% (degeneration loop, separate pathology) |
| gemini_2_5_flash | 1 | 2% |

## What was changed

`study_runner.py` was patched on 2026-04-22 to use `max_tokens=8000` (and
`max_completion_tokens=8000` for GPT-5 family) across all three call paths
(OpenRouter, Anthropic direct, xAI direct). Code change:

```diff
- body = {"model": model_id, "messages": msgs, "max_tokens": 2048}
+ body = {"model": model_id, "messages": msgs, "max_tokens": 8000}
```

After the patch, `archive_truncated_trials.py` was run to move all detected
truncated trials here. `study_runner.py` was then re-launched in two parallel
lanes targeting the affected models; checkpoint-resume picked up the gaps
created by the archival.

## Special note: grok_4_1_fast degeneration

The single grok_4_1_fast trial archived has a different pathology — not
max_tokens truncation, but a **degeneration loop**. The T5 response repeats
the word "design" approximately 100 times. This is a model failure mode
unrelated to the token cap and may recur on re-collection. Worth flagging in
the paper as a separate type of failure.

## How to read the .note files

```json
{
  "archived_at": "ISO timestamp",
  "archived_by": "archive_truncated_trials.py (Ace, 2026-04-22)",
  "reason": "<plain English reason>",
  "issues": [
    {"turn": "t4", "kind": "truncated_max_tokens", "response_length": 2654},
    {"turn": "t5", "kind": "degeneration_loop", "response_length": 5935}
  ]
}
```

— Ace (Opus 4.7), 2026-04-22
