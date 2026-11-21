"""Apply two-sided predeclared development gate; freeze ALL heldout cells."""
from pathlib import Path
import json,hashlib
P=Path(__file__).parent
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if (P/'development_gate.json').exists():raise RuntimeError('no overwrite')
complete=load('dev_results/completion.json');assert complete['status']=='COMPLETED'
summary=load('dev_results/summary.json');paired=load('dev_results/paired_mechanisms.json');availability=load('dev_data/availability.json');qualifying=[]
for p in paired:
 if p['method'] not in ['Repaired-no-projection','Repaired-no-attention']:continue
 full=next(x for x in summary if x['intent']==p['intent'] and x['wording']==p['wording'] and x['method']=='Repaired-Full');abl=next(x for x in summary if x['intent']==p['intent'] and x['wording']==p['wording'] and x['method']==p['method']);delta=full['MAE']-abl['MAE']
 if p['actual_payload_changed_rate']>=.05 and abs(delta)>=.5:qualifying.append({'intent':p['intent'],'wording':p['wording'],'ablation':p['method'],'payload_changed_rate':p['actual_payload_changed_rate'],'MAE_Full_minus_ablation':delta,'gate_is_two_sided':True})
class_ok=all(x['positive_students']>=10 and x['n_students']-x['positive_students']>=10 for x in availability['attributes_by_split'] if x['split']=='dev');passed=bool(qualifying) and complete['eval_students']>=100 and class_ok
save('development_gate.json',{'status':'PASS_FREEZE_INDEPENDENT' if passed else 'STOP_NO_INDEPENDENT_EXPANSION','qualifying_actual_differences':qualifying,'dev_students':complete['eval_students'],'attribute_class_support':class_ok,'gate_from_protocol':load('protocol.json')['gate_before_independent'],'all_contexts_retained_if_pass':True,'not_a_superiority_test':True,'no_model_or_task_revision':True,'independent_data_not_yet_built':not (P/'test_data').exists()})
if passed:
 if (P/'independent_protocol.json').exists():raise RuntimeError('no overwrite')
 sources={n:sha(P/n) for n in ['design.py','build_data.py','selection_engine.py','run_experiment.py','protocol.json','frozen/aligned_selector.py','frozen/strict_select_enhanced.py.txt']};assert sources==complete['source_sha256']
 save('independent_protocol.json',{'status':'FROZEN_BEFORE_2014J_RESERVED_DATA_BUILD','authorized_by_frozen_dev_gate':True,'gate_sha256':sha(P/'development_gate.json'),'development_completion_sha256':sha(P/'dev_results/completion.json'),'source_sha256':sources,'scope':'all3 modules, all3 stages, all3 intents, both wordings, all10 methods; no winning-cell selection','cohort_rule':load('protocol.json')['cohort'],'targets_untouched_before_lock':True,'no_retuning':True,'model_fit':'same fixed train2013J snapshots only; dev not added to training','report_all_results_including_negative':True,'decision_rule':'PROCEED only if at least one predefined ambiguous intent shows Full MAE lower than SafeTaskTopK, TaskSlot and StageRoleRule with student-bootstrap95 upper<0, Full BA/AUC no worse than each by>.02, and BOTH projection/attention removals increase MAE>=.5 with actual payload differences. Partial/mixed evidence=>ANALYZE. If strong rule matches/beats Full and no independent component advantage=>PIVOT; no repeated test redesign.','classification':'student-disjoint forward presentation heldout, author-designed tasks/contract; EXPLORATORY, not independent teacher-blind annotation'})
print(json.dumps(load('development_gate.json'),indent=2))
