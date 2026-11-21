"""Secondary causal/representation audit; does not change prior frozen outputs."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import sys,json,hashlib,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
P=Path(__file__).parent;O=P/'mm';OLD=ROOT/'experiments/strong_evidence_20261019_01'
def get(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
tr=get(O/'trace_LOCAL.json');summary=get(O/'paired_summary.json');stage=[]
for row in summary:
 z=[x for x in tr if x['subject']==row['subject'] and x['method']==row['method']];enabled=row['method']!='Strict-no-taskslot';row=copy.deepcopy(row);row['post_compression_set_change_rate']=row.pop('taskslot_rewrites_set_rate');row['taskslot_executed_rate']=float(enabled);row['taskslot_set_rewrite_rate_when_enabled']=row['post_compression_set_change_rate'] if enabled else None
 row['decompose_nonzero_knowledge_rate']=float(np.mean([any(any(abs(v)>1e-12 for v in e['knowledge']) for e in x['events_LOCAL'] if e['fn']=='decompose') for x in z]));row['compressed_empty_rate']=float(np.mean([not x['pre_taskslot'] for x in z]));row['task_embedding_lengths']=sorted(set(x['task_embedding_length'] for x in z));stage.append(row)
save('corrected_stage_summary.json',stage)
privacy=[];wiring=[]
for subject,file,n in [('Math','student-mat.csv',395),('Portuguese','student-por.csv',649)]:
 data=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n);parts=get(OLD/'mm'/ (subject+'_split_LOCAL.json'));full=get(OLD/'mm'/(subject+'_Strict-Full_LOCAL.json'));fullsets=full['fields']
 canonical=lambda fields:json.dumps([r.release(row,set(ids)) for row,ids in zip(data,fields)],sort_keys=True,separators=(',',':')).encode()
 for name in ['Strict-no-projection','Strict-no-attention','Strict-no-bottleneck','Strict-no-taskslot']:
  arm=get(OLD/'mm'/(subject+'_'+name+'_LOCAL.json'));different=[set(a)!=set(b) for a,b in zip(fullsets,arm['fields'])];identical=canonical(fullsets)==canonical(arm['fields'])
  privacy.append({'subject':subject,'method':name,'all_rows':n,'released_field_sets_differ_fraction':float(np.mean(different)),'canonical_external_release_identical_all_rows':identical,'full_release_sha256':hashlib.sha256(canonical(fullsets)).hexdigest(),'arm_release_sha256':hashlib.sha256(canonical(arm['fields'])).hexdigest(),'claim':'identical observable views cannot support a projection/attention privacy benefit under this release interface' if identical else 'actual released views differ; privacy must use recorded target-specific attacks, not internal norms'})
 for m,flag in [('Legacy-Full',None),('Legacy-no-projection','use_orthogonal'),('Legacy-no-attention','use_task_attention'),('Legacy-no-bottleneck','use_bottleneck')]:
  lengths=[];pprivate=[];sets=[]
  for i in parts['test']:
   p,t=(r.make_profile if subject=='Math' else make_portuguese_profile)(data[i],i);c=copy.deepcopy(r.CONFIG)
   if flag:c['fopd']['components'][flag]=False
   picked=ProfileSelector(c).select(p,t);s={x.record.record_id for x in picked};lengths.append(len(s));pprivate.append(bool(s&r.PRIVATE));sets.append(sorted(s))
  wiring.append({'subject':subject,'configuration':m,'test_n':len(lengths),'mean_fields':float(np.mean(lengths)),'min_fields':min(lengths),'max_fields':max(lengths),'K3_violations':sum(x>3 for x in lengths),'any_private_release_rate':float(np.mean(pprivate)),'interpretation':'current core with historical component switches and TaskSlot off; not restoration of an unavailable historical source hash'})
save('observable_privacy_audit.json',privacy);save('legacy_wiring_replay.json',wiring)
# Counterfactual finite-input check: internal vector support vs task-vector support.
support=[]
for subject in ['Math','Portuguese']:
 z=[x for x in tr if x['subject']==subject and x['method']=='Strict-Full'];valid=[]
 for x in z:
  e=next(a for a in x['events_LOCAL'] if a['fn']=='decompose');task=x['task_vector_LOCAL'];dims=[i for i,v in enumerate(e['knowledge']) if abs(v)>1e-12];valid.append(all(i>=len(task) or task[i]==0 for i in dims))
 support.append({'subject':subject,'n':len(z),'knowledge_nonzero_coordinate_set':[30,31],'task_vector_unpadded_lengths':sorted(set(x['task_embedding_length'] for x in z)),'knowledge_support_has_zero_task_weight_rate':float(np.mean(valid)),'projection_zero_rate':float(np.mean([x['projection_norm']==0 for x in z]))})
save('projection_support_audit.json',support)
save('secondary_completion.json',{'status':'COMPLETED','new_model_calls':0,'new_predictor_training':0,'additional_core_selection_calls':sum(x['test_n'] for x in wiring),'production_mutations':0,'privacy_scope':'canonical actual outbound dictionaries from original frozen all-row releases; no raw values exported'})
print(json.dumps({'support':support,'legacy':wiring},indent=2))
