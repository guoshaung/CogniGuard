"""Predeclared unused candidate pressure; one source, not 512 recipients."""
import hashlib,json,math,os,secrets,sys,time
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.dont_write_bytecode=True
from bootstrap import E,R,save,digest
from secrets_store import store,read
from methods import greenlist_public
import psutil,torch
from transformers import AutoTokenizer

D=R/'analysis_round01';out=D/'NULL_CANDIDATE_STRESS.json'
assert not out.exists()
torch.set_num_threads(2);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
source=next(s for s in json.loads((R/'inputs/DATA_MANIFEST_FROZEN.json').read_text()) if s['source_id']=='S01')
text=open(source['frozen_path'],encoding='utf-8').read();ids=tok.encode(text,add_special_tokens=False)
queries=[('FULL',text),('START50',tok.decode(ids[:52],skip_special_tokens=True,clean_up_tokenization_spaces=False))]
private=R/'private/NULL_DETECTOR_KEYS.dpapi';assert not private.exists()
values=[]
while len(values)<512:
 k=secrets.randbelow(2**31-1)+1
 if k not in values:values.append(k)
codes=[]
while len(codes)<512:
 c=format(secrets.randbits(32),'032b')
 if c not in codes:codes.append(c)
store(private,{'null_keys':values})
save(D/'NULL_STRESS_FREEZE.json',{'status':'BEFORE_NEW_NULL_CANDIDATE_SCORES','candidate_counts':[1,8,32,128,512],
 'queries':[{'variant':n,'public_sha256':hashlib.sha256(t.encode()).hexdigest()} for n,t in queries],
 'key_commitments':[hashlib.sha256(str(v).encode()).hexdigest() for v in values],'unused_public_codes':codes,
 'CPU_wall_seconds_limit':240,'new_generation':0,'same_root_failure_retry':0,
 'original_parameters_unchanged':True,'single_nominal_p':.01,'family_nominal_p':'.01/(candidate_count*13)',
 'calibrated_primary':'INFINITY_N2; NOT_CERTIFIED','independent_background_chapters':1,
 'candidate_pressure_not_actual_issued_population':True,'code_sha256':digest(E/'null_candidate_stress.py')})
t0=time.perf_counter();raw=[];limit=False
with (D/'NULL_STRESS_SCORES.jsonl').open('x',encoding='utf-8') as f:
 for index,key in enumerate(values):
  if time.perf_counter()-t0>240:limit=True;break
  for name,text in queries:
   s=greenlist_public(text,tok,key)
   r={'variant':name,'null_key_index':index,'nominal_p':s.get('p_value'),'T':s.get('scoring_tokens'),'G':s.get('score_sum'),'status':s['status']}
   raw.append(r);f.write(json.dumps(r)+'\n')
  f.flush()
complete_keys=len(raw)//2;summary=[]
for K in [1,8,32,128,512]:
 if K>complete_keys:summary.append({'candidate_count':K,'status':'NOT_RUN_CPU_LIMIT'});continue
 per=[]
 for name,_ in queries:
  ps=[r['nominal_p'] for r in raw if r['variant']==name and r['null_key_index']<K and r['nominal_p'] is not None]
  per.append({'variant':name,'any_uncorrected_p_lt_0_01':any(p<.01 for p in ps),'uncorrected_positive_keys':sum(p<.01 for p in ps),
   'any_nominal_Bonferroni_13views':any(p<.01/(K*13) for p in ps),'smallest_nominal_p':min(ps),
   'primary_calibrated_accept':'REJECT_UNCERTIFIED','independent_texts_not_K':True})
 summary.append({'candidate_count':K,'status':'COMPLETE','per_view':per,'source_any_nominal_false_accept':any(p['any_uncorrected_p_lt_0_01'] for p in per)})
save(out,{'status':'CPU_LIMIT' if limit else 'COMPLETE','detector_calls':len(raw),'wall_seconds':time.perf_counter()-t0,
 'actual_issued_null_resources':0,'independent_source_chapters':1,'public_views':2,'candidate_results':summary,
 'empirical_family_FPR_estimate':'NOT_ESTIMABLE; one reused DEV source, correlated views and nested null-key sets',
 'new_model_or_API_calls':0,'secret_values_published':False})
print(json.dumps({'status':'NULL_STRESS_SAVED','calls':len(raw),'seconds':time.perf_counter()-t0}))
