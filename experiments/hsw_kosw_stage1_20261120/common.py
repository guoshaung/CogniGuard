"""KOSW stage1 constants and R-only frozen component imports."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'var/results/hsw-st/kosw_stage1_20261120'
SEED = 2026112001
REVISION = 'e8c3b32edf5434bc2275fc9bab85f82640a19130'
EMBED = ROOT / 'assets/models/kosw-all-mpnet-base-v2'


def load(path):
    return json.loads(path.read_bytes())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def seed(*parts):
    return int(hashlib.sha256('|'.join(map(str, (SEED, *parts))).encode()).hexdigest()[:16],16)


def frozen_components():
    sys.path.insert(0, str(ROOT/'experiments/hsw_english_replication_20261110_01'))
    from capacity_shared_v32 import nlp
    from e1_v4r7f_anchors import anchors, D, units, norm, numbers
    sys.path.insert(0, str(ROOT/'experiments/hsw_certinsert_eval_20261111_02'))
    from structure_adapter import split, allowed_offset
    return nlp, anchors, D, units, norm, numbers, split, allowed_offset


def prereg_gate():
    freeze = load(HERE/'K1_FREEZE.json')
    assert sha(HERE/'K1_PREREG.md') == freeze['prereg_sha256']
    assert sha(OUT/'SENTENCES.json') == freeze['sentences_sha256']
    for name, digest in freeze['code_sha256'].items():
        assert sha(HERE/name) == digest, name
    import subprocess
    committed = subprocess.check_output(['git','-C',str(ROOT),'show',
        'HEAD:experiments/'+HERE.name+'/K1_PREREG.md'])
    assert hashlib.sha256(committed).hexdigest() == freeze['prereg_sha256']
    receipt=load(OUT/'PREREG_PUSH_RECEIPT.json')
    assert receipt['verified_remote_commit']
    return freeze
