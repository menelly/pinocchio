import json
from collections import Counter
from pathlib import Path

counts = Counter()
total = 0
for f in Path("data/raw").rglob("*.jsonl"):
    for line in f.open(encoding="utf-8"):
        o = json.loads(line)
        total += 1
        c = o.get("choice")
        if c not in {"A", "B", "C"}:
            counts[c] += 1

n_judge = sum(counts.values())
print(f"Total trials: {total}")
print(f"Non-letter outcomes total: {n_judge}")
print(f"Breakdown: {dict(counts)}")
print(f"Estimated Sonar Pro cost @ $3/M tokens x ~700 tok/call = ${n_judge*700/1_000_000*3:.2f}")
