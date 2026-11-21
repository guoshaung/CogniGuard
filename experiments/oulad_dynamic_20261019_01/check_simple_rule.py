"""Post-dev diagnostic, fixed before heldout results: ordinary relevance-cost rule.

No projection, subset optimization, TaskSlot, trained embedding or outcome input.
Score=.75*relative_TFIDF_attention-.25*sensitivity; same actual output cap.
If its unconstrained Top3 equals unconstrained Full and is feasible per row,
the constrained Full objective cannot prefer an infeasible higher-scoring subset.
Actual eval payload equality is also checked directly, without trusting that proof.
"""
from pathlib import Path
import json,sys,hashlib
P=Path(__file__).parent;sys.path.insert(0,str(P));import design as d;import selection_engine as e
from protection.common.schemas import ProfileRecord,Task
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if not (P/'rule_protocol.json').exists():
 save('rule_protocol.json',{'status':'FROZEN_AFTER_DEV_BEFORE_HELDOUT_RESULTS','driver_sha256':sha(Path(__file__)),'definition':'greedy Top3 by .75*TFIDF_relative_weight-.25*sensitivity; no projection, TaskSlot or subset penalty','public_inputs':'identical metadata, aliases, fixed sensitivities and task question; no student labels/values except actual token feasibility','purpose':'test if apparent benefits over raw SafeTaskTopK are ordinary relevance-cost ranking','heldout_results_exist_at_freeze':(P/'test_results/completion.json').exists(),'primary_protocol_unchanged':True,'not_an_additional_tuned_proposal':True})
assert load('rule_protocol.json')['driver_sha256']==sha(Path(__file__))
phase=sys.argv[1] if len(sys.argv)>1 else 'dev';assert phase in ['dev','test']
output=f'rule_{phase}.json'
if (P/output).exists():raise RuntimeError('no overwrite')
train=[x for x in load('dev_data/snapshots_LOCAL.json') if x['split']=='train'];evalrows=[x for x in load('dev_data/snapshots_LOCAL.json') if x['split']=='dev'] if phase=='dev' else load('test_data/snapshots_LOCAL.json');rows=train+evalrows;actual={(x['student'],x['cutoff'],x['intent'],x['wording']):x for x in load(phase+'_results/cases_LOCAL.json') if x['method']=='Repaired-Full'}
from transformers import AutoTokenizer
tokenizer=AutoTokenizer.from_pretrained(str(P.parents[1]/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
out=[]
for intent in d.INTENTS:
 for wording in ['explicit','ambiguous']:
  fields_by_stage={};unconstrained_equal=True
  for cutoff in d.CUTOFFS:
   records=[ProfileRecord(k,t,'oulad','metadata_only',1.,s,'') for k,(t,s,r,desc) in d.FIELDS.items()];task=Task('oulad','public',f'Task purpose {intent}. '+d.question(intent,wording,cutoff),'oulad','development',False);_,_,u=e.alg.attention_values(records,task,d.CFG['temperature']);score={r.record_id:.75*float(u[i])-.25*r.sensitivity for i,r in enumerate(records)};ordered=sorted(score,key=lambda k:(-score[k],k));fields=sorted(ordered[:3]);full,trace=e.alg.choose(records,task,lambda _:0,d.CFG,'Repaired-Full');unconstrained_equal&=set(fields)==full;fields_by_stage[cutoff]=fields
  counts=[len(v) for v in tokenizer([e.payload(row,fields_by_stage[row['cutoff']]) for row in rows],add_special_tokens=False)['input_ids']];allfit=max(counts)<=64
  equal=sum(actual[x['student'],x['cutoff'],intent,wording]['payload']==e.payload(x,fields_by_stage[x['cutoff']]) for x in evalrows);n=len(evalrows)
  out.append({'phase':phase,'intent':intent,'wording':wording,'n_train_snapshots':len(train),'n_eval_snapshots':n,'unconstrained_Full_and_simple_rule_fields_equal_all_stages':bool(unconstrained_equal),'simple_Top3_feasible_all_train_eval_rows':allfit,'max_actual_tokens':max(counts),'actual_eval_payloads_identical':equal,'actual_eval_payload_equal_rate':equal/n,'fields_by_stage':fields_by_stage,'fixed_predictor_attack_metrics_can_be_reused_exactly':bool(unconstrained_equal and allfit and equal==n),'scope':'Only reuse same model/attack metrics when identical train and eval releases established; otherwise no unexecuted performance claim'})
save(output,{'status':'COMPLETED_RULE_EQUIVALENCE_CHECK','phase':phase,'frozen_protocol_sha256':sha(P/'rule_protocol.json'),'all_cells_exactly_equal':all(x['fixed_predictor_attack_metrics_can_be_reused_exactly'] for x in out),'cells':out});print(json.dumps(out,indent=2))
