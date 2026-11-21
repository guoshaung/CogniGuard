"""Create grouped blind development input; seal unused groups and old IDs."""
import hashlib
import json
import os
import secrets
from collections import defaultdict
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

root = Path(__file__).parent
old = json.loads((root / 'r48b_blind_items.json').read_text(encoding='utf-8'))
groups = defaultdict(list)
for row in old:
    assert set(row) == {'case_id', 'background', 'fact', 'answer'}
    groups[row['background']].append(row)
assert len(groups) == 5 and all(len(x) == 14 for x in groups.values())
assert all(len({x['answer'] for x in group}) == 7 and len({x['fact'] for x in group}) == 2 for group in groups.values())
keys = list(groups)
secrets.SystemRandom().shuffle(keys)
dev_old = [r for k in keys[:2] for r in groups[k]]
test_old = [r for k in keys[2:] for r in groups[k]]
assert len(dev_old) == 28 and len(test_old) == 42
for field in ('background', 'answer', 'fact'):
    assert not ({x[field] for x in dev_old} & {x[field] for x in test_old})
mapping = {}
def anonymize(records):
    result = []
    for r in records:
        new_id = secrets.token_hex(16)
        assert new_id not in mapping
        mapping[new_id] = r['case_id']
        result.append({'case_id': new_id, 'background': r['background'], 'fact': r['fact'], 'answer': r['answer']})
    secrets.SystemRandom().shuffle(result)
    return result
dev, test = anonymize(dev_old), anonymize(test_old)
assert len(mapping) == 70
key = AESGCM.generate_key(bit_length=256)
nonce = os.urandom(12)
private = json.dumps({'test_items': test, 'old_id_mapping': mapping}, ensure_ascii=False).encode('utf-8')
sealed = nonce + AESGCM(key).encrypt(nonce, private, b'r48b-quality-gate-v1')
assert AESGCM(key).decrypt(nonce, sealed[12:], b'r48b-quality-gate-v1') == private
packet = (json.dumps(dev, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
with (root / 'r48b_quality_dev.json').open('xb') as f:
    f.write(packet)
with (root / 'r48b_quality_test.aesgcm').open('xb') as f:
    f.write(sealed)
print(json.dumps({'key_hex': key.hex(), 'development_pairs': len(dev), 'withheld_pairs': len(test),
                  'development_sha256': hashlib.sha256(packet).hexdigest(),
                  'withheld_sha256': hashlib.sha256(sealed).hexdigest()}))
