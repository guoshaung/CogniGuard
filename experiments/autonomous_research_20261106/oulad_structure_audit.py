"""Audit development-only availability signatures, emitting aggregates only."""
import hashlib
import json
from collections import Counter
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'oulad_dynamic_20261019_01/dev_data/snapshots_LOCAL.json'
raw = source.read_bytes()
rows = json.loads(raw)
train = [r for r in rows if r['split'] == 'train']
dev = [r for r in rows if r['split'] == 'dev']
assert len(train) == 1337 and len(dev) == 473

def key(r, level):
    missing = tuple(sorted(k for k, v in r['values'].items() if v is None))
    if level == 'missing':
        return missing
    if level == 'module_cutoff':
        return r['module'], r['cutoff']
    return r['module'], r['cutoff'], missing

result = {'source_sha256': hashlib.sha256(raw).hexdigest(), 'train_rows': len(train), 'dev_rows': len(dev)}
for level in ('missing', 'module_cutoff', 'combined'):
    seen = {key(r, level) for r in train}
    counts = Counter(key(r, level) for r in dev)
    result[level] = {'train_keys': len(seen), 'dev_keys': len(counts),
                     'dev_rows_in_train_keys': sum(n for k, n in counts.items() if k in seen),
                     'dev_unseen_keys': sum(1 for k in counts if k not in seen)}
result['dev_target_observed'] = dict(Counter(str(r['target_observed']) for r in dev))
print(json.dumps(result, indent=2, sort_keys=True))
