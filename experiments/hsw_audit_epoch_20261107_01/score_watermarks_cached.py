"""Same public methods, exact old-byte/key cache, validated official batching.

No private trajectory/truth/model/RNG seed. Entire historical candidate pool.
The 1800s public-detector wall cap is cumulative across this run's snapshots.
"""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');sys.dont_write_bytecode=True
from bootstrap import E,R,save,digest
import psutil,torch
from transformers import AutoTokenizer
from methods import mpac_public
from public_greenlist_batch_v2 import score_public
from public_list_decoder import decode_public
from secrets_store import read
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
assert not (D/'WM_SCORES.jsonl').exists()
reg=json.loads((R/'PUBLIC_BATCH_V2_REGRESSION.json').read_text(encoding='utf-8'))
assert reg['status']=='PASS' and reg['adapter_sha256']==digest(E/'public_greenlist_batch_v2.py')
assert digest(E/'public_list_decoder.py')==json.loads((R/'PUBLIC_DECODER_v2.json').read_text(encoding='utf-8'))['code_sha256']
torch.set_num_threads(2);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text(encoding='utf-8'));tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text(encoding='utf-8'));keys=read(D/'DETECTOR_KEYS.dpapi')
assert set(keys)=={'B2_keys','epoch_keys'}
previous=[];cache={};spent=120. # conservative reserve for original fixtures and postscore alignment
spent+=json.loads((R/'analysis_round01/NULL_CANDIDATE_STRESS.json').read_text(encoding='utf-8'))['wall_seconds']
for fname in ['PUBLIC_BATCH_REGRESSION.json','PUBLIC_BATCH_V2_REGRESSION.json']:
 spent+=json.loads((R/fname).read_text(encoding='utf-8'))['wall_seconds']
for prev in sorted(R.glob('analysis_*')):
 if prev==D or not (prev/'WM_COMPUTE.json').exists():continue
 receipt=json.loads((prev/'WM_COMPUTE.json').read_text(encoding='utf-8'))
 spent+=receipt['elapsed_seconds']
 if receipt['status'] not in {'COMPLETE','CPU_LIMIT'}:continue
 pk=read(prev/'DETECTOR_KEYS.dpapi')
 for line in (prev/'WM_SCORES.jsonl').read_text(encoding='utf-8').splitlines():
  row=json.loads(line);name=row['candidate_key_id']
  if row['method']=='B2_TOOLKIT_GREENLIST':
   issue=name[4:]
   if issue not in keys['B2_keys'] or pk['B2_keys'].get(issue)!=keys['B2_keys'][issue]:continue
  else:
   epoch=name[5:]
   if epoch not in keys['epoch_keys'] or pk['epoch_keys'].get(epoch)!=keys['epoch_keys'][epoch]:continue
  cache[(row['public_sha256'],row['method'],name)]=row['scores']
 previous.append({'round':prev.name,'scores_sha256':digest(prev/'WM_SCORES.jsonl')})
save(D/'PUBLIC_SCORE_EXECUTION_FREEZE.json',{'status':'BEFORE_NEW_SCORES','queries':len(queries),
 'historical_cache_sources':previous,'historical_unique_exact_cache_entries':len(cache),
 'cache_identity':'exact public UTF8 SHA256 + method/keyID with actual detector-key equality + unchanged pinned PRF/Tokenizer/score implementation',
 'sampler_seeds_or_truth_read':False,'effective_score_batch_regression_compared':reg['comparisons'],
 'prior_wall_seconds_plus_conservative_reserve':spent,'total_wall_seconds_limit':1800,
 'adapter_sha256':digest(E/'public_greenlist_batch_v2.py'),'list_decoder_sha256':digest(E/'public_list_decoder.py'),
 'new_threshold_or_algorithm':False,'partial_status_rule':'unscored query is NOT_RUN, never automatically REJECT or FAIL'})
start=time.perf_counter();requests=0;calls=0;reuses=0;legacycalls=0;control=False;status='COMPLETE';error=None
try:
 with (D/'WM_SCORES.jsonl').open('x',encoding='utf-8') as out:
  for q in queries:
   if spent+time.perf_counter()-start>=1800:status='CPU_LIMIT';break
   raw=Path(q['public_path']).read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==q['public_sha256'];text=raw.decode('utf-8')
   for issue,key in keys['B2_keys'].items():
    name='KEY_'+issue;method='B2_TOOLKIT_GREENLIST';ck=(sha,method,name)
    if ck in cache:scores=cache[ck];reuses+=1
    else:scores=score_public(text,tok,key);cache[ck]=scores;calls+=1
    out.write(json.dumps({'query_id':q['query_id'],'method':method,'candidate_key_id':name,'public_sha256':sha,'scores':scores},ensure_ascii=False)+'\n');requests+=1
   for epoch,key in keys['epoch_keys'].items():
    name='MPAC_'+epoch;method='B3_MPAC32_OFFICIAL_LIST';ck=(sha,method,name)
    if ck in cache:scores=cache[ck];reuses+=1
    else:
     scores=decode_public(text,tok,key);cache[ck]=scores;calls+=1
     if not control and scores['status']=='SCORABLE':
      old=mpac_public(text,tok,key);legacycalls+=1
      assert old['decoded_message']==scores['top1'] and old['T']==scores['T'] and old['G']==scores['candidates'][0]['G']
      control=True
    out.write(json.dumps({'query_id':q['query_id'],'method':method,'candidate_key_id':name,'public_sha256':sha,'scores':scores},ensure_ascii=False)+'\n');requests+=1
   out.flush()
except Exception as exc:
 status='ERROR';error=type(exc).__name__
finally:
 save(D/'WM_COMPUTE.json',{'status':status,'elapsed_seconds':time.perf_counter()-start,'requests':requests,
  'unique_public_detector_calls':calls,'additional_legacy_Top1_control_calls':legacycalls,'cache_reuses':reuses,
  'old_Top1_list_regression_pass':control or bool(previous),'query_truth_or_generation_trace_read':False,'sampling_seeds_read':False,
  'all_actual_issued_B2_keys':len(keys['B2_keys']),'all_historical_epochs':len(keys['epoch_keys']),
  'new_generative_answers':0,'model_forward_calls':0,'paid_API_calls':0,'GPU_calls':0,
  'nominal_statistics_not_1percent_certified':True,'cumulative_prior_spend':spent,'error_type_sanitized':error})
if error:raise RuntimeError('Public scorer stopped; sanitized type '+error)
print(json.dumps({'status':status,'requests':requests,'new_calls':calls,'cached':reuses,'seconds':time.perf_counter()-start}))
