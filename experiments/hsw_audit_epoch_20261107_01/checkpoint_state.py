"""Atomic mutable recovery pointer, derived from append-only evidence."""
import datetime,json,os
from collections import Counter
from pathlib import Path
import psutil
from bootstrap import E,R
ledger=[json.loads(x) for x in (R/'RUN_MANIFEST.jsonl').read_text(encoding='utf-8').splitlines()]
started=[x for x in ledger if x['event']=='STARTED']
raw=[json.loads(p.read_text(encoding='utf-8')) for p in (R/'raw').glob('*/result.json')]
quality=[q for p in (R/'reviews').glob('*QUALITY_LOCK*.json') for q in json.loads(p.read_text(encoding='utf-8')).get('rows',[])]
stages=[]
for d in R.glob('generation_*'):
 if not d.is_dir() or (d/'EXITED.json').exists():continue
 p=d/'LOADED.json'
 if not p.exists():continue
 x=json.loads(p.read_text(encoding='utf-8'));pid=x['controller_pid'];live=False
 try:
  cmd=psutil.Process(pid).cmdline()
  live=any(Path(c).name in {'run_generation.py','run_attack.py'} and Path(c).parent.resolve()==E.resolve() for c in cmd)
 except (psutil.NoSuchProcess,psutil.AccessDenied):pass
 stages.append({'stage':d.name,'controller_pid':pid,'owned_worker_pid':x.get('owned_worker_pid'),'live_identity_verified':live})
tokens=sum(x.get('tokens',0) for x in ledger if x['event'] in {'DELIVERED','TECH_FAIL'})
state={'task':'HSW-AUDIT-EPOCH-01','stage':'RUNNING_EXISTING_STAGE' if any(s['live_identity_verified'] for s in stages) else 'CHECKPOINT',
 'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'attempts':len(started),'delivered':len(raw),
 'natural_EOS_complete':sum(x['natural_EOS'] for x in raw),'technical_truncated_snapshots':sum(not x['natural_EOS'] for x in raw),
 'quality_locked':len(quality),'quality_counts':dict(Counter(q['overall'] for q in quality)),
 'tokens_recorded_completed':tokens,'stage_wall_recorded':sum(x['wall_seconds'] for x in ledger if x['event']=='STAGE_EXIT'),
 'active_stage_wall_not_in_closed_total':True,'open_stages':stages,'user_choice':'KEEP_7B_WAIT',
 'RAM_admission_GiB':6.5,'RAM_decode_guard_MiB':800,'3B_issuer_fallback_authorized':False,
 'frozen_main_slots':89,'generation_attempt_limit':96,'user_outer_limit':256,'GPU_calls':0,'paid_API_calls':0,
 'original_hard_model_seconds':7200,'budget_extension_requires_explicit_reply':True,
 'new_root':str(E.parents[1]),'no_original_research_files_written':True,'RQ2':'FROZEN',
 'next_action':'Monitor existing stage; finish pending label-hidden full-text quality cards before public scoring. Never repeat STARTED tasks.'}
dest=R/'STATE.json';temp=dest.with_suffix('.json.partial');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(temp,dest)
print(json.dumps({k:state[k] for k in ['stage','attempts','delivered','quality_locked','open_stages']}))
