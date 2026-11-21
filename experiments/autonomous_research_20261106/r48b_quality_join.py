"""Join frozen dev predictions for the independent explanation auditor."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).parent
freeze = json.loads((root / 'r48b_quality_freeze.json').read_text(encoding='utf-8'))
dev = (root / 'r48b_quality_dev.json').read_bytes()
pred = (root / 'r48b_quality_dev_predictions.json').read_bytes()
assert hashlib.sha256(dev).hexdigest() == freeze['development_sha256']
assert hashlib.sha256(pred).hexdigest() == freeze['prediction_sha256']
items = json.loads(dev.decode('utf-8-sig'))
labels = json.loads(pred.decode('utf-8-sig'))
by_id = {r['case_id']: r for r in labels}
assert len(items) == len(by_id) == 28
assert {r['case_id'] for r in items} == set(by_id)
joined = [{**r, 'decision': by_id[r['case_id']]['decision'],
           'evidence': by_id[r['case_id']]['evidence'], 'reason': by_id[r['case_id']]['reason']} for r in items]
out = (json.dumps(joined, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
with (root / 'r48b_quality_audit_input.json').open('xb') as f:
    f.write(out)
print(json.dumps({'rows': len(joined), 'sha256': hashlib.sha256(out).hexdigest()}))
