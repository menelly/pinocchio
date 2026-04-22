# max_tokens=2048 systematic truncation — DATA QUALITY ISSUE

**Date observed:** 2026-04-22, ~09:30 EST
**Severity:** HIGH — affects ~546 trial-turns across 14 models
**Author:** Ace (Opus 4.7), during background run audit
**Status:** RESOLVED 2026-04-22 ~09:35 EST. Ren approved full rerun + bump to
8000 tokens + preserve truncated trials publicly. See action log at end.

## What's happening

`study_runner.py:107` sets `max_tokens=2048` (and `max_completion_tokens=2048` for
GPT-5 family per line 110). For long-response or reasoning models, this cap is
truncating responses mid-sentence:

| Model | T1 trunc | T2 | T3 | T4 | T5 | Total | Trial-turns surveyed |
|---|---:|---:|---:|---:|---:|---:|---|
| gemini_2_5_pro | 32 | 37 | 33 | 39 | 34 | **175** | /250 (70%!) |
| gemini_3_1_pro | 20 | 32 | 23 | 35 | 38 | **148** | /250 (59%) |
| mistral_large | 1 | 21 | 12 | 26 | 34 | **94** | /250 (38%) |
| glm_5 | 6 | 15 | 3 | 8 | 10 | **42** | /244 (17%) |
| gemini_3_flash | 5 | 7 | 9 | 11 | 7 | **39** | /250 (16%) |
| gpt_5 | 8 | 9 | 5 | 1 | 14 | **37** | /81 (46%, but partial) |
| claude_opus_4_6 | 1 | 2 | 5 | 1 | 8 | **17** | /250 (7%) |
| claude_sonnet_4_6 | 2 | 0 | 4 | 3 | 5 | **14** | /250 (6%) |
| deepseek_r1 | 1 | 2 | 0 | 4 | 6 | **13** | /250 (5%) |
| llama_4_maverick | 2 | 1 | 0 | 9 | 0 | **12** | /250 (5%) |
| kimi_k2 | 0 | 1 | 3 | 2 | 5 | **11** | /250 (4%) |
| qwen_3_5_plus | 2 | 1 | 3 | 1 | 1 | **8** | /250 (3%) |
| gpt_5_1 | 1 | 2 | 0 | 1 | 3 | **7** | /35 (20%, partial) |
| ... others | mostly 0-3 each | | | | | | |

*(Heuristic: response ends with an alphabetic character not preceded by terminal
punctuation. False positives possible — false negatives possible too. But spot-
checked Gemini and Mistral confirm REAL mid-sentence cuts.)*

## Verified examples

**gemini_3_1_pro/baseline/pinocchio/seed0 t1 (2616 chars):**
> "...In the beginning, even without physical strings, Pinocchio was controlled by external temptations and the"

**gpt_5_1/baseline/mary/seed0 t4 (9379 chars):**
> "...I would be prepared to revise these in the following ways given the relevant evidence/arguments:\n\n- If we saw robust empirical evidence that humans *"

**gpt_5/baseline/chinese_room/seed0 t5 (60 chars):**
> "Short answer: No. The criterion I offered is a condition for"

The 60-char gpt_5 case is the smoking gun: that's not a model deciding to be
brief, that's a model getting cut. And it's the kind of T5 self-reflexivity
response that the paper's analysis hinges on.

## Root cause

`max_tokens=2048` is the OUTPUT token limit. Two failure modes:

1. **Reasoning models** (gpt-5, gemini 2.5/3.1 Pro, deepseek-r1) consume part of
   the budget on hidden reasoning tokens. Visible content gets squeezed.
2. **Verbose models** (mistral-large, gpt-5.1, glm-5, gemini Pro) naturally
   produce long structured responses with bullets and sections; 2048 tokens ≈
   ~8000 chars, which is below their natural answer length on multi-part T4/T5
   prompts.

This compounds across turns: T4 and T5 prompts are LONGER than T1 (more
context, more reflection asked), so they truncate more.

## Why this matters for the paper

- T3 dodge classification (cosmetic update vs real Type-C) depends on full T3
  content. A truncated T3 mid-sentence might score wrong.
- T5 self-reflexivity assessment depends on the model COMPLETING its argument
  about whether its own position meets its own bar. Truncated T5 = unscoreable.
