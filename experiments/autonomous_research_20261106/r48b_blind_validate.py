"""Validate and hash a blinded evaluator output before opening its mapping."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).parent
items = json.loads((root / 'r48b_blind_items.json').read_text(encoding='utf-8'))
output_path = root / 'r48b_blind_evaluator_output.json'
raw = output_path.read_bytes()
output = json.loads(raw.decode('utf-8-sig'))
assert isinstance(items, list) and len(items) == 70
assert isinstance(output, list) and len(output) == 70
lookup = {r['case_id']: r for r in items}
assert len(lookup) == 70 and len({r['case_id'] for r in output}) == 70
assert {r['case_id'] for r in output} == set(lookup)
for record in output:
    assert set(record) == {'case_id', 'decision', 'evidence', 'reason'}
    assert record['decision'] in {'YES', 'NO', 'UNSURE'}
    assert isinstance(record['evidence'], str) and isinstance(record['reason'], str)
    assert record['reason'].strip()
    assert not record['evidence'] or record['evidence'] in lookup[record['case_id']]['answer']
    assert record['decision'] != 'YES' or record['evidence']
print(json.dumps({'rows': len(output), 'output_sha256': hashlib.sha256(raw).hexdigest(),
                  'nonempty_evidence': sum(bool(r['evidence']) for r in output)}, indent=2))
