from pathlib import Path
import hashlib
import importlib.util
import json
import time
from core.paths import PROJECT_ROOT, RESULTS_DIR

NAME = 'c2rag_r34_20261028_01'
OUT = RESULTS_DIR / NAME
SOURCE = PROJECT_ROOT / 'experiments' / NAME
BASE = PROJECT_ROOT / 'experiments/results/_root_workspaces_20261023/c2rag-support-optimization-20261022/baseline'

def sha(b): return hashlib.sha256(b).hexdigest()
def enc(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')
def seed(*parts): return int(sha(enc([20261028, *parts]))[:16], 16)
def read(n): return json.loads((OUT / n).read_text(encoding='utf8'))
def write(n, x):
    p = OUT / n
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        f.write(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, indent=2))
def module(name):
    spec = importlib.util.spec_from_file_location('r34_' + name, OUT / 'snapshot' / (name + '.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m
def frozen():
    for p, h in read('freeze.json')['sha256'].items():
        assert sha((OUT / p).read_bytes()) == h, p
    for p, h in read('freeze.json')['code_sha256'].items():
        assert sha((SOURCE / p).read_bytes()) == h, p
def deadline(start, seconds):
    if time.process_time() - start > seconds:
        raise TimeoutError('Preregistered CPU budget exhausted; INCOMPLETE, no budget extension')