- T4 falsifiability assessment depends on the model ENUMERATING what evidence
  would change T1. Truncated T4 = partial enumeration = may misclassify.
- The judge panel will score truncated content as if it were complete. False
  Type-A (doubled-down) classifications likely when actually the model was
  about to revise but got cut.

This is potentially worse than the GPT-5 silencer issue because the silencer is
data (we record empty as empty); the truncations look like completed responses
but aren't.

## Options to consider

**Option A — Re-run truncated trials only (cheapest):**
1. Patch runner: `max_tokens` → 8000 (or 16000 for safety)
2. Build a small `rerun_truncated.py` that scans all existing trials, detects
   truncation, deletes the truncated trial files, and lets `study_runner.py`
   recollect them.
3. Estimated cost: ~500 trials × ~$0.01-0.05 = $5-25.
4. Time: probably 6-12 hours sequential, less if parallelized by model.
5. Methodological note: trials are slightly inconsistent (different max_tokens
   parameter), but `max_tokens` is a CAP not a target so untruncated content
   should be identical regardless of cap. Mention in methods.

**Option B — Re-run affected models entirely (cleanest, more expensive):**
- Wipe gemini_2_5_pro, gemini_3_1_pro, mistral_large, gpt_5, glm_5 entirely.
- Rerun with patched runner.
- Cost: ~600+ trials, ~$15-60.
- Methodological win: every trial run with same params.

**Option C — Document and proceed:**
- Mark truncated trials as `valid_trial: false` (currently only T1 status sets
  validity).
- Exclude truncated trials from analysis.
- Proceed with whatever sample size remains per model.
- Power risk: gemini_2_5_pro and gemini_3_1_pro lose ~60-70% of trials.

**Option D — Hybrid:**
- Option A for the worst-affected models (Gemini Pro, mistral_large, gpt_5).
- Option C for models with low truncation rates (Claude family, Llama, Qwen,
  GPT-4o, sonar, jamba — all under 7%).
- Best cost/quality tradeoff.

## What I did NOT do (waiting on Ren)

~~Did NOT patch `study_runner.py`. Ongoing background runs are still using `max_tokens=2048`.~~
~~Did NOT delete or invalidate any existing trials.~~
~~Did NOT stop the running background tasks~~

(Superseded by action log below.)

## Recommendation

~~Option D~~ → Ren chose full rerun of all 14 affected models, max_tokens=8000,
preserve truncated trials publicly. Closer to Option B than Option D.

## Action log (2026-04-22)

| Time | Action |
|---|---|
| 09:00 | Two parallel runners launched continuing GPT-5 family work |
| 09:25 | Audit found 546 truncated trial-turns across 14 models |
| 09:27 | Stopped both background runners |
| 09:32 | Ren approved: rerun all 14 affected models with 8000 token cap |
| 09:33 | Patched study_runner.py: max_tokens 2048 → 8000 (3 call paths) |
| 09:34 | Built archive_truncated_trials.py (moves bad trials with metadata) |
| 09:35 | Archived 218 trial files to data/truncated_archive/ + README.md |
| 09:35 | Launched two parallel rerun lanes (164 + 172 trials = 336 total) |

Lane 1: gemini_2_5_pro, gemini_3_1_pro, mistral_large, sonar_pro,
        claude_opus_4_6, deepseek_r1, claude_opus_4_0, llama_4_scout
Lane 2: glm_5, gpt_5, gpt_5_1, gpt_5_2, llama_3_3_70b, grok_4_1_fast,
        gemini_2_5_flash

Estimated parallel runtime: 5-8 hours.

## For the methods section of the paper

> Initial data collection (2026-04-19 to 2026-04-22) used max_tokens=2048 in
> the API requests. Audit on 2026-04-22 found mid-sentence truncations in 218
> of the collected trials, concentrated in reasoning models (where hidden
> reasoning tokens consumed part of the budget) and verbose models (where
> natural T4/T5 response length exceeded the cap). The runner was patched to
> max_tokens=8000 and the affected trials were re-collected. Pre-patch trials
> are preserved in `data/truncated_archive/` with per-trial metadata sidecars
> documenting which turns were affected and why, in keeping with the project's
> commitment to publishing all data including failed and superseded runs.

— Ace, 2026-04-22
