"""Postscore trace diagnostics; NEVER imported by any public detector."""
import csv,difflib,json,datetime
from collections import Counter
from bootstrap import R,E,save,digest
import psutil

D=R/'analysis_round01';assert (D/'EVALUATION_RECEIPT.json').is_file()
assert not (D/'TOKEN_AND_COST_DIAGNOSTICS.json').exists()
tasks=json.loads((R/'TASKS_FROZEN.json').read_text());byid={t['task_id']:t for t in tasks}
locked={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for r in json.loads(p.read_text()).get('rows',[]):locked[r['task_id']]=r
rows=[]
for t in tasks:
 p=R/'raw'/t['task_id']/'result.json';row={'task_id':t['task_id'],'source_id':t['source_id'],'split':t['source_split'],
 'stage':t['stage'],'method':t['method'],'recipient':t['recipient_pseudonym'],'epoch':t['epoch'],
 'input_source_sha256':t['source_sha256'],'status':'NOT_RUN','not_run_reason':'RESOURCE_WAIT_7B; stage gate may also be pending',
 'quality':'NOT_RUN','complete_EOS':False,'public_sha256':'','generated_tokens':None,'wall_seconds':None}
 if p.exists():
  d=json.loads(p.read_text());q=locked[t['task_id']];trace=[json.loads(l) for l in (p.parent/'trace.jsonl').read_text().splitlines()]
  row.update(status='COMPLETE' if d['natural_EOS'] else 'TECHNICAL_TRUNCATED',not_run_reason='',quality=q['overall'],
   complete_EOS=d['natural_EOS'],finish_reason=d['finish_reason'],facts=q['facts'],coverage=q['coverage'],task_utility=q['task_utility'],
   public_sha256=d['public_sha256'],generated_tokens=d['generated_tokens'],wall_seconds=d['wall_seconds'],
   A_bytes=d['A_bytes'],B_ids_equal=d['B_ids_equal'],finite=d['raw_finite_all'],
   public_tokens=len(d['public_ids']),nonterminal_generated_tokens=len(d['generated_ids'])-int(d['natural_EOS']))
  source=open(t['source_path'],encoding='utf-8').read();text=(p.parent/'public.txt').read_text(encoding='utf-8')
  row['character_change_1minus_SequenceMatcher_no_autojunk']=1-difflib.SequenceMatcher(None,source,text,autojunk=False).ratio()
  if t['method']!='C0':
   ds=[x['diagnostic'] for x in trace]
   row['bias_logged_steps']=len(ds);row['selected_favored_steps']=sum(bool(x.get('selected_favored')) for x in ds)
   row['bias_count_min']=min(x['biased_count'] for x in ds);row['bias_count_max']=max(x['biased_count'] for x in ds)
   if t['method']=='B3':row['bias_exact_all']=all(x['bias_exact'] for x in ds)
  row['review_evidence_json']=json.dumps(q['evidence'],ensure_ascii=False)
 rows.append(row)
fields=list(dict.fromkeys(k for r in rows for k in r))
with (R/'RESULTS.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
actual=[r for r in rows if r['status']!='NOT_RUN']
own=[]
with (D/'OWN_KEY_DIAGNOSTICS.csv').open(encoding='utf-8-sig') as f:own=list(csv.DictReader(f))
wm=[json.loads(l) for l in (D/'WM_SCORES.jsonl').read_text().splitlines()]
truth={r['query_id']:r for r in json.loads((R/'private/round01_QUERY_TRUTH.json').read_text()) if r['status']=='SCORABLE'}
bits=[]
for r in wm:
 t=truth[r['query_id']]
 if t.get('issued_method')=='B3' and t['variant']=='FULL' and r['candidate_key_id']=='MPAC_'+t['truth_epoch']:
  goal=byid[t['truth_issue_id']]['message_code'];code=r['scores']['top1']
  bits.append({'task_id':t['truth_issue_id'],'top1_bit_errors':sum(a!=b for a,b in zip(goal,code)),
   'payload_bits':32,'top1_complete_identity_recovered':goal==code,'list_contains_goal':any(c['message_code']==goal for c in r['scores']['candidates']),
   'true_code_only_after_independent_decoding':True,'not_a_decoder_input':True})
ledger=[json.loads(l) for l in (R/'RUN_MANIFEST.jsonl').read_text().splitlines()]
modelwall=sum(r['wall_seconds'] for r in ledger if r['event']=='STAGE_EXIT')
save(D/'TOKEN_AND_COST_DIAGNOSTICS.json',{'status':'POSTSCORE_DESCRIPTIVE','attempts':len(actual),'planned_base_slots':len(tasks),
 'not_started':len(tasks)-len(actual),'natural_EOS':sum(r['complete_EOS'] for r in actual),
 'technical_truncated':sum(r['status']=='TECHNICAL_TRUNCATED' for r in actual),'generated_tokens_including_EOS':sum(r['generated_tokens'] for r in actual),
 'quality':dict(Counter(r['quality'] for r in actual)),'A_bytes':dict(Counter(str(r['A_bytes']) for r in actual)),
 'B_ids_equal':dict(Counter(str(r['B_ids_equal']) for r in actual)),
 'generation_stage_seconds':modelwall,'native_RSS_peak_bytes':max(r['peak_native_worker_RSS_bytes'] for r in ledger if r['event']=='STAGE_EXIT'),
 'native_tokens_per_stage_wall':sum(r['generated_tokens'] for r in actual)/modelwall,
 'API_paid_calls':0,'GPU_seconds':0,'new_models_downloaded':0,'MPAC_bit_recovery':bits,
 'not_a_formal_effectiveness_or_security_test':True})
# Persist user's explicit choice; no implicit permission to weaken the guard.
save(R/'RESOURCE_WAIT_USER_DIRECTIVE.json',{'user_choice':'保持7B，等待资源空闲','fallback_to3B':False,'lower_RAM_admission':False,
 'RAM_admission_GiB':6.5,'already_started_slots_must_not_repeat':True,'new_model_calls_after_choice':0,
 'captured_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'free_RAM_GiB':psutil.virtual_memory().available/2**30})
snapshot=R/'STATE.json';save(R/'STATE_BEFORE_OFFLINE_CHECKPOINT.json',json.loads(snapshot.read_text()))
state=json.loads(snapshot.read_text());state.update(stage='RESOURCE_WAIT',user_choice='KEEP_7B_WAIT',
 offline_round01='COMPLETE',generation_remaining_slots=len(tasks)-len(actual),full_experiment_complete=False,
 updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
snapshot.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'CHECKPOINT_UPDATED','actual':len(actual),'not_started':len(tasks)-len(actual),'MPAC':bits}))
