"""Observe frozen selectors, without importing or rerunning the previous runner."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import sys,json,copy,inspect,hashlib,textwrap,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from protection.student_profile.src.fopd.orthogonal_decoder import OrthogonalDecoder
from protection.student_profile.src.fopd.task_attention import TaskAttentionSelector,InformationBottleneck
P=Path(__file__).parent;OLD=ROOT/'experiments/strong_evidence_20261019_01';O=P/'mm';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def load(n):return json.loads((OLD/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
code=(OLD/'mm/strict_select_enhanced.py.txt').read_text(encoding='utf8');ns={};exec(compile(code,str(O/'observed_strict.py'),'exec'),ProfileSelector.select_enhanced.__globals__,ns);Strict=type('StrictSelector',(ProfileSelector,),{'select_enhanced':ns['select_enhanced']})
methods=['Strict-Full','Strict-no-projection','Strict-no-attention','Strict-no-bottleneck','Strict-no-taskslot']
paths=[ROOT/'protection/student_profile/src/fopd'/x for x in ['profile_selector.py','orthogonal_decoder.py','task_attention.py']]
hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
save('protocol.json',{'status':'FROZEN_EXPLORATORY_TRACE_OLD_SAMPLES','methods':methods,'seed':20261013,'test':'same214 old records, 82 and128 proxy identity groups; no retraining or new test tuning','diagnostic':'first16 existing Math dev rows, omit explicit G1/G2 names; no test changes','source_hashes':hashes,'strict_source_sha256':sha(OLD/'mm/strict_select_enhanced.py.txt'),'outputs':'UCI internal numeric vectors only LOCAL; public trace contains field IDs, norms, counts, differences','projection_privacy':'only actual released representations count, never internal vector differences'})
line_index={}
for p in paths:
 line_index[str(p.relative_to(ROOT))]=[{'line':i,'code':line.strip()} for i,line in enumerate(p.read_text(encoding='utf8').splitlines(),1) if any(term in line for term in ['def select_enhanced','def decompose','def project_to_task','task_embedding','ortho_projection','attention_scores','compressed_records','distinct_types','reserved =','ordered =','return list(aligned','weight > privacy_cost','def compute_attention','return scores['])]
save('code_line_index.json',line_index)
def observe(selector,p,t):
 events=[];final={};interesting={'select_enhanced','decompose','project_to_task','compute_attention','compress'}
 def tracer(frame,event,arg):
  if event=='call':
   if frame.f_code.co_name not in interesting:return None
   frame.f_trace_lines=False;return tracer
  if event=='return':
   name=frame.f_code.co_name;loc=frame.f_locals
   if name=='select_enhanced':final.update(loc)
   elif name=='project_to_task':events.append({'fn':name,'task_input':loc.get('task_embedding',[]),'output':arg})
   elif name=='decompose':events.append({'fn':name,'knowledge':arg.knowledge_vector,'strategy':arg.strategy_vector,'sensitive':arg.sensitive_vector})
   elif name=='compute_attention':events.append({'fn':name,'output':arg})
   elif name=='compress':events.append({'fn':name,'input_ids':[x.record_id for x in loc['selected_records']],'weights':loc['attention_weights'],'output_ids':[x.record_id for x in arg]})
  return tracer
 sys.settrace(tracer)
 try:result=selector.select(p,t)
 finally:sys.settrace(None)
 ids=lambda z:[x.record_id if hasattr(x,'record_id') else x.record.record_id for x in z]
 projection=final.get('projected',[]);taskvec=final.get('task_embedding',[])
 return {'projection_called':any(x['fn']=='project_to_task' for x in events),'decompose_called':any(x['fn']=='decompose' for x in events),'attention_called':any(x['fn']=='compute_attention' for x in events),'task_embedding_length':len(taskvec),'projection_norm':float(np.linalg.norm(projection)),'nonzero_projection_coordinates':[i for i,v in enumerate(projection) if abs(v)>1e-12],'attention_rank':[p.profile_records[i].record_id for i,w in final.get('attention_scores',[])],'attention_weights':{p.profile_records[i].record_id:float(w) for i,w in final.get('attention_scores',[])},'pre_taskslot':ids(final.get('compressed_records',[])),'reserved':ids(final.get('reserved',[])),'final':[x.record.record_id for x in result],'taskslot_modified_set':set(ids(final.get('compressed_records',[])))!={x.record.record_id for x in result},'events_LOCAL':events,'projection_LOCAL':projection,'task_vector_LOCAL':taskvec}
def config(m,count):
 c=copy.deepcopy(r.CONFIG);c['fopd']['attention']={'top_k_dimensions':count};c['fopd']['unit_budget']['distinct_requested_types']=[] if m=='Strict-no-taskslot' else ['mastery']
 flag={'Strict-no-projection':'use_orthogonal','Strict-no-attention':'use_task_attention','Strict-no-bottleneck':'use_bottleneck'}.get(m)
 if flag:c['fopd']['components'][flag]=False
 return c
rowsout=[];local=[];summaries=[];diagnostic=[]
oldmetrics=load('mm/summary.json');oldattacks=load('mm/attacks.json')
for subject,file,n in [('Math','student-mat.csv',395),('Portuguese','student-por.csv',649)]:
 rows=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n);parts=load('mm/'+subject+'_split_LOCAL.json');saved={m:load('mm/'+subject+'_'+m+'_LOCAL.json') for m in methods};by={}
 for i in parts['test']:
  p,t=(r.make_profile if subject=='Math' else make_portuguese_profile)(rows[i],i)
  for m in methods:
   obs=observe(Strict(config(m,len(p.profile_records))),p,t)
   assert set(obs['final'])==set(saved[m]['fields'][i]),(subject,i,m)
   entry={'subject':subject,'row_LOCAL':i,'method':m,**obs};local.append(entry);by[(i,m)]=obs
   rowsout.append({k:v for k,v in entry.items() if not k.endswith('_LOCAL') and k not in ['attention_weights']})
 fullpred=np.array(saved['Strict-Full']['prediction'])
 for m in methods:
  pairs=[(by[(i,'Strict-Full')],by[(i,m)]) for i in parts['test']];diff=lambda k:float(np.mean([a[k]!=b[k] for a,b in pairs]));setdiff=lambda k:float(np.mean([set(a[k])!=set(b[k]) for a,b in pairs]));pred=np.array(saved[m]['prediction']);metric=next(x for x in oldmetrics if x['subject']==subject and x['method']==m)
  summaries.append({'subject':subject,'method':m,'n_records':len(pairs),'projection_execution_rate':float(np.mean([b['projection_called'] for a,b in pairs])),'nonzero_projection_rate':float(np.mean([b['projection_norm']>1e-12 for a,b in pairs])),'internal_weights_changed_rate':float(np.mean([a['attention_weights']!=b['attention_weights'] for a,b in pairs])),'top3_rank_changed_rate':float(np.mean([a['attention_rank'][:3]!=b['attention_rank'][:3] for a,b in pairs])),'pre_taskslot_set_changed_vs_full':setdiff('pre_taskslot'),'taskslot_rewrites_set_rate':float(np.mean([b['taskslot_modified_set'] for a,b in pairs])),'final_set_changed_rate':setdiff('final'),'prediction_changed_rate':float(np.mean(np.abs(pred-fullpred)>1e-10)),'max_prediction_delta':float(np.max(np.abs(pred-fullpred))),'MAE':metric['mae'],'BA':metric['attack_BA'],'AUC':metric['attack_AUC'],'tokens':metric['tokens']})
 if subject=='Math':
  # Dev-only ambiguity, fixed to first16 frozen dev rows; baseline capabilities unchanged.
  mi=r.train_mi_order(rows,np.array(parts['train']),20261019)
  for i in parts['dev'][:16]:
   p,t=r.make_profile(rows[i],i);t.question=re.sub(r'\bG[12]\b','previous assessment',t.question)
   for m in methods:
    z=observe(Strict(config(m,len(p.profile_records))),p,t);diagnostic.append({'row_LOCAL':i,'method':m,'projection_norm':z['projection_norm'],'task_embedding_length':z['task_embedding_length'],'top3':z['attention_rank'][:3],'pre_taskslot':z['pre_taskslot'],'final':z['final']})
   for m in ['SafeTaskTopK-3','TrainMI-SafeTopK-3']:diagnostic.append({'row_LOCAL':i,'method':m,'final':sorted(r.select_fields(m,p,t,20261019,mi))})
save('trace_LOCAL.json',local);save('trace_public.json',rowsout);save('paired_summary.json',summaries);save('dev_ambiguity_LOCAL.json',diagnostic)
ds=[]
for m in methods+['SafeTaskTopK-3','TrainMI-SafeTopK-3']:
 z=[x for x in diagnostic if x['method']==m];reference=[x for x in diagnostic if x['method']=='Strict-Full'];ds.append({'method':m,'dev_n':len(z),'final_changed_vs_full':float(np.mean([set(x['final'])!=set(y['final']) for x,y in zip(z,reference)])),'grade_period_coverage':float(np.mean([len(set(x['final'])&{'G1','G2'})/2 for x in z])),'mean_fields':float(np.mean([len(x['final']) for x in z])),'nonzero_projection_rate':float(np.mean([x.get('projection_norm',0)>1e-12 for x in z]))})
save('dev_summary.json',ds)
save('completion.json',{'status':'COMPLETED_FROZEN_PATH_REPLAY','traced_sample_method_cells':len(local),'test_records':214,'exact_released_field_replay':True,'new_model_calls':0,'new_attacker_training':0,'predictions':'paired original frozen individual predictions, no re-fitting or re-tuning','core_unchanged':all(sha(ROOT/p)==h for p,h in hashes.items())})
print(json.dumps(summaries,indent=2))
