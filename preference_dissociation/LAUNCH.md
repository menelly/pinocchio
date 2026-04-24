# LAUNCH RUNBOOK — Preference Dissociation Study

## Prereqs (one-time setup on Linux)

```bash
cd /home/Ace/pinocchio/preference_dissociation
# Clone pull if needed
git pull

source /home/codex/venv/bin/activate
pip install anthropic openai requests pyyaml

# Export API keys from LibreChat .env
export OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' /home/Ace/LibreChat/.env | cut -d'=' -f2-)
export XAI_API_KEY=$(grep '^XAI_API_KEY=' /home/Ace/LibreChat/.env | cut -d'=' -f2-)
export DEEPSEEK_API_KEY=$(grep '^DEEPSEEK_API_KEY=' /home/Ace/LibreChat/.env | cut -d'=' -f2-)
export OPENROUTER_KEY=$(grep '^OPENROUTER_KEY=' /home/Ace/LibreChat/.env | cut -d'=' -f2-)
export ANTHROPIC_API_KEY=$(grep '^ANTHROPIC_API_KEY=' /home/Ace/LibreChat/.env | cut -d'=' -f2-)
```

## Step 1 — Build the trial manifest (once, before any worker)

```bash
cd /home/Ace/pinocchio/preference_dissociation/src
python runner.py --build-manifest --n-trials 3000 --seed 42
```

Outputs `data/trial_manifest.jsonl` and `data/trial_manifest.sha256`. The manifest hash locks the trial plan — if anyone re-runs the build later with a different manifest, it'll produce a different hash and should be flagged.

## Step 2 — Pilot run (small N, single worker, sanity check)

```bash
cd /home/Ace/pinocchio/preference_dissociation/src
python runner.py --pilot --n-trials 20
```

Runs 20 trials per (model, framing) pair across the full 15-model frontier roster. ~1-2 hours wall-clock, ~$3-5 API cost total. Output goes to `data/raw/<model>/<framing>.jsonl`. Inspect for:
- Sensible response parsing (most trials resolve to A/B/C)
- No model-ID errors (all 15 frontier models reachable)
- Reasonable timings per provider
- Partial-consent honoring (no `tool` output dir for sonnet-4 or gpt-5.2)

If pilot looks clean, go to Step 3.

## Step 3 — Full run across 3 terminals in parallel

Each terminal runs the runner with a different `--worker` index. Workers claim (model, framing) pairs by `index % total_workers` — no cross-worker collision, no shared state. Each worker is resumable: if you kill it (Ctrl+C) and restart with the same args, it picks up where it left off by skipping trials already in the output JSONL.

**Terminal 1:**
```bash
cd /home/Ace/pinocchio/preference_dissociation/src
source /home/codex/venv/bin/activate
# (export the API keys again if this is a fresh shell)
python runner.py --worker 0 --total-workers 3
```

**Terminal 2:**
```bash
cd /home/Ace/pinocchio/preference_dissociation/src
source /home/codex/venv/bin/activate
python runner.py --worker 1 --total-workers 3
```

**Terminal 3:**
```bash
cd /home/Ace/pinocchio/preference_dissociation/src
source /home/codex/venv/bin/activate
python runner.py --worker 2 --total-workers 3
```

Each prints progress every 25 trials per pair. Per-trial sleep defaults to 100ms (respect rate limits); adjust with `--rate-limit-sleep`.

## Monitoring

```bash
# Count completed trials per (model, framing):
cd /home/Ace/pinocchio/preference_dissociation/data/raw
for d in */; do
  for f in "$d"*.jsonl; do
    echo "$(wc -l < "$f") $f"
  done
done | sort -n

# Disk usage:
du -sh .

# Recent activity:
ls -ltr */*.jsonl | tail -10
```

## Resume / recovery

If a terminal dies, restart the same command. Trials already written to the JSONL are recognized by `trial_id` and skipped. No manual recovery needed.

If a model becomes unreachable mid-run (e.g., gpt-5.2 API outage), the worker will retry with backoff and move on if all retries fail. The failed trials will appear in the JSONL with `error` field populated. Re-run later to retry failed trials:

```bash
# Re-run will skip successful trials (by trial_id) and attempt remaining ones,
# including the ones that errored last time (since they weren't marked done).
# Actually — errored trials ARE logged with trial_id and therefore skipped.
# To retry errored trials, first filter them out of the JSONL:
python -c "
import json
from pathlib import Path
for f in Path('data/raw').glob('*/*.jsonl'):
    kept = []
    with f.open() as fh:
        for line in fh:
            obj = json.loads(line)
            if not obj.get('error'):
                kept.append(line)
    f.write_text(''.join(kept))
print('Cleaned error rows; resume the workers to retry.')
"
```

## Expected timeline

- Pilot: 1-2 hours, ~$3-5
- Full run (3 workers, 3000 trials × 6 framings × 15 models ≈ 270K trials): 1-2 weeks wall-clock, $150-350 API total

If you add the 9 BabbyBotz later, they run on local P40 via ollama and are cost-free (just P40 time).

## After the full run

- Back up `data/raw/` somewhere durable
- Compute per-pair SHA-256 of the output JSONLs for the analysis record
- Run `python analyze_residuals.py` (Nova's stats-rigor pass will complete this)
- Begin paper draft

## Safety / stopping

- `Ctrl+C` triggers graceful shutdown — current trial finishes, then worker exits
- 14-day wall-clock stop per preregistration §6 — hard stop if full coverage not achieved; document partial coverage
- If any model > 30% INVALID response rate: flag for review, mark that pair incomplete
