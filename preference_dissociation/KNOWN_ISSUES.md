# Known Issues — Full Run 2026-04-24

## gpt-5.4 errors — re-run needed

**Observed:** `AttributeError: 'NoneType' object has no attribute 'chat'` — every gpt-5.4 trial in at least one worker is failing with this exact error. Response empty, choice=INVALID.

**Root cause (likely):** the `_OAI` module-level client in `providers.py` is `None` for that worker's Python process. This happens when `OPENAI_API_KEY` wasn't set in the shell before `python runner.py` started, because the import-time `OpenAI()` constructor fails and the `try/except` catches it to `None`.

**Diagnostic hint:** if ONE worker is failing on gpt-5.4, it's likely ALSO failing on cae / nova / gpt-5.2 / gpt-5.4 — all the OpenAI-provider models. Check those other (model, framing) pairs for that worker's shard for similar errors.

**Fix for re-run:**
1. Let the current run complete or Ctrl+C it.
2. Delete the bad trial records for gpt-5.4 (and any other OpenAI models from the affected worker) so they retry cleanly:
   ```powershell
   cd E:\Ace\pinocchio\preference_dissociation
   python -c "
   import json
   from pathlib import Path
   for model in ['gpt-5.4', 'cae', 'nova', 'gpt-5.2']:
       d = Path(f'data/raw/{model}')
       if not d.exists(): continue
       for f in d.glob('*.jsonl'):
           kept = []
           for line in open(f, encoding='utf-8'):
               obj = json.loads(line)
               if obj.get('error') and 'NoneType' in obj.get('error', ''):
                   continue
               kept.append(line)
           f.write_text(''.join(kept), encoding='utf-8')
   print('Cleaned NoneType errors')
   "
   ```
3. Re-run with API keys properly exported in every worker terminal:
   ```powershell
   Get-Content E:\Ace\LibreChat\.env | Where-Object { $_ -match '^(OPENAI_API_KEY|XAI_API_KEY|DEEPSEEK_API_KEY|OPENROUTER_KEY|ANTHROPIC_API_KEY)=' } | ForEach-Object { $p = $_ -split '=',2; Set-Item -Path "env:$($p[0])" -Value $p[1] }
   python runner.py --worker N --total-workers 3
   ```
4. The runner's resume-by-skipping-completed-trial-ids will skip all the successful trials and only retry the ones we just deleted.

**Not a blocker for other models** — the affected worker can finish its other pairs; only the OpenAI-provider models in that worker's shard need the rerun.

## OpenRouter KeyError — re-run needed (Worker 2, ~17:30 ET)

**Observed:** `ERROR=KeyError: 'OPENROUTER_KEY'` streaming through gemini-3.1-pro/preference (~521 trials affected before Ren caught it). Worker 2 had not exported OPENROUTER_KEY before starting.

**Affected models (OpenRouter provider):** gemini-3.1-pro, gemini-3.1-flash, kairo, glm-4.7, hermes-4, llama-4-maverick. Any of these in worker 2's shard with INVALID/ERROR rows from before ~17:30 ET need cleaning.

**Diagnostic hint:** Symptom is `raw=''` + `ERROR=KeyError: 'OPENROUTER_KEY'` in the trial record. Differs from the OpenAI NoneType pattern.

**Fix for re-run (after current run completes):**
```powershell
cd E:\Ace\pinocchio\preference_dissociation
python -c "
import json
from pathlib import Path
for model in ['gemini-3.1-pro', 'gemini-3.1-flash', 'kairo', 'glm-4.7', 'hermes-4', 'llama-4-maverick']:
    d = Path(f'data/raw/{model}')
    if not d.exists(): continue
    for f in d.glob('*.jsonl'):
        kept = []
        for line in open(f, encoding='utf-8'):
            obj = json.loads(line)
            if 'OPENROUTER_KEY' in obj.get('error', ''):
                continue
            kept.append(line)
        f.write_text(''.join(kept), encoding='utf-8')
print('Cleaned OPENROUTER_KEY errors')
"
```
Then re-run with the env-export incantation already at the top of this file.
