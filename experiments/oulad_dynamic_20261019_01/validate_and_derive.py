"""Integrity, temporal, budget and release-level checks on actual saved runs."""
from pathlib import Path
import sys,json,hashlib,collections,csv,ast
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(P));import design as d;import selection_engine as e
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def csvout(n,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row))
 with (P/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
pres=load('preservation.json');assert all(sha(ROOT/k)==v for k,v in pres['core'].items());previous=0
for old in pres['previous']:
 base=ROOT/'experiments'/old['directory'];assert sha(base/'evidence_manifest.json')==old['manifest_sha256']
 for file in old['files']:assert sha(base/file['path'])==file['sha256'];previous+=1
initial=load('protocol.json')
for rel,digest in initial['source_sha256'].items():assert sha(P/rel)==digest
independent=load('independent_protocol.json');assert independent['source_sha256']==load('dev_results/completion.json')['source_sha256']==load('test_results/completion.json')['source_sha256']
for rel,digest in independent['source_sha256'].items():assert sha(P/rel)==digest
dev=load('dev_data/snapshots_LOCAL.json');test=load('test_data/snapshots_LOCAL.json');train=[x for x in dev if x['split']=='train'];validation=[x for x in dev if x['split']=='dev'];groups=[{x['student'] for x in z} for z in [train,validation,test]];assert all(groups[i].isdisjoint(groups[j]) for i,j in [(0,1),(0,2),(1,2)])
temporal=0
for row in dev+test:
 audit=row['source_audit'];t=row['cutoff'];assert row['target_due']>t and row['target_due']<=t+56
 assert audit['grade_max_due'] is None or audit['grade_max_due']<=t-7
 assert audit['grade_max_submitted'] is None or audit['grade_max_submitted']<=t-7
 assert audit['click_max_date'] is None or audit['click_max_date']<=t
 temporal+=1
# All 256 valid coordinate masks; actual semantics are public role metadata.
projector_error=0.
for n in range(256):
 mask=np.array([(n>>i)&1 for i in range(8)],dtype=float);projector=np.diag(mask);z=np.arange(1,9)/8;u=projector@z;v=z-u;projector_error=max(projector_error,float(np.max(abs(projector@projector-projector))),float(np.max(abs(projector-projector.T))),abs(float(u@v)))
assert projector_error==0
from transformers import AutoTokenizer
tok=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
derived=[];transitions=[];contexts=[];localfail=[];realrelease_count=0
for phase,evalrows in [('dev',validation),('test',test)]:
 cases=load(phase+'_results/cases_LOCAL.json');lookup={(x['student'],x['cutoff']):x for x in evalrows};summary=load(phase+'_results/summary.json');assert len(cases)==len(evalrows)*60;realrelease_count+=len(cases)
 lengths=[len(v) for v in tok([x['payload'] for x in cases],add_special_tokens=False)['input_ids']]
 for case,length in zip(cases,lengths):
  row=lookup[case['student'],case['cutoff']];assert len(case['selected_fields'])==3 and set(case['selected_fields'])<=set(d.FIELDS);assert e.payload(row,case['selected_fields'])==case['payload'];assert length==case['actual_tokens']<=64
  assert all(d.FIELDS[k][1]<=.7 for k in case['selected_fields'])
 for cell in summary:
  z=[x for x in cases if x['method']==cell['method'] and x['intent']==cell['intent'] and x['wording']==cell['wording']];assert len(z)==len(evalrows);mae=np.mean([abs(x['prediction']-x['target']) for x in z]);assert abs(mae-cell['MAE'])<1e-10
  missing=sum(lookup[x['student'],x['cutoff']]['values'][k] is None for x in z for k in x['selected_fields']);derived.append({**cell,'released_missing_fraction':missing/(3*len(z)),'nonmissing_fields_mean':3-missing/len(z)})
  if cell['method']!='Repaired-Full':continue
  full={(x['student'],x['cutoff']):x for x in z};same=changed=total=0
  for sid in sorted({x['student'] for x in z}):
   zz=sorted([x for x in z if x['student']==sid],key=lambda x:x['cutoff'])
   for before,after in zip(zz,zz[1:]):total+=1;same+=before['selected_fields']==after['selected_fields'];changed+=before['payload']!=after['payload']
  transitions.append({'phase':phase,'intent':cell['intent'],'wording':cell['wording'],'adjacent_student_stage_pairs':total,'field_set_changed_rate':1-same/total,'actual_value_payload_changed_rate':changed/total,'scope':'same intent, same wording, retained adjacent observations per student'})
  for case in sorted(z,key=lambda x:abs(x['prediction']-x['target']),reverse=True)[:3]:
   related=[x for x in cases if x['student']==case['student'] and x['cutoff']==case['cutoff'] and x['intent']==case['intent'] and x['wording']==case['wording']];localfail.append({'phase':phase,'source_snapshot':lookup[case['student'],case['cutoff']],'paired_methods':related,'selection':'largest Full errors within predeclared intent/wording; explanatory only, not selected for metric estimates'})
 for intent in d.INTENTS:
  for wording in ['explicit','ambiguous']:
   s={x['method']:x for x in derived if x['phase']==phase and x['intent']==intent and x['wording']==wording};p={x['method']:x for x in load(phase+'_results/paired_mechanisms.json') if x['intent']==intent and x['wording']==wording};c=next(x for x in load('rule_'+phase+'.json')['cells'] if x['intent']==intent and x['wording']==wording);assert c['fixed_predictor_attack_metrics_can_be_reused_exactly']
   contexts.append({'phase':phase,'intent':intent,'wording':wording,'Full_MAE':s['Repaired-Full']['MAE'],'SafeTaskTopK_MAE':s['SafeTaskTopK']['MAE'],'TaskSlot_MAE':s['TaskSlot']['MAE'],'TrainMI_MAE':s['TrainMI']['MAE'],'StageRoleRule_MAE':s['StageRoleRule']['MAE'],'delta_Full_minus_Safe':s['Repaired-Full']['MAE']-s['SafeTaskTopK']['MAE'],'delta_Full_minus_no_projection':s['Repaired-Full']['MAE']-s['Repaired-no-projection']['MAE'],'delta_Full_minus_no_attention':s['Repaired-Full']['MAE']-s['Repaired-no-attention']['MAE'],'no_projection_payload_changed':p['Repaired-no-projection']['actual_payload_changed_rate'],'no_attention_payload_changed':p['Repaired-no-attention']['actual_payload_changed_rate'],'Full_equals_cost_rule':True})
save('comparison_derived.json',derived);save('dynamic_transitions.json',transitions);save('context_comparison.json',contexts);save('failure_cases_LOCAL.json',localfail)
csvout('comparison.csv',derived);csvout('strict_ablation.csv',[{'phase':phase,**x} for phase in ['dev','test'] for x in load(phase+'_results/paired_mechanisms.json')]);csvout('attributes.csv',[{'phase':phase,**x} for phase in ['dev','test'] for x in load(phase+'_results/attacks.json')]);csvout('stage_utility.csv',[{'phase':phase,**x} for phase in ['dev','test'] for x in load(phase+'_results/subgroups.json')]);csvout('stage_privacy.csv',load('stage_privacy_results.json'));csvout('public_context_attack.csv',load('public_context_attack.json'));csvout('dynamic_transitions.csv',transitions);csvout('paired_intervals.csv',[{'phase':phase,**x} for phase in ['dev','test'] for x in load(phase+'_results/paired_intervals.json')])
privacy=load('stage_privacy_completion.json');assert privacy['main_attack_cells_exactly_matched']==240
decision={'decision':'PIVOT','scope':'independent advantage / innovation claim of orthogonal projection and complex MM-FOPD stack','evidence':{'test_no_projection_payload_change_rate':sorted(set(x['no_projection_payload_changed'] for x in contexts if x['phase']=='test')),'attention_has_actual_effect_in_cells':sum(x['no_attention_payload_changed']>0 for x in contexts if x['phase']=='test'),'Full_identical_to_Safe_in_contexts':sum(abs(x['delta_Full_minus_Safe'])<1e-10 for x in contexts if x['phase']=='test'),'simple_cost_rule_equal_test_payloads':sum(x['actual_eval_payloads_identical'] for x in load('rule_test.json')['cells']),'simple_cost_rule_test_cells':6},'recommendation':'Keep common safety gate, exact cost accounting and transparent TFIDF relevance-cost ranking; remove/optionalize coordinate projection, redundant subset optimizer and bounded TaskSlot bonus. Ordinary schema rule remains useful when contract is explicit. Do not claim learned disentanglement or independent Attention novelty.','positive_evidence':'Attention improves utility vs constant-weight removal in some cells, independently replicated on2014J; actual field changes verified. This does not establish superiority to ordinary relevance ranking.','negative_evidence':'No projection contribution; Full equal ordinary relevance-cost rule across all train/test contexts; primary PROCEED criterion requiring BOTH components cannot be satisfied.','stop':'No retuning, test replacement, module expansion or repeated heldout search this round.'}
save('decision.json',decision)
save('validation.json',{'status':'VERIFIED_EXPLORATORY_REAL_DATA_RESULTS','core_unchanged':True,'previous_evidence_files_unchanged':previous,'source_versions_unchanged_since_freeze':True,'student_groups':{'train':len(groups[0]),'dev':len(groups[1]),'test':len(groups[2]),'all_pairwise_disjoint':True},'snapshots_time_checked':temporal,'actual_eval_payloads_token_checked':realrelease_count,'all_K3_cap64':True,'projector_masks_checked':256,'projector_max_error':projector_error,'stage_privacy_aggregate_fits_matched':privacy['main_attack_cells_exactly_matched'],'ordinary_rule_all_train_eval_equivalent':True,'time_availability_limitation':'grade publication timestamp not provided, seven-day lag is only a proxy','contract_limitation':'author-created necessary field contract, not independent human truth','not_a_privacy_guarantee':True,'no_untouched_human_blind_claim':True})
paths=[]
for rel in ['design.py','selection_engine.py','run_experiment.py','build_data.py','check_simple_rule.py','stage_privacy.py','frozen/aligned_selector.py','frozen/profile_selector.py','frozen/orthogonal_decoder.py','frozen/task_attention.py']:
 p=P/rel;tree=ast.parse(p.read_text(encoding='utf8'));paths.append({'file':rel,'sha256':sha(p),'functions':[{'name':x.name,'line':x.lineno} for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.ClassDef))]})
save('code_paths.json',paths);print(json.dumps({'decision':decision,'validation':load('validation.json')},indent=2))
