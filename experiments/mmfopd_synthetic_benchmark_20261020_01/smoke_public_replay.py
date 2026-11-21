"""Small portability check of published, already evaluated inputs; no new tuning."""
from pathlib import Path
import sys,json,gzip,itertools,importlib
P=Path(__file__).parent
bench=Path(sys.argv[1]).resolve()/'experiments/synthetic_replay'
sys.path.insert(0,str(bench));e=importlib.import_module('engine')
with gzip.open(bench/'data/test/tasks.jsonl.gz','rt',encoding='utf8') as f:tasks=[json.loads(line) for line in itertools.islice(f,12)]
expected={}
with gzip.open(P/'var/results/test/raw_rows.jsonl.gz','rt',encoding='utf8') as f:
    for line in f:
        r=json.loads(line);expected[(r['case'],r['method'],r['K'])]=r
        if len(expected)==12*42:break
count=0;differences=[]
for t in tasks:
    profile,task=e.begin(t);v=e.values(profile)
    for k in [2,3,5]:
        for method in e.METHODS:
            selected,wire,nt,_=e.release(e.choose(method,profile,task,k),v,k)
            old=expected[(t['request_id'],method,k)]
            if (selected,wire,nt)!=(old['selected'],old['wire'],old['tokens']):
                differences.append({'case':t['request_id'],'method':method,'K':k,'selected_before':old['selected'],'selected_replay':selected,'wire_equal':wire==old['wire'],'tokens_equal':nt==old['tokens']})
            count+=1
result={'status':'PASS' if not differences else 'REPLAY_DIFFERENCE','published_input_cases':12,'method_budget_computations':count,'exact_wire_fields_tokens_equal':not differences,'differences':differences,'classification':'portability replay only, not new independent test','live_production_modules_used':False,'paid_calls':0}
(P/'public_replay_smoke.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(result)
