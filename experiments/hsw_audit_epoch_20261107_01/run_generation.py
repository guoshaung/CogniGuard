"""Finite, exactly-once task executor. No detector calls, no output repair/retry."""
import argparse,datetime,hashlib,json,os,sys,time,traceback
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
from bootstrap import E,R,OLD,digest
for k,sub in [('HF_HOME','cache/hf'),('TORCH_HOME','cache/torch'),('TEMP','tmp'),('TMP','tmp')]:os.environ[k]=str(R/sub)
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import numpy as np
import psutil
import torch
from transformers import AutoTokenizer
from methods import Sampler
from native_proxy import NativeModel
from secrets_store import read
def put(p,o):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.partial');tmp.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');os.replace(tmp,p)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def log(o):
 with (R/'RUN_MANIFEST.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(o,ensure_ascii=False)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['probe','s2','s3','cal','reissue'],required=True);a=ap.parse_args()
 cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tasks=json.loads((R/'TASKS_FROZEN.json').read_text())
 gate=R/'GENERATION_CODE_FREEZE.json';frozen=json.loads(gate.read_text())
 for rel,expected in frozen['code'].items():assert digest(E/rel)==expected,'Generation code changed after admission'
 assert digest(R/'freeze.json')==frozen['input_freeze_sha256']
 ledger=R/'RUN_MANIFEST.jsonl';history=[json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
 started={r['task_id'] for r in history if r.get('event')=='STARTED'}
 attempts=len(started);tokens=sum(r.get('tokens',0) for r in history if r.get('event') in {'DELIVERED','TECH_FAIL'})
 spent=sum(r['wall_seconds'] for r in history if r.get('event')=='STAGE_EXIT')
 if a.phase=='probe':wanted=set(cfg['probe_tasks'])
 else:
  assert (R/'ADMISSION_PROBE.json').is_file(),'No formal followup before actual probe admission'
  admission=json.loads((R/'ADMISSION_PROBE.json').read_text());allowed=set(admission['methods_allowed'])
  stage={'s2':'S2','s3':'S3','cal':'CAL','reissue':'REISSUE'}[a.phase]
  if a.phase in {'s3','reissue'}:
   admission=json.loads((R/'ADMISSION_S2.json').read_text());allowed&=set(admission['methods_allowed'])
  wanted={t['task_id'] for t in tasks if t['stage']==stage and t['method'] in allowed}
 plan=[t for t in tasks if t['task_id'] in wanted and t['task_id'] not in started]
 if not plan:raise RuntimeError('No never-started planned slots; do not repeat')
 index=1
 while (R/f'generation_{a.phase}_{index:02}').exists():index+=1
 stage_dir=R/f'generation_{a.phase}_{index:02}';stage_dir.mkdir()
 torch.set_num_threads(2)
 psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
 secret=read(R/'private/RUN_SECRETS.dpapi')
 tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
 start=time.perf_counter();model=None;peak=0;loaded=0;delivered=0;newtokens=0;status='COMPLETE'
 try:
  if psutil.virtual_memory().available<6.5*2**30:raise MemoryError('Await >=6.5GiB freeRAM; never stop others')
  if spent>=cfg['model_wall_seconds_ceiling'] or attempts>=cfg['attempt_ceiling']:raise RuntimeError('Existing hard budget exhausted')
  model=NativeModel(Path(cfg['model_path']),R,2);loaded=time.perf_counter()-start
  put(stage_dir/'LOADED.json',{'controller_pid':os.getpid(),'owned_worker_pid':model.process.pid,'load_seconds':loaded,'GPU':False,'vocab':model.vocab})
  for task in plan:
   elapsed=time.perf_counter()-start
   if attempts>=cfg['attempt_ceiling'] or spent+elapsed>=cfg['model_wall_seconds_ceiling'] or tokens+newtokens>=cfg['generated_token_ceiling']:
    status='RESOURCE_LIMIT';break
   if sum(p.stat().st_size for p in R.rglob('*') if p.is_file())>=cfg['disk_ceiling_bytes']:status='DISK_LIMIT';break
   if psutil.virtual_memory().available<800*2**20:status='MEMORY_GUARD';break
   source=Path(task['source_path']).read_text(encoding='utf-8');assert hashlib.sha256(source.encode()).hexdigest()==task['source_sha256']
   messages=[{'role':'system','content':cfg['posthoc_system']},{'role':'user','content':cfg['posthoc_user_prefix']+source+cfg['posthoc_user_suffix']}]
   prefix=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
   assert len(prefix)+cfg['max_new_tokens']<=cfg['context']
   out=R/'raw'/task['task_id'];out.mkdir()
   log({'event':'STARTED','task_id':task['task_id'],'utc':now(),'phase':a.phase,'source_sha256':task['source_sha256']});attempts+=1
   put(out/'request.json',{'task':task,'messages':messages,'input_ids':prefix,'input_ids_sha256':hashlib.sha256(np.asarray(prefix,dtype='<i4').tobytes()).hexdigest(),
    'sampling_seed':'DPAPI secure local store; public commitment only','watermark_key':'DPAPI secure local store; key_id only','temperature':.8,'top_p':.95,'max_new_tokens':640,
    'model_identity_file':'MODEL_IDENTITY.json','code_freeze_sha256':digest(gate),'GPU':False,'HTTP_requests':0})
   key=secret['B2_keys'][task['issue_id']] if task['method']=='B2' else secret['epoch_keys'][task['epoch']] if task['method']=='B3' else 1
   torch.manual_seed(secret['sampling_seeds'][task['pair_id']])
   sampler=Sampler(tok,task['method'],key,task.get('message_code'))
   ids=[];rows=[];why='MAX_TOKENS';t=time.perf_counter()
   try:
    model.clear();raw=model.forward(prefix);hist=list(prefix);prefill=time.perf_counter()-t
    for step in range(cfg['max_new_tokens']):
     if spent+time.perf_counter()-start>=cfg['model_wall_seconds_ceiling']:why='WALL_LIMIT';status='RESOURCE_LIMIT';break
     if tokens+newtokens>=cfg['generated_token_ceiling']:why='TOKEN_LIMIT';status='RESOURCE_LIMIT';break
     if psutil.virtual_memory().available<800*2**20:why='MEMORY_GUARD';status='MEMORY_GUARD';break
     token,diag=sampler.select(raw,hist)
     if token>=len(tok):raise RuntimeError('Un-decodable padded head token selected; no replacement')
     ids.append(token);newtokens+=1
     rows.append({'step':step,'token_id':token,'history_sha256':hashlib.sha256(np.asarray(hist,dtype='<i4').tobytes()).hexdigest(),
      'raw_logits_finite':bool(np.isfinite(raw).all()),'raw_logits_sha256':hashlib.sha256(raw.tobytes()).hexdigest(),
      'method':task['method'],'key_id':task['key_id'],'diagnostic':diag})
     hist.append(token)
     try:peak=max(peak,psutil.Process(model.process.pid).memory_info().rss)
     except psutil.Error:pass
     if token in [151643,151645]:why='EOS';break
     raw=model.forward([token])
    text=tok.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False);b=text.encode('utf-8');(out/'public.txt').write_bytes(b)
    public_ids=tok.encode(text,add_special_tokens=False);visible=[x for x in ids if x not in tok.all_special_ids]
    put(out/'result.json',{'task_id':task['task_id'],'generated_ids':ids,'public_ids':public_ids,'generated_tokens':len(ids),
     'public_sha256':hashlib.sha256(b).hexdigest(),'A_bytes':b==tok.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False).encode('utf-8'),
     'B_ids_equal':public_ids==visible,'natural_EOS':why=='EOS','finish_reason':why,'prefill_seconds':prefill,'wall_seconds':time.perf_counter()-t,
     'model_calls_cumulative':model.calls,'raw_finite_all':all(x['raw_logits_finite'] for x in rows),'method':task['method'],
     'quality':'PENDING_LOCK_BEFORE_DETECTION','fidelity_review_not_external_gold':True})
    (out/'trace.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
    log({'event':'DELIVERED','task_id':task['task_id'],'tokens':len(ids),'finish_reason':why,'wall_seconds':time.perf_counter()-t,'utc':now()});delivered+=1
    print(json.dumps({'task':task['task_id'],'status':'DELIVERED','tokens':len(ids),'finish':why,'seconds':round(time.perf_counter()-t,3)}),flush=True)
    if status!='COMPLETE':break
   except Exception as e:
    put(out/'FAILURE.json',{'type':type(e).__name__,'message':str(e),'partial_ids':ids,'trace':rows,'failure_consumes_attempt':True})
    log({'event':'TECH_FAIL','task_id':task['task_id'],'tokens':len(ids),'type':type(e).__name__,'utc':now()})
    # One method failure does not launch retries. Remaining methods are checkpointed for independent execution.
    status='METHOD_FAILURE';break
 except Exception as e:
  status='ADMISSION_OR_STAGE_FAILURE';put(stage_dir/'FAILURE.json',{'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc(),'no_retry':True})
 finally:
  if model:model.close()
  receipt={'event':'STAGE_EXIT','phase':a.phase,'status':status,'wall_seconds':time.perf_counter()-start,'load_seconds':loaded,
   'actual_new_answer_attempts':attempts-len(started),'new_delivered':delivered,'new_tokens':newtokens,'peak_native_worker_RSS_bytes':peak,
   'own_worker_closed':True,'other_processes_stopped':False,'GPU_calls':0,'paid_API_calls':0,'utc':now()}
  put(stage_dir/'EXITED.json',receipt);log(receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
