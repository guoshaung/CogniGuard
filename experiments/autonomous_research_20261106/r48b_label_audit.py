"""Recount public derived R48b C labels; no generation or private text."""
import csv
import json
from collections import Counter
from pathlib import Path

path = Path(__file__).with_name('r48b_c_labels.csv')
with path.open(encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 70
assert len({(r['blind_id'], r['element_id']) for r in rows}) == 70
result = {'rows': len(rows), 'reference': dict(Counter(r['reference_label'] for r in rows))}
for name in ('S1', 'S2', 'DeepSeek', 'D1_hit'):
    result[name] = dict(sorted(Counter(r['reference_label'] + '->' + r[name] for r in rows).items()))
print(json.dumps(result, indent=2, sort_keys=True))
