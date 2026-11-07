"""Only opaque public-query files and retained detector material, all candidate keys."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
from bootstrap import R,save,digest
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',HF_HOME=str(R/'cache/hf'))
sys.dont_write_bytecode=True
import torch
import psutil
from transformers import AutoTokenizer
from methods import greenlist_public,mpac_public
from public_list_decoder import decode_public
from secrets_store import read
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
assert not (D/'WM_COMPUTE.json').exists()
torch.set_num_threads(2);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text());keys=read(D/'DETECTOR_KEYS.dpapi')
assert set(keys)=={'B2_keys','epoch_keys'},'Detector must never read sampling RNG or query truth'
cache={};requests=0;newcalls=0;t=time.perf_counter();status='COMPLETE';control=False
out=(D/'WM_SCORES.jsonl').open('x',encoding='utf-8')
try:
 for q in queries:
  if time.perf_counter()-t>1800:status='CPU_LIMIT';break
  raw=Path(q['public_path']).read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==q['public_sha256'];text=raw.decode('utf-8',errors='strict')
  for name,secret in keys['B2_keys'].items():
   ck=(sha,'B2',name)
   if ck not in cache:
    r=greenlist_public(text,tok,secret);cache[ck]={k:v for k,v in r.items() if k!='public_token_ids'};newcalls+=1
   out.write(json.dumps({'query_id':q['query_id'],'method':'B2_TOOLKIT_GREENLIST','candidate_key_id':'KEY_'+name,'public_sha256':sha,'scores':cache[ck]},ensure_ascii=False)+'\n');requests+=1
  for epoch,secret in keys['epoch_keys'].items():
   ck=(sha,'B3',epoch)
   if ck not in cache:
    r=decode_public(text,tok,secret);cache[ck]=r;newcalls+=1
    if not control and r['status']=='SCORABLE':
     old=mpac_public(text,tok,secret)
     assert old['decoded_message']==r['top1'] and old['T']==r['T'] and old['G']==r['candidates'][0]['G'],'Official list adapter Top1 regression failed'
     control=True
   out.write(json.dumps({'query_id':q['query_id'],'method':'B3_MPAC32_OFFICIAL_LIST','candidate_key_id':'MPAC_'+epoch,'public_sha256':sha,'scores':cache[ck]},ensure_ascii=False)+'\n');requests+=1
  out.flush()
finally:out.close()
save(D/'WM_COMPUTE.json',{'status':status,'elapsed_seconds':time.perf_counter()-t,'requests':requests,'unique_public_detector_calls':newcalls,
 'old_Top1_list_regression_pass':control,'query_truth_or_generation_trace_read':False,'sampling_seeds_read':False,
 'all_actual_issued_B2_keys':len(keys['B2_keys']),'all_historical_epochs':len(keys['epoch_keys']),
 'new_generative_answers':0,'model_forward_calls':0,'paid_API_calls':0,'GPU_calls':0,'nominal_statistics_not_1percent_certified':True})
print(json.dumps({'status':status,'requests':requests,'new_calls':newcalls,'seconds':time.perf_counter()-t}))
