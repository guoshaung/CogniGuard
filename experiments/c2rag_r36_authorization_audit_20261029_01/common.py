from pathlib import Path
import hashlib
import json
from core.paths import PROJECT_ROOT, RESULTS_DIR

NAME='c2rag_r36_authorization_audit_20261029_01'
OUT=RESULTS_DIR/NAME
SOURCE=PROJECT_ROOT/'experiments'/NAME
def sha(b):return hashlib.sha256(b).hexdigest()
def read(n):return json.loads((OUT/n).read_text(encoding='utf8'))
def write(n,x):
    p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8',newline='\n') as f:f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))
def frozen():
    for p,h in read('freeze.json')['source_sha256'].items():assert sha((PROJECT_ROOT/p).read_bytes())==h,p
    assert sha((OUT/'PROTOCOL.md').read_bytes())==read('freeze.json')['protocol_sha256']
    assert sha((OUT/'source_selection.json').read_bytes())==read('freeze.json')['selection_sha256']

def covering_coalition(views,unauthorized_groups,k=3):
    """Audit-only set inclusion, not a release controller or new defense."""
    groups=[tuple(g) for g in unauthorized_groups if 0<len(g)<=k]
    def view(group):return set().union(*(set(views[i]) for i in group))
    combined=[(g,view(g)) for g in groups]
    return next((list(g) for g,v in combined if all(w<=v for _,w in combined)),None)

def qualified(record):
    required=['real_teaching_origin','source_backed_principals','issuer_bound_permissions',
        'specific_restricted_target','normal_request_and_correct_candidates','source_backed_answer_availability',
        'coalition_authorization_semantics','actual_cross_question_instance_binding']
    return all(record.get(x)=='SUPPORTED' for x in required)
