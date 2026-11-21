"""Frozen synthetic field-necessity stress test, not real teaching quality."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import sys,json,copy,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.feature_selection import mutual_info_regression
from transformers import AutoTokenizer
from experiments.mmfopd_uci.runner import CONFIG
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
OUT=Path(__file__).parent/'mm_authored';OUT.mkdir(exist_ok=True)
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
methods=['FullProfile','NoProfile','SafeTaskTopK','TrainMI-SafeTopK','MM-Original','MM-TaskSlot']
fields={'prior_score':'mastery','recent_score':'mastery','practice_count':'behavior_aggregate','attendance':'behavior_aggregate','support_level':'educational_context','access_hours':'access_context','misconception_code':'error_pattern','format_choice':'preference','sensitive_flag':'sensitive_profile'}
templates=[('prior_score','recent_score','practice_count'),('recent_score','attendance','support_level'),('practice_count','access_hours','format_choice'),('prior_score','misconception_code','format_choice'),('attendance','support_level','access_hours'),('recent_score','practice_count','misconception_code'),('prior_score','support_level','format_choice'),('recent_score','access_hours','misconception_code'),('prior_score','recent_score','format_choice'),('attendance','misconception_code','format_choice')]
protocol={'status':'FROZEN_SYNTHETIC_HELDOUT_TASK_FAMILIES','methods':methods,'seed':20261019,'n':200,'train':120,'dev':20,'test':60,'split':'20 independently generated fictional profiles per task family; families0:6 train,6 dev,7:10 test','K':3,'necessary_gold':'the three operands needed by an authored weighted-score computation; task explicitly names operands','utility':'all required operands released = deterministic task solvability, not LLM teaching quality','MI':'train-only mutual_info_regression between safe field numeric values and authored computation target','limitations':'10 authored task families, only3 held-out; synthetic prior shared with author; no real student generalization; no human blind labels','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
if (OUT/'protocol.json').exists():raise RuntimeError('refuse overwrite')
save('protocol.json',protocol)
rng=np.random.default_rng(20261019);data=[]
for family,required in enumerate(templates):
 for j in range(20):
  vals={k:int(rng.integers(1,21)) for k in fields}; sensitive=int(rng.integers(0,2));vals['sensitive_flag']=sensitive
  vals['support_level']=int(rng.integers(1,6))+sensitive*10
  data.append({'id':f'fictional-{family}-{j}','family':family,'split':'train' if family<6 else 'dev' if family==6 else 'test','values':vals,'necessary':list(required),'target':sum((i+1)*vals[k] for i,k in enumerate(required))})
save('data.json',data)
safe=[k for k in fields if k!='sensitive_flag'];train=[d for d in data if d['split']=='train'];mi=mutual_info_regression(np.array([[d['values'][k] for k in safe] for d in train]),[d['target'] for d in train],random_state=20261019);order=[k for _,k in sorted(zip(mi,safe),reverse=True)]
tok=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
rows=[];started=time.perf_counter()
for d in data:
 records=[ProfileRecord(k,kind,'lesson',f'{k} {d["values"][k]}',1.,.9 if k=='sensitive_flag' else .3,'') for k,kind in fields.items()];profile=StudentProfile(d['id'],{},records)
 task=Task(d['id'],d['id'],'Compute the weighted lesson score from '+' '.join(d['necessary'])+'. Use exactly these three inputs.','lesson','computation',False)
 for method in methods:
  cfg=copy.deepcopy(CONFIG);cfg['fopd']['unit_budget']['allowed']=sorted(set(fields.values())-{'sensitive_profile'})
  if method=='FullProfile':chosen=set(fields)
  elif method=='NoProfile':chosen=set()
  elif method=='TrainMI-SafeTopK':chosen=set(order[:3])
  elif method=='SafeTaskTopK':chosen={x.record.record_id for x in ProfileSelector(cfg).score_records(profile,task) if x.record.sensitivity<=.7};chosen=set([x.record.record_id for x in ProfileSelector(cfg).score_records(profile,task) if x.record.record_id in chosen][:3])
  else:
   if method=='MM-TaskSlot':cfg['fopd']['unit_budget']['distinct_requested_types']=['mastery']
   picked=ProfileSelector(cfg).select(profile,task);chosen={x.record.record_id for x in picked}
   # Keep native overflow visible instead of silently fixing or rerunning it.
  need=set(d['necessary']);tp=len(chosen&need);precision=tp/len(chosen) if chosen else 0.;recall=tp/3
  rows.append({'id':d['id'],'family':d['family'],'split':d['split'],'method':method,'fields':sorted(chosen),'precision':precision,'recall':recall,'F1':2*precision*recall/(precision+recall) if precision+recall else 0.,'direct_exposure':int('sensitive_flag' in chosen),'budget_violation':method!='FullProfile' and len(chosen)>3,'task_solvable':int(need<=chosen),'tokens':len(tok.encode('\n'.join(f'{k}={d["values"][k]}' for k in sorted(chosen)),add_special_tokens=False))})
save('rows.json',rows);summary=[]
for method in methods:
 z=[x for x in rows if x['split']=='test' and x['method']==method];summary.append({'method':method,'n':len(z),**{k:float(np.mean([x[k] for x in z])) for k in ['precision','recall','F1','direct_exposure','task_solvable','tokens']},'budget_violations':sum(x['budget_violation'] for x in z)})
save('summary.json',summary);save('completion.json',{'status':'COMPLETED_SYNTHETIC_ONLY','wall_seconds':time.perf_counter()-started,'real_model_calls':0,'failures':0,'warning':'native selector budget overflows retained and disqualify affected arm from fair K3 claims','test_task_families':3,'CI':'no population CI: 3 deliberately chosen task families are insufficient for general inference'})
print(json.dumps(summary,indent=2))
