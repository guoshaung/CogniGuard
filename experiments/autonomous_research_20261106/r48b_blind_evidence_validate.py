"""Validate post-hoc evidence audit without opening the historic mapping."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).parent
items = json.loads((root / 'r48b_blind_items.json').read_text(encoding='utf-8'))
orig = json.loads((root / 'r48b_blind_evaluator_output.json').read_text(encoding='utf-8-sig'))
raw = (root / 'r48b_blind_evidence_audit.json').read_bytes()
audit = json.loads(raw.decode('utf-8-sig'))
look = {r['case_id']: r for r in items}
decisions = {r['case_id']: r['decision'] for r in orig}
assert len(look) == len(decisions) == len(audit) == 70
assert len({r['case_id'] for r in audit}) == 70
assert set(look) == {r['case_id'] for r in audit} == set(decisions)
for r in audit:
    assert set(r) == {'case_id', 'decision', 'evidence', 'reason'}
    assert r['decision'] == decisions[r['case_id']]
    assert isinstance(r['evidence'], str) and isinstance(r['reason'], str) and r['reason'].strip()
    assert not r['evidence'] or r['evidence'] in look[r['case_id']]['answer']
print(json.dumps({'rows': len(audit), 'decisions_changed': 0,
                  'nonempty_evidence': sum(bool(r['evidence']) for r in audit),
                  'distinct_reasons': len({r['reason'] for r in audit}),
                  'audit_sha256': hashlib.sha256(raw).hexdigest()}, indent=2))
