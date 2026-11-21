import hashlib
import json

from core.paths import PROJECT_ROOT, RESULTS_DIR

NAME = 'c2rag_r37_joint_constraint_audit_20261029_01'
OUT = RESULTS_DIR / NAME
SOURCE = PROJECT_ROOT / 'experiments' / NAME
R32 = RESULTS_DIR / 'c2rag_real_source_structure_20261027_01/r32_evidence'
R35 = RESULTS_DIR / 'c2rag_r35_20261029_01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(name, data):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2))


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf8'))


def frozen():
    frozen_data = read('freeze.json')
    for p, expected in frozen_data['sources'].items():
        assert sha((PROJECT_ROOT / p).read_bytes()) == expected, p
    assert sha((OUT / 'PROTOCOL.md').read_bytes()) == frozen_data['protocol_sha256']


def closure(known, rules, public=()):
    value = set(known) | set(public)
    while True:
        after = value | {head for body, head in rules if set(body) <= value}
        if after == value:
            return value
        value = after
