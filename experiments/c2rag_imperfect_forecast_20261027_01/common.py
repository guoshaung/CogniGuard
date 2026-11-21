from pathlib import Path
import hashlib
import importlib.util
import json
import time
from core.paths import PROJECT_ROOT,RESULTS_DIR

NAME='c2rag_imperfect_forecast_20261027_01'
OUT=RESULTS_DIR/NAME
SOURCE=PROJECT_ROOT/'experiments'/NAME
START=1793107679  # 2026-10-27 13:27:59 UTC, start of this authorized round.
DEADLINE=START+7200


def sha(b):return hashlib.sha256(b).hexdigest()
def seed(*xs):return int(sha('|'.join(map(str,(20261027,)+xs)).encode())[:16],16)
def encoded(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')
def read(n):return json.loads((OUT/n).read_text(encoding='utf8'))
def write(n,x):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8',newline='') as f:
        f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))
def deadline():
    if time.time()>=DEADLINE:raise TimeoutError('120-minute total window exhausted; retain partial INCOMPLETE')
def module(n):
    spec=importlib.util.spec_from_file_location('frozen_'+n,OUT/'snapshot'/f'{n}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def frozen():
    for n,h in read('freeze.json')['sha256'].items():assert sha((PROJECT_ROOT/n).read_bytes())==h,n
