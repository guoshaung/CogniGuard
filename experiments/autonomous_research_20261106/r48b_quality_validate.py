"""Development predictions only; do not open the sealed test partition."""
import hashlib
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).parent
items = json.loads((root / 'r48b_quality_dev.json').read_text(encoding='utf-8'))
raw = (root / 'r48b_quality_dev_predictions.json').read_bytes()
pred = json.loads(raw.decode('utf-8-sig'))
assert isinstance(pred, list) and len(items) == len(pred) == 28
items_by_id = {r['case_id']: r for r in items}
assert len(items_by_id) == len({r['case_id'] for r in pred}) == 28
assert set(items_by_id) == {r['case_id'] for r in pred}
for r in pred:
    assert set(r) == {'case_id', 'decision', 'evidence', 'reason'}
    assert r['decision'] in {'YES', 'NO', 'UNSURE'}
    assert isinstance(r['reason'], str) and r['reason'].strip()
    assert isinstance(r['evidence'], str)
    assert not r['evidence'] or r['evidence'] in items_by_id[r['case_id']]['answer']
    assert r['decision'] != 'YES' or r['evidence']
assert len({r['reason'] for r in pred}) == 28, 'exact duplicate reasons need manual procedure review'
print(json.dumps({'pairs': len(pred), 'decisions': dict(Counter(r['decision'] for r in pred)),
                  'nonempty_evidence': sum(bool(r['evidence']) for r in pred),
                  'prediction_sha256': hashlib.sha256(raw).hexdigest()}, indent=2))
