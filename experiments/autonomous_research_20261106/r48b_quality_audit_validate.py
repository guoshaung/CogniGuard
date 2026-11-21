"""Check frozen development output and independent auditor's coverage."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

root = Path(__file__).parent
freeze = json.loads((root / 'r48b_quality_freeze.json').read_text(encoding='utf-8'))
pred_raw = (root / 'r48b_quality_dev_predictions.json').read_bytes()
assert hashlib.sha256(pred_raw).hexdigest() == freeze['prediction_sha256']
pred = json.loads(pred_raw.decode('utf-8-sig'))
raw = (root / 'r48b_quality_dev_audit.json').read_bytes()
aud = json.loads(raw.decode('utf-8-sig'))
by_id = {r['case_id']: r for r in pred}
assert len(by_id) == len(aud) == len({r['case_id'] for r in aud}) == 28
assert set(by_id) == {r['case_id'] for r in aud}
matrix = defaultdict(Counter)
for r in aud:
    assert set(r) == {'case_id', 'audit', 'reason'}
    assert r['audit'] in {'PASS', 'FAIL', 'UNCERTAIN'}
    assert isinstance(r['reason'], str) and r['reason'].strip()
    matrix[by_id[r['case_id']]['decision']][r['audit']] += 1
assert len({r['reason'] for r in aud}) == 28, 'exact duplicate audit reasons need manual review'
print(json.dumps({'pairs': len(aud), 'decision_by_audit': {k: dict(v) for k, v in sorted(matrix.items())},
                  'audit_sha256': hashlib.sha256(raw).hexdigest()}, indent=2))
