"""Predeclared technical S2 gate, not selection by a favorable effect score."""
import json
from bootstrap import R,save,digest
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text(encoding='utf-8'))
tasks=json.loads((R/'TASKS_FROZEN.json').read_text(encoding='utf-8'))
locks={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for q in json.loads(p.read_text(encoding='utf-8')).get('rows',[]):
  assert q['task_id'] not in locks,'Duplicate quality author lock'
  locks[q['task_id']]=q
stage=json.loads((R/'generation_s2_02/EXITED.json').read_text(encoding='utf-8'))
assert stage['own_worker_closed'] and stage['status']=='COMPLETE','Unfinished own model stage must not overlap'
D=R/'analysis_round02'
fp=json.loads((D/'FP_COMPUTE.json').read_text(encoding='utf-8'))
wm=json.loads((D/'WM_COMPUTE.json').read_text(encoding='utf-8'))
assert fp['status']=='COMPLETE' and wm['status']=='COMPLETE'
assert wm['query_truth_or_generation_trace_read'] is False
proof={};allowed=[]
for method in ['C0','B2','B3']:
 proof[method]={}
 for source in ['S01','S02']:
  valid=[]
  for t in tasks:
   if t['stage']!='S2' or t['source_id']!=source or t['method']!=method:continue
   p=R/'raw'/t['task_id']/'result.json'
   if not p.exists():continue
   raw=json.loads(p.read_text(encoding='utf-8'));q=locks[t['task_id']]
   assert digest(p.parent/'public.txt')==q['public_sha256'] and not q['detection_scores_seen_before_lock']
   if raw['natural_EOS'] and raw['A_bytes'] and raw['raw_finite_all']:valid.append(t['task_id'])
  proof[method][source]=valid
 if all(proof[method][s] for s in ['S01','S02']):allowed.append(method)
save(R/'ADMISSION_S2.json',{'status':'TECHNICAL_IMPLEMENTATION_ADMITTED_NOT_EFFECTIVENESS_SUCCESS','methods_allowed':allowed,
 'per_method_DEV_EOS_A_finite_evidence':proof,'public_pipeline_complete':True,'quality_locked':True,
 'knowledge_FAIL_and_technical_truncation_retained':True,'BPE_history_difference_not_a_generation_failure':True,
 'score_or_message_recovery_used_to_select_method':False,'public_error_target1percent_certified':False,
 'no_algorithm_or_threshold_change':True,'formal_next_stage_is_frozen_S3_only':True,'actual_S2_attempts':36})
print(json.dumps({'status':'S2_TECHNICAL_GATE_RECORDED','allowed':allowed}))
