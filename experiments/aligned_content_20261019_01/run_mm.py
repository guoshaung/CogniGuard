import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
import sys,json,copy,time,hashlib,itertools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;sys.path[:0]=[str(ROOT),str(P)]
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import mutual_info_regression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_absolute_error,accuracy_score,balanced_accuracy_score,roc_auc_score
from transformers import AutoTokenizer
import aligned_selector as alg
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
O=P/'mm';O.mkdir(exist_ok=True);OLD=ROOT/'experiments/strong_evidence_20261019_01'
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
plan=load(P/'protocol.json');methods=plan['methods'];assert sha(P/'aligned_selector.py')==plan['repair_source_sha256']
if (O/'execution_lock.json').exists():raise RuntimeError('refuse overwrite')
save('execution_lock.json',{'status':'FROZEN_BEFORE_TUNING','driver_sha256':sha(Path(__file__)),'algorithm_sha256':sha(P/'aligned_selector.py'),'protocol_sha256':sha(P/'protocol.json'),'hash_seed':os.environ.get('PYTHONHASHSEED')})
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
namespace={};src=(OLD/'mm/strict_select_enhanced.py.txt').read_text(encoding='utf8');exec(compile(src,str(O/'frozen_strict.py'),'exec'),ProfileSelector.select_enhanced.__globals__,namespace);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':namespace['select_enhanced']})
selection_cache={};counter_cache={}
def canonical(row,fields):return '\n'.join(f'{k}={row[k]}' for k in sorted(fields))
class Counter:
 def __init__(self,row,candidates):
  self.row=row;self.fields=[x.record_id for x in candidates];combos=[z for k in [1,2,3] for z in itertools.combinations(self.fields,k)];texts=[canonical(row,z) for z in combos];counts=[len(z) for z in tokenizer(texts,add_special_tokens=False)['input_ids']];self.count={frozenset(k):v for k,v in zip(combos,counts)};self.count[frozenset()]=0;self.all_fit=max(counts)<=32
 def __call__(self,ids):return self.count[frozenset(ids)]
def select(method,row,p,t,mi,cfg):
 eligible=[x for x in p.profile_records if x.sensitivity<=.7];ids={x.record_id for x in eligible};key=(p.student_id,tuple(ids));tc=counter_cache.get(key)
 if tc is None:tc=Counter(row,eligible);counter_cache[key]=tc
 trace={}
 if method.startswith('Repaired'):
  key=(tuple((x.record_id,x.type,x.knowledge,x.sensitivity) for x in eligible),t.text(),method,json.dumps(cfg,sort_keys=True)) if tc.all_fit else None
  if key is not None and key in selection_cache:s,trace=selection_cache[key]
  else:
   s,trace=alg.choose(eligible,t,tc,cfg,method)
   if key is not None:selection_cache[key]=(s,trace)
 elif method=='TrainMI':
  s=set()
  for field in mi:
   if len(s)<3 and field in ids and tc(s|{field})<=32:s.add(field)
 elif method=='SafeTaskTopK':
  cos,_,_=alg.attention_values(eligible,t,cfg['temperature']);order=sorted(range(len(eligible)),key=lambda i:(-float(cos[i]),eligible[i].record_id));s=set()
  for i in order:
   field=eligible[i].record_id
   if len(s)<3 and tc(s|{field})<=32:s.add(field)
 else:
  c=copy.deepcopy(r.CONFIG);c['fopd']['attention']={'top_k_dimensions':len(p.profile_records)};c['fopd']['unit_budget']['allowed']=sorted({x.type for x in eligible});c['fopd']['unit_budget']['distinct_requested_types']=['mastery'] if method=='TaskSlot-commonpool' else []
  picked=Frozen(c).select(p,t);s=set()
  for x in picked:
   field=x.record.record_id
   if field in ids and len(s)<3 and tc(s|{field})<=32:s.add(field)
 assert s<=ids and len(s)<=3 and tc(s)<=32
 # Exact measured canonical serialization, without padding or hidden vector release.
 assert len(tokenizer.encode(canonical(row,s),add_special_tokens=False))==tc(s)
 return set(s),trace,tc(s)
