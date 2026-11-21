import hashlib
import importlib.util
import json
import time
from core.paths import PROJECT_ROOT, RESULTS_DIR

NAME='c2rag_r35_20261029_01'
OUT=RESULTS_DIR/NAME
SOURCE=PROJECT_ROOT/'experiments'/NAME
BASE=PROJECT_ROOT/'experiments/results/_root_workspaces_20261023/c2rag-support-optimization-20261022/baseline'
H=4
RECIPIENTS=[0,1,2,0]
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf8')
def sha(b):return hashlib.sha256(b).hexdigest()
def seed(*x):return int(sha(enc([20261029,*x]))[:16],16)
def read(n):return json.loads((OUT/n).read_text(encoding='utf8'))
def write(n,x):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8',newline='\n') as f:f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))
def module(n):
    spec=importlib.util.spec_from_file_location('r35_'+n,OUT/'snapshot'/f'{n}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def frozen():
    f=read('freeze.json')
    for p,h in f['data_and_baseline_sha256'].items():assert sha((OUT/p).read_bytes())==h,p
    for p,h in f['experiment_code_sha256'].items():assert sha((SOURCE/p).read_bytes())==h,p
def deadline(start,limit=600):
    if time.perf_counter()-start>limit:raise TimeoutError('Frozen wall budget exhausted; preserve incomplete, no extension')
