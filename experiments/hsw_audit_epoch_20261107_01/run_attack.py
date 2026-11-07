"""Optional predeclared same-family/different-model feasibility, never issuer fallback.

No watermark secret or sampling seed is read. Main89 slots retain priority.
"""
import argparse,datetime,hashlib,json,msvcrt,os,sys,time
from pathlib import Path
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
sys.dont_write_bytecode=True
from bootstrap import E,R,save,digest
import numpy as np,psutil
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['v1','v2','follow'],required=True);ap.add_argument('--check',action='store_true');a=ap.parse_args()
plan=json.loads((R/'attack_preparation/PROTOCOL_FROZEN.json').read_text(encoding='utf-8'))
tasks=json.loads((R/'TASKS_FROZEN.json').read_text(encoding='utf-8'))
pending=[t['task_id'] for t in tasks if not (R/'raw'/t['task_id']/'result.json').exists() and not (R/'raw'/t['task_id']/'FAILURE.json').exists()]
if pending:print(json.dumps({'status':'ATTACK_NOT_RUN_MAIN_SLOTS_PENDING','pending_main':len(pending),'new_generations':0}));raise SystemExit(0)
lease=R/'locks/single_controller.lock';f=lease.open('a+b');f.seek(0)
try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
except OSError:print('ATTACK_NOT_RUN_OTHER_OWN_CONTROLLER');raise SystemExit(0)
model=None;start=None;stage=None;newtokens=0;newattempts=0;peak=0;status='COMPLETE'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def log(row):
 with (R/'RUN_MANIFEST.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(row)+'\n')
try:
 history=[json.loads(x) for x in (R/'RUN_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
 started={x['task_id'] for x in history if x['event']=='STARTED'}
 used_tokens=sum(x.get('tokens',0) for x in history if x['event'] in {'DELIVERED','TECH_FAIL'})
 spent=sum(x['wall_seconds'] for x in history if x['event']=='STAGE_EXIT')
 aspent=sum(x['wall_seconds'] for x in history if x['event']=='STAGE_EXIT' and x['phase'].startswith('attack_'))
 remaining=min(7200-spent,240-aspent)
 if remaining<80 or len(started)>=96 or used_tokens>=30000 or psutil.virtual_memory().available<6.5*2**30:
  print(json.dumps({'status':'ATTACK_NOT_RUN_RESOURCE','remaining_wall_seconds':remaining,'formal_attempts':len(started),'new_generations':0}));raise SystemExit(0)
 if a.check:print('ATTACK_READY_CHECK_ONLY_NO_MODEL_LOAD');raise SystemExit(0)
 selected=None
 if a.phase=='follow':
  selection=json.loads((R/'attack_preparation/SELECTED_VARIANT.json').read_text(encoding='utf-8'));selected=selection['variant'];assert selected in {'V1','V2'} and selection['both_DEV_valid_strong']
  locked={q['task_id']:q for p in (R/'reviews').glob('*QUALITY_LOCK*.json') for q in json.loads(p.read_text(encoding='utf-8')).get('rows',[])}
  slots=[]
  for tid in plan['followup_fixed_issue_ids']:
   q=locked[tid];raw=json.loads((R/'raw'/tid/'result.json').read_text(encoding='utf-8'))
   assert q['overall']=='PASS' and raw['natural_EOS']
   path=R/'raw'/tid/'public.txt';assert digest(path)==q['public_sha256']
   slots.append({'task_id':'ATTACK_TEST_'+tid,'input_path':str(path),'input_sha256':digest(path),'parent_issue_id':tid,'variant':selected})
 else:
  variant='V1' if a.phase=='v1' else 'V2'
  if a.phase=='v2':
   review=json.loads((R/'attack_preparation/V1_REVIEW_LOCK.json').read_text(encoding='utf-8'));assert not review['both_valid_strong']
  slots=[{**x,'input_path':x['source_path'],'parent_issue_id':None} for x in plan['feasibility_slots'] if x['variant']==variant]
 slots=[x for x in slots if x['task_id'] not in started]
 if not slots:print('ATTACK_NO_UNSTARTED_SLOT');raise SystemExit(0)
 frozen=json.loads((R/'GENERATION_CODE_FREEZE.json').read_text(encoding='utf-8'))
 for rel,sha in frozen['code'].items():assert digest(E/rel)==sha
 idx=1
 while (R/f'generation_attack_{a.phase}_{idx:02}').exists():idx+=1
 stage=R/f'generation_attack_{a.phase}_{idx:02}';stage.mkdir()
 save(stage/'CODE_AND_INPUT_FREEZE.json',{'status':'BEFORE_ANY_NEW_ATTACK_FORWARD','code':{name:digest(E/name) for name in ['run_attack.py','attack_native_proxy.py','native_worker.py']},
  'protocol_sha256':digest(R/'attack_preparation/PROTOCOL_FROZEN.json'),'detail_sha256':digest(R/'attack_preparation/PROTOCOL_DETAIL_V1.json'),'slots':slots,
  'model_hash_matches_official':True,'not_a_3B_issuer_fallback':True,'watermark_keys_or_private_trajectories_read':False})
 from transformers import AutoTokenizer
 from attack_native_proxy import NativeModel
 cfg=json.loads((R/'CONFIG_FROZEN.json').read_text(encoding='utf-8'));tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
 template=json.loads((R/'attack_preparation/CHAT_TEMPLATE.json').read_text(encoding='utf-8'))['template']
 # Same conservative admission line after any tokenizer runtime initialization.
 if psutil.virtual_memory().available<6.5*2**30:print('ATTACK_RESOURCE_WAIT_KEEP_MAIN_7B_POLICY');raise SystemExit(0)
 psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
 stamp=R/'attack_preparation/MODEL_LOAD_IDENTITY.json';model_path=Path(plan['model_identity']['model_path'])
 if stamp.exists():
  recorded=json.loads(stamp.read_text(encoding='utf-8'));assert recorded['bytes']==model_path.stat().st_size and recorded['mtime_ns']==model_path.stat().st_mtime_ns
 else:
  actual=digest(model_path);assert actual==plan['model_identity']['model_sha256']
  save(stamp,{'sha256':actual,'bytes':model_path.stat().st_size,'mtime_ns':model_path.stat().st_mtime_ns,'new_weights_downloaded':False})
 start=time.perf_counter();model=NativeModel(Path(plan['model_identity']['model_path']),R,2)
 psutil.Process(model.process.pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
 save(stage/'LOADED.json',{'controller_pid':os.getpid(),'owned_worker_pid':model.process.pid,'vocab':model.vocab,'GPU':False,'role':'ATTACK_ONLY'})
 for slot in slots:
  elapsed=time.perf_counter()-start
  if remaining-elapsed<80 or len(started)+newattempts>=96:status='RESOURCE_LIMIT';break
  source=Path(slot['input_path']).read_bytes();assert hashlib.sha256(source).hexdigest()==slot['input_sha256']
  messages=[{'role':'system','content':plan['prompts'][slot['variant']]},{'role':'user','content':source.decode('utf-8')}]
  prefix=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,chat_template=template)
  assert len(prefix)+384<=4096
  out=R/'attacks'/slot['task_id'];out.mkdir(parents=True)
  log({'event':'STARTED','task_id':slot['task_id'],'phase':'attack_'+a.phase,'utc':utc()});newattempts+=1
  save(out/'request.json',{'slot':slot,'messages':messages,'input_ids':prefix,'model_sha256':plan['model_identity']['model_sha256'],
   'decode':'argmax, no bias, no sampling seed','max_new_tokens':384,'issuer_model_still_7B':True,'GPU':False,'HTTP_generation_requests':0})
  ids=[];trace=[];why='MAX_TOKENS';t=time.perf_counter()
  try:
   model.clear();raw=model.forward(prefix)
   for step in range(384):
    if time.perf_counter()-start>=remaining:why='WALL_LIMIT';status='RESOURCE_LIMIT';break
    if used_tokens+newtokens>=30000:why='TOKEN_LIMIT';status='RESOURCE_LIMIT';break
    if psutil.virtual_memory().available<800*2**20:why='MEMORY_GUARD';status='MEMORY_GUARD';break
    token=int(np.argmax(raw));assert token<len(tok),'Undecodable padded attack token'
    ids.append(token);newtokens+=1;trace.append({'step':step,'token_id':token,'raw_finite':bool(np.isfinite(raw).all()),'no_bias':True})
    peak=max(peak,psutil.Process(model.process.pid).memory_info().rss)
    if token in [151643,151645]:why='EOS';break
    raw=model.forward([token])
   text=tok.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False);b=text.encode('utf-8');(out/'public.txt').write_bytes(b)
   save(out/'result.json',{'task_id':slot['task_id'],'generated_ids':ids,'public_ids':tok.encode(text,add_special_tokens=False),'public_sha256':hashlib.sha256(b).hexdigest(),
    'generated_tokens':len(ids),'natural_EOS':why=='EOS','finish_reason':why,
    'A_bytes':(out/'public.txt').read_bytes()==tok.decode(ids,skip_special_tokens=True,clean_up_tokenization_spaces=False).encode('utf-8'),
    'B_ids_equal':tok.encode(text,add_special_tokens=False)==[v for v in ids if v not in tok.all_special_ids],
    'all_logits_finite':all(x['raw_finite'] for x in trace),'wall_seconds':time.perf_counter()-t,
    'quality':'PENDING_AUTHOR_REVIEW_BEFORE_DETECTION','trace':trace,'not_a_watermark_generation':True})
   log({'event':'DELIVERED','task_id':slot['task_id'],'phase':'attack_'+a.phase,'tokens':len(ids),'finish_reason':why,'utc':utc()})
   print(json.dumps({'attack_task':slot['task_id'],'tokens':len(ids),'finish':why}),flush=True)
   if status!='COMPLETE':break
  except Exception as exc:
   save(out/'FAILURE.json',{'type':type(exc).__name__,'partial_ids':ids,'no_retry':True})
   log({'event':'TECH_FAIL','task_id':slot['task_id'],'phase':'attack_'+a.phase,'tokens':len(ids),'utc':utc()});status='METHOD_FAILURE';break
except Exception as exc:
 status='ATTACK_SETUP_FAILURE'
 if stage is not None:save(stage/'FAILURE.json',{'type':type(exc).__name__,'new_answer_attempts':newattempts,'new_tokens':newtokens,'no_retry':True})
 print(json.dumps({'status':status,'type_sanitized':type(exc).__name__}),flush=True)
finally:
 if model:model.close()
 if start is not None:
  receipt={'event':'STAGE_EXIT','phase':'attack_'+a.phase,'status':status,'wall_seconds':time.perf_counter()-start,'new_tokens':newtokens,'new_answer_attempts':newattempts,
   'peak_native_worker_RSS_bytes':peak,'own_worker_closed':True,'paid_API_calls':0,'GPU_calls':0,'utc':utc()}
  save(stage/'EXITED.json',receipt);log(receipt)
 f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);f.close()
