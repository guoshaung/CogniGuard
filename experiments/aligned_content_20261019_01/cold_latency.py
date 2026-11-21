"""Selector-only cold-call comparison; shared token-count preparation excluded."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import sys,json,ast,time,copy
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;sys.path[:0]=[str(ROOT),str(P)]
import numpy as np
from transformers import AutoTokenizer
import aligned_selector as alg
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
O=P/'latency';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,indent=2),encoding='utf8')
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
save('protocol.json',{'status':'FROZEN_DEV_ONLY_COLD_SELECTOR_BENCHMARK','records':40,'rows':'first20 old dev per subject','repeats':1,'cache':'clear repaired selection result cache before every call; token-cost table prepared outside ALL timed calls','cost_scope':'selector plus exact final token consistency assert; excludes common token table construction, predictor/attacker fitting, model loading','why':'main run uses deterministic metadata memoization; its mixed-cache wall times are not fair speed rankings'})
tok=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True);old=ROOT/'experiments/strong_evidence_20261019_01';ns={};exec(compile((old/'mm/strict_select_enhanced.py.txt').read_text(encoding='utf8'),'<frozen>','exec'),ProfileSelector.select_enhanced.__globals__,ns);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':ns['select_enhanced']})
globals_={'alg':alg,'r':r,'tokenizer':tok,'selection_cache':{},'counter_cache':{},'Frozen':Frozen,'copy':copy,'json':json,'itertools':__import__('itertools')}
tree=ast.parse((P/'run_mm_v2.py').read_text(encoding='utf8'));nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['canonical','Counter','select']];exec(compile(ast.Module(body=nodes,type_ignores=[]),'<same-driver-functions>','exec'),globals_)
methods=json.loads((P/'protocol.json').read_text(encoding='utf8'))['methods'];cfg=json.loads((P/'mm_v2/selected_config_lock.json').read_text(encoding='utf8'))['selected'];times={m:[] for m in methods}
for subject,file,n in [('Math','student-mat.csv',395),('Portuguese','student-por.csv',649)]:
 data=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n);parts=json.loads((old/'mm'/(subject+'_split_LOCAL.json')).read_text(encoding='utf8'));mi=r.train_mi_order(data,np.array(parts['train']),20261019)
 for i in parts['dev'][:20]:
  p,t=(r.make_profile if subject=='Math' else make_portuguese_profile)(data[i],i);eligible=[x for x in p.profile_records if x.sensitivity<=.7];ids={x.record_id for x in eligible};key=(p.student_id,t.knowledge,tuple(sorted((k,str(data[i][k])) for k in ids)));globals_['counter_cache'][key]=globals_['Counter'](data[i],eligible)
  for method in methods:
   globals_['selection_cache'].clear();start=time.perf_counter();globals_['select'](method,data[i],p,t,mi,cfg);times[method].append(1000*(time.perf_counter()-start))
save('summary.json',[{'method':m,'n_calls':len(v),'mean_ms':float(np.mean(v)),'median_ms':float(np.median(v)),'p95_ms':float(np.quantile(v,.95))} for m,v in times.items()]);save('completion.json',{'status':'COMPLETED_DEV_PERFORMANCE_ONLY','calls':sum(len(v) for v in times.values()),'test_rows_used':0,'LLM_calls':0})
