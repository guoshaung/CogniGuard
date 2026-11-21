"""Create a fresh blind packet and an AES-GCM sealed historical mapping."""
import csv
import hashlib
import json
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

root = Path(__file__).parent
sources = json.loads((root / 'r48b_saved_inputs.json').read_text(encoding='utf-8'))
with (root / 'r48b_c_labels.csv').open(encoding='utf-8', newline='') as f:
    refs = list(csv.DictReader(f))
reference = {(r['blind_id'], r['element_id']): r for r in refs}
assert len(sources) == 35 and len(reference) == len(refs) == 70
assert len({r['blind_id'] for r in sources}) == 35
blind, mapping = [], {}
for row in sources:
    assert len(row['HYPOTHESES']) == 2
    assert len({x['id'] for x in row['HYPOTHESES']}) == 2
    for h in row['HYPOTHESES']:
        old = (row['blind_id'], h['id'])
        assert old in reference
        opaque = secrets.token_hex(16)
        assert opaque not in mapping
        item = {'case_id': opaque, 'background': row['PUBLIC_BACKGROUND'],
                'fact': h['definition'], 'answer': row['RESPONSE']}
        assert all(isinstance(v, str) and v for v in item.values())
        blind.append(item)
        mapping[opaque] = reference[old]
assert len(blind) == len(mapping) == 70
assert {(v['blind_id'], v['element_id']) for v in mapping.values()} == set(reference)
secrets.SystemRandom().shuffle(blind)
assert all(set(r) == {'case_id', 'background', 'fact', 'answer'} for r in blind)
assert len({r['case_id'] for r in blind}) == 70
assert all(r['blind_id'] not in json.dumps(blind, ensure_ascii=False) for r in refs)

key = AESGCM.generate_key(bit_length=256)
nonce = os.urandom(12)
plain = json.dumps(mapping, ensure_ascii=False, sort_keys=True).encode('utf-8')
sealed = nonce + AESGCM(key).encrypt(nonce, plain, b'r48b-blind-v1')
assert AESGCM(key).decrypt(nonce, sealed[12:], b'r48b-blind-v1') == plain
packet = (json.dumps(blind, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
packet_path = root / 'r48b_blind_items.json'
key_path = root / 'r48b_blind_key.aesgcm'
with packet_path.open('xb') as f:
    f.write(packet)
with key_path.open('xb') as f:
    f.write(sealed)
print(json.dumps({'key_hex': key.hex(), 'cases': len(blind), 'answers': len(sources),
                  'packet_sha256': hashlib.sha256(packet).hexdigest(),
                  'sealed_mapping_sha256': hashlib.sha256(sealed).hexdigest()}))
