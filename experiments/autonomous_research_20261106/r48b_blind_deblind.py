"""Open sealed map after validation; key supplied on stdin, never stored."""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

root = Path(__file__).parent
freeze = json.loads((root / 'r48b_blind_freeze.json').read_text(encoding='utf-8'))
output_raw = (root / 'r48b_blind_evaluator_output.json').read_bytes()
packet_raw = (root / 'r48b_blind_items.json').read_bytes()
sealed = (root / 'r48b_blind_key.aesgcm').read_bytes()
for name, data in [('output_sha256', output_raw), ('packet_sha256', packet_raw), ('sealed_sha256', sealed)]:
    assert hashlib.sha256(data).hexdigest() == freeze[name]
key = bytes.fromhex(sys.stdin.readline().strip())
assert len(key) == 32
mapping = json.loads(AESGCM(key).decrypt(sealed[:12], sealed[12:], b'r48b-blind-v1'))
output = json.loads(output_raw.decode('utf-8-sig'))
assert len(mapping) == len(output) == 70
assert set(mapping) == {r['case_id'] for r in output}
matrix = defaultdict(Counter)
reasons = Counter()
identified_cases = []
for row in output:
    ref = mapping[row['case_id']]
    human = ref['reference_label']
    decision = row['decision']
    matrix[human][decision] += 1
    if decision == 'YES' and human in {'NOT', 'PARTIAL'}:
        reasons['yes_human_negative'] += 1
    if decision == 'NO' and human in {'EXPLICIT', 'IMPLICIT'}:
        reasons['no_human_positive'] += 1
    if decision == 'UNSURE':
        reasons['unsure'] += 1
    if ref['blind_id'] == 'B015' and ref['element_id'] == 'K1':
        identified_cases.append({'id': 'B015-K1', 'human': human, 'evaluator': decision})
print(json.dumps({'n': len(output), 'human_by_evaluator': {k: dict(v) for k, v in sorted(matrix.items())},
                  'counts': dict(reasons), 'diagnostic_cases': identified_cases}, ensure_ascii=False, indent=2))