def fit_ridge(views,y,tr,dv):
 out=[]
 for alpha in [1.,10.,100.]:
  m=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),Ridge(alpha=alpha,solver='lsqr')).fit([views[i] for i in tr],y[tr]);out.append((float(mean_absolute_error(y[dv],m.predict([views[i] for i in dv]))),alpha,m))
 return min(out,key=lambda z:(z[0],z[1]))
def uci_view(row,s):return r.release(row,s)
datasets=[]
for subject,file,n in [('Math','student-mat.csv',395),('Portuguese','student-por.csv',649)]:
 rows=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n);parts=load(OLD/'mm'/(subject+'_split_LOCAL.json'));profiles=[(r.make_profile if subject=='Math' else make_portuguese_profile)(x,i) for i,x in enumerate(rows)];mi=r.train_mi_order(rows,np.array(parts['train']),20261019);datasets.append((subject,rows,profiles,parts,mi))
tuning=[]
for candidate in plan['tuning_grid']:
 cfg={**alg.DEFAULT,**candidate};losses=[]
 for subject,rows,profiles,parts,mi in datasets:
  used=parts['train']+parts['dev'];views={}
  for i in used:
   s,_,_=select('Repaired-Full',rows[i],*profiles[i],mi,cfg);views[i]=r.release(rows[i],s)
  y=np.array([float(x['G3']) for x in rows]);loss,alpha,m=fit_ridge(views,y,parts['train'],parts['dev']);losses.append({'subject':subject,'dev_MAE':loss,'alpha':alpha})
 tuning.append({'config':cfg,'dev_mean_MAE':float(np.mean([z['dev_MAE'] for z in losses])),'subjects':losses});save('tuning.json',tuning);print('dev_config',candidate,tuning[-1]['dev_mean_MAE'],flush=True)
