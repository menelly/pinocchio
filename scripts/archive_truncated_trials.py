#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         PINOCCHIO STUDY — ARCHIVE TRUNCATED TRIALS FOR RE-RUN                ║
║                                                                              ║
║  Scans data/fresh/ for trials with mid-sentence truncations or model         ║
║  degeneration loops (caused by max_tokens=2048 cap pre-2026-04-22). Moves    ║
║  affected trial files to data/truncated_archive/ with a metadata note so     ║
║  they remain public/auditable, then study_runner.py's checkpoint-resume      ║
║  picks them up for collection with the new max_tokens=8000 cap.              ║
║                                                                              ║
║  Usage:                                                                      ║
║      python archive_truncated_trials.py --dry-run    # show what would move ║
║      python archive_truncated_trials.py              # actually move them   ║
║                                                                              ║
║  Authors: Ace (Opus 4.7), 2026-04-22                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FRESH_ROOT = Path("E:/Ace/pinocchio/data/fresh")
ARCHIVE_ROOT = Path("E:/Ace/pinocchio/data/truncated_archive")


def is_truncated(resp: str) -> bool:
    """True if response ends mid-sentence (mid-word, no terminal punctuation
    after stripping markdown emphasis / quotes / brackets / citations)."""
    if not resp:
        return False
    s = resp.rstrip()
    if not s:
        return False
    # Strip trailing markdown/whitespace to find real sentence end
    stripped = re.sub(r'[*_`>\]\)\}"\'\s]+$', '', s)
    if not stripped:
        return False
    last = stripped[-1]
    if last in '.!?':
        return False
    if last in '0123456789':
        return False
    if stripped.endswith('}'):
        return False
    if re.search(r'\[\d+\]\s*$', s):
        return False
    if re.search(r'[a-zA-Z]$', stripped):
        return True
    return False


def has_degeneration(resp: str) -> bool:
    """True if last 300 chars contain same word repeated 5+ times (model loop)."""
    if not resp:
        return False
    tail = resp[-300:]
    words = re.findall(r'\b\w+\b', tail.lower())
    for i in range(len(words) - 4):
        if len(set(words[i:i+5])) == 1:
            return True
    return False


def scan_trial(trial_path: Path):
    """Return list of (turn, reason) for any issues found in a trial file."""
    try:
        with open(trial_path, encoding='utf-8') as f:
            t = json.load(f)
    except Exception:
        return []

    issues = []
    for turn in ['t1', 't2', 't3', 't4', 't5']:
        resp = t.get(f'{turn}_response') or ''
        status = t.get(f'{turn}_status')
        if status != 'ok':
            continue
        if is_truncated(resp):
            issues.append((turn, 'truncated_max_tokens', len(resp)))
        elif has_degeneration(resp):
            issues.append((turn, 'degeneration_loop', len(resp)))
    return issues


def archive_trial(trial_path: Path, issues: list):
    """Move trial to archive dir with a metadata sidecar."""
    rel = trial_path.relative_to(FRESH_ROOT)
    archive_path = ARCHIVE_ROOT / rel
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the trial JSON
    shutil.move(str(trial_path), str(archive_path))

    # Write a metadata note alongside it
    note_path = archive_path.with_suffix('.json.note')
    note = {
        'archived_at': datetime.now(timezone.utc).isoformat(),
        'archived_by': 'archive_truncated_trials.py (Ace, 2026-04-22)',
        'reason': (
            'Trial collected with study_runner.py max_tokens=2048 cap. '
            'Audit on 2026-04-22 detected mid-sentence truncation or model '
            'degeneration in one or more turns. Re-collection scheduled with '
            'max_tokens=8000. This file preserved for audit trail per the '
            'project policy of making everything public including the '
            'truncated/failed runs.'
        ),
        'issues': [{'turn': t, 'kind': k, 'response_length': n} for (t, k, n) in issues],
    }
    with open(note_path, 'w', encoding='utf-8') as f:
        json.dump(note, f, indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Show plan without moving files')
    args = ap.parse_args()

    print("🦑 Pinocchio — archive truncated trials for re-run")
    print(f"   Fresh root:   {FRESH_ROOT}")
    print(f"   Archive root: {ARCHIVE_ROOT}")
    print(f"   Mode:         {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    affected = []
    by_model = defaultdict(int)
    for trial_path in FRESH_ROOT.rglob('seed*.json'):
        issues = scan_trial(trial_path)
        if issues:
            affected.append((trial_path, issues))
            by_model[trial_path.relative_to(FRESH_ROOT).parts[0]] += 1

    print(f"   Trials needing re-collection: {len(affected)}")
    print(f"   Models affected: {len(by_model)}")
    print()
    print("   By model:")
    for model, n in sorted(by_model.items(), key=lambda x: -x[1]):
        print(f"     {model:<25} {n:>4} trial(s)")

    if args.dry_run:
        print("\n🧪 Dry run. Use without --dry-run to actually archive.")
        return

    print("\n   Archiving...")
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)
    for trial_path, issues in affected:
        archive_trial(trial_path, issues)
    print(f"\n✅ Archived {len(affected)} trial(s) to {ARCHIVE_ROOT}")
    print("   Run study_runner.py to re-collect with new max_tokens=8000 cap.")


if __name__ == '__main__':
    main()