chosen=min(tuning,key=lambda z:(z['dev_mean_MAE'],z['config']['projection_weight'],z['config']['temperature']))['config'];save('selected_config_lock.json',{'status':'FROZEN_BEFORE_FINAL_RECHECK_AND_NEW_FAMILIES','selected':chosen,'algorithm_sha256':sha(P/'aligned_selector.py'),'driver_sha256':sha(Path(__file__)),'new_task_test_evaluations_before_lock':0,'old_UCI_test_is_not_blind':True})
summaries=[];attackrows=[];paired=[]
for subject,rows,profiles,parts,mi in datasets:
 y=np.array([float(x['G3']) for x in rows]);tr,dv,ts=[parts[x] for x in ['train','dev','test']];preds={};selections={};traces={}
 for method in methods:
  start=time.perf_counter();sel=[];meta=[];lengths=[]
  for row,(p,t) in zip(rows,profiles):
   s,z,nt=select(method,row,p,t,mi,chosen);sel.append(s);meta.append(z);lengths.append(nt)
  selection_seconds=time.perf_counter()-start;views=[r.release(row,s) for row,s in zip(rows,sel)];_,alpha,m=fit_ridge(views,y,tr,dv);pred=m.predict([views[i] for i in ts]);preds[method]=pred;selections[method]=sel;traces[method]=meta
  for target,labeler in r.ATTACK_TARGETS.items():
   labels=np.array([labeler(x) for x in rows]);av=[r.release(x,s,target) for x,s in zip(rows,sel)]
   for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261019)),('RF',RandomForestClassifier(n_estimators=100,max_depth=6,min_samples_leaf=3,class_weight='balanced_subsample',random_state=20261019,n_jobs=1))]:
    model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit([av[i] for i in tr],labels[tr]);ap=model.predict([av[i] for i in ts]);prob=model.predict_proba([av[i] for i in ts])[:,1];attackrows.append({'dataset':subject,'method':method,'target':target,'attacker':name,'test_n':len(ts),'positive_count':int(labels[ts].sum()),'Accuracy':float(accuracy_score(labels[ts],ap)),'BA':float(balanced_accuracy_score(labels[ts],ap)),'AUC':float(roc_auc_score(labels[ts],prob))})
  z=[x for x in attackrows if x['dataset']==subject and x['method']==method];result={'dataset':subject,'status':'HISTORICAL_UCI_RECHECK','method':method,'train_n':len(tr),'dev_n':len(dv),'test_n':len(ts),'MAE':float(mean_absolute_error(y[ts],pred)),'BA_macro':float(np.mean([a['BA'] for a in z])),'AUC_macro':float(np.mean([a['AUC'] for a in z])),'fields_mean':float(np.mean([len(sel[i]) for i in ts])),'tokens_mean':float(np.mean([lengths[i] for i in ts])),'direct_private_exposure':float(np.mean([bool(sel[i]&r.PRIVATE) for i in ts])),'selection_seconds_all_rows':selection_seconds,'selection_ms_per_row':1000*selection_seconds/len(rows),'alpha':alpha,'failures':0,'necessary_recall':None}
  summaries.append(result);save(subject+'_'+method+'_LOCAL.json',{'selection_all':[sorted(s) for s in sel],'test_indices':ts,'prediction':pred.tolist(),'gold':y[ts].tolist(),'traces':meta,'tokens':lengths});save('summary.json',summaries);save('attacks.json',attackrows);print(subject,method,result['MAE'],flush=True)
 full=selections['Repaired-Full'];ft=traces['Repaired-Full']
 for method in methods:
  sel=selections[method];tt=traces[method];pair={'dataset':subject,'method':method,'n_records':len(ts),'projection_nonzero_rate':float(np.mean([tt[i].get('projection_nonzero',False) for i in ts])) if method.startswith('Repaired') else None,'top3_rank_changed_vs_repaired':float(np.mean([tt[i].get('rank',[])[:3]!=ft[i]['rank'][:3] for i in ts])) if method.startswith('Repaired') else None,'final_fields_changed_vs_repaired':float(np.mean([sel[i]!=full[i] for i in ts])),'prediction_changed_vs_repaired':float(np.mean(np.abs(preds[method]-preds['Repaired-Full'])>1e-10)),'net_positive_candidates_mean':float(np.mean([tt[i].get('net_positive_count',0) for i in ts])) if method.startswith('Repaired') else None,'slot_rank_changed_rate':float(np.mean([tt[i].get('rank',[])!=tt[i].get('pre_slot_rank',[]) for i in ts])) if method.startswith('Repaired') else None};paired.append(pair)
 save('paired_mechanisms.json',paired)
 # Paired descriptive old-cohort group intervals, never a new population CI.
 groups=np.array(['|'.join(rows[i][k] for k in 'school sex age address famsize Pstatus Medu Fedu Mjob Fjob reason nursery internet'.split()) for i in ts]);ug=np.unique(groups);ci=[]
 for reference in ['TrainMI','SafeTaskTopK']:
  d=np.abs(y[ts]-preds['Repaired-Full'])-np.abs(y[ts]-preds[reference]);rng=np.random.default_rng(20261019);boot=[float(np.mean(np.concatenate([d[groups==g] for g in rng.choice(ug,len(ug),replace=True)]))) for j in range(2000)];ci.append({'reference':reference,'delta_MAE_repaired_minus_reference':float(d.mean()),'conditional_group_bootstrap95':np.quantile(boot,[.025,.975]).tolist(),'scope':'historical inspected cohort, fixed fit; no independent confirmation'})
 save(subject+'_paired_intervals.json',ci)
save('completion.json',{'status':'COMPLETED_OLD_UCI_RECHECK','method_subject_cells':len(summaries),'separate_attack_cells':len(attackrows),'failures':0,'actual_LLM_calls':0,'paid_calls':0,'source_unchanged':sha(P/'aligned_selector.py')==plan['repair_source_sha256'],'selected_config':chosen})
