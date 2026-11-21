"""Offline exploratory UCI audit. No private values are exported in summaries."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import sys, json, copy, time, hashlib, inspect
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_absolute_error,accuracy_score,balanced_accuracy_score,roc_auc_score
from transformers import AutoTokenizer
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
OUT=Path(__file__).parent/'mm'; OUT.mkdir(exist_ok=True)
def save(name,x): (OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
METHODS=['FullProfile','NoProfile','RuleSummary','SafeTaskTopK-3','TrainMI-SafeTopK-3','MM-Original','MM-TaskSlot','Strict-Full','Strict-no-projection','Strict-no-attention','Strict-no-bottleneck','Strict-no-taskslot']
KEY='school sex age address famsize Pstatus Medu Fedu Mjob Fjob reason nursery internet'.split()
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
# Minimal experiment-only copy: decouple safety from projection; decouple refill
# from bottleneck removal; freeze candidate attention pool independently of ranking.
src=inspect.getsource(ProfileSelector.select_enhanced)
src=src.replace('and (not self.use_orthogonal or records[idx].sensitivity <= self.sensitivity_threshold)','and records[idx].sensitivity <= self.sensitivity_threshold')
src=src.replace('(not self.use_orthogonal or item.record.sensitivity <= self.sensitivity_threshold)','item.record.sensitivity <= self.sensitivity_threshold')
src=src.replace('if self.use_bottleneck:\n            distinct_types', 'if True:\n            distinct_types')
import textwrap
ns={}; exec(textwrap.dedent(src),ProfileSelector.select_enhanced.__globals__,ns)
Strict=type('StrictSelector',(ProfileSelector,),{'select_enhanced':ns['select_enhanced']})
(OUT/'strict_select_enhanced.py.txt').write_text(textwrap.dedent(src),encoding='utf8')
paths=[Path(__file__),ROOT/'experiments/mmfopd_uci/runner.py',ROOT/'protection/student_profile/src/fopd/profile_selector.py',ROOT/'protection/student_profile/src/fopd/task_attention.py',ROOT/'protection/student_profile/src/fopd/orthogonal_decoder.py']
hashes={str(p.relative_to(ROOT)):digest(p) for p in paths}
protocol={'status':'FROZEN_EXPLORATORY_OLD_DATA_RECHECK','seed':20261019,'methods':METHODS,'K':3,'token_count':'actual Qwen tokenizer on canonical field=value serialization, no padding','split':'global UCI merge-key groups 60/20/20; same cross-subject identity always same partition','independent_blind_test':False,'strict_ablation_scope':'experiment copy; same safety, all-record ranking candidate pool, taskslot refill and cap; full original separately','necessary_field_metrics':'NOT_APPLICABLE: UCI has no independent necessary-teaching-field gold','code_sha256':hashes,'attack_hyperparameters':'LR C=1 balanced; RF 100 depth6 leaf3 balanced_subsample; fixed in advance, both reported','ridge_alpha_dev':[1,10,100],'real_api_calls':0}
if (OUT/'protocol.json').exists(): raise RuntimeError('refuse overwrite')
save('protocol.json',protocol)
rows_by={s:r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/f).read_bytes(),n) for s,f,n in [('Math','student-mat.csv',395),('Portuguese','student-por.csv',649)]}
allkeys=sorted({tuple(x[k] for k in KEY) for rows in rows_by.values() for x in rows})
indices=np.arange(len(allkeys)); train,other=next(GroupShuffleSplit(n_splits=1,test_size=.4,random_state=20261019).split(indices,groups=indices)); de,te=next(GroupShuffleSplit(n_splits=1,test_size=.5,random_state=20261020).split(other,groups=other))
partition={allkeys[i]:part for part,ids in [('train',train),('dev',other[de]),('test',other[te])] for i in ids}
save('identity_audit.json',{'unique_merge_keys':len(allkeys),'cross_subject_shared_keys':len(set(tuple(x[k] for k in KEY) for x in rows_by['Math'])&set(tuple(x[k] for k in KEY) for x in rows_by['Portuguese'])),'warning':'merge key is proxy identity; no authoritative student IDs; uncertain duplicate groups remain together','by_subject':{s:{'rows':len(rows),'unique_keys':len({tuple(x[k] for k in KEY) for x in rows}),'exact_duplicate_rows':len(rows)-len({tuple(x.items()) for x in rows})} for s,rows in rows_by.items()}})
summaries=[]; attacks=[]; paired=[]
for subject,rows in rows_by.items():
 start=time.perf_counter(); profiles=[(r.make_profile if subject=='Math' else make_portuguese_profile)(x,i) for i,x in enumerate(rows)]
 split={p:np.array([i for i,x in enumerate(rows) if partition[tuple(x[k] for k in KEY)]==p]) for p in ['train','dev','test']}; tr,dv,ts=[split[p] for p in ['train','dev','test']]
 save(subject+'_split_LOCAL.json',{p:v.tolist() for p,v in split.items()})
 mi=r.train_mi_order(rows,tr,20261019); y=np.array([int(x['G3']) for x in rows]); subjectpred={}
 for method in METHODS:
  t0=time.perf_counter(); selected=[]; lengths=[]
  for i,(p,t) in enumerate(profiles):
   if method=='NoProfile': fields=set()
   elif method=='RuleSummary': fields={'studytime','failures','absences'}
   elif method in ['FullProfile','SafeTaskTopK-3','TrainMI-SafeTopK-3']: fields=r.select_fields(method,p,t,20261019,mi)
   else:
    cfg=copy.deepcopy(r.CONFIG); strict=method.startswith('Strict'); cfg['fopd']['unit_budget']['distinct_requested_types']=['mastery'] if method!='MM-Original' and method!='Strict-no-taskslot' else []
    if strict: cfg['fopd']['attention']={'top_k_dimensions':len(p.profile_records)}
    flag={'Strict-no-projection':'use_orthogonal','Strict-no-attention':'use_task_attention','Strict-no-bottleneck':'use_bottleneck'}.get(method)
    if flag: cfg['fopd']['components'][flag]=False
    fields={a.record.record_id for a in (Strict if strict else ProfileSelector)(cfg).select(p,t)}
   if method not in ['FullProfile','NoProfile']: assert len(fields)<=3 and not fields&r.PRIVATE,(method,fields)
   selected.append(fields); lengths.append(len(tokenizer.encode('\n'.join(f'{k}={rows[i][k]}' for k in sorted(fields)),add_special_tokens=False)))
  selection_seconds=time.perf_counter()-t0
  views=[r.release(x,f) for x,f in zip(rows,selected)]
  # Dummy feature keeps the actual empty release represented without adding information.
  views=[v if method!='NoProfile' else {'constant':1.} for v in views]
  candidates=[]
  for alpha in [1.,10.,100.]:
   model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),Ridge(alpha=alpha,solver='lsqr')).fit([views[i] for i in tr],y[tr]); candidates.append((mean_absolute_error(y[dv],model.predict([views[i] for i in dv])),alpha,model))
  _,alpha,model=min(candidates,key=lambda z:(z[0],z[1])); pred=model.predict([views[i] for i in ts]); subjectpred[method]=pred
  local=[]
  for target,labeler in r.ATTACK_TARGETS.items():
   labels=np.array([labeler(x) for x in rows]); av=[r.release(x,f,target) if method!='NoProfile' else {'constant':1.} for x,f in zip(rows,selected)]
   for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261019)),('RF',RandomForestClassifier(n_estimators=100,max_depth=6,min_samples_leaf=3,class_weight='balanced_subsample',random_state=20261019,n_jobs=1))]:
    atk=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit([av[i] for i in tr],labels[tr]); ap=atk.predict([av[i] for i in ts]); prob=atk.predict_proba([av[i] for i in ts])[:,1]
    a={'subject':subject,'method':method,'target':target,'attacker':name,'n':len(ts),'positive':int(labels[ts].sum()),'accuracy':float(accuracy_score(labels[ts],ap)),'BA':float(balanced_accuracy_score(labels[ts],ap)),'AUC':float(roc_auc_score(labels[ts],prob)),'explicit_target_rate':float(np.mean([target in selected[i] for i in ts]))}; attacks.append(a); local.append(a)
  result={'subject':subject,'method':method,'train_n':len(tr),'dev_n':len(dv),'test_n':len(ts),'mae':float(mean_absolute_error(y[ts],pred)),'fields':float(np.mean([len(selected[i]) for i in ts])),'tokens':float(np.mean([lengths[i] for i in ts])),'private_exposure':float(np.mean([bool(selected[i]&r.PRIVATE) for i in ts])),'attack_BA':float(np.mean([a['BA'] for a in local])),'attack_AUC':float(np.mean([a['AUC'] for a in local])),'alpha':alpha,'selection_seconds_all_rows':selection_seconds,'total_seconds':time.perf_counter()-t0,'failures':0,'field_frequencies':{k:float(np.mean([k in selected[i] for i in ts])) for k in r.INPUT_FIELDS}}
  summaries.append(result); save('summary.json',summaries); save('attacks.json',attacks)
  save(subject+'_'+method+'_LOCAL.json',{'fields':[sorted(f) for f in selected],'test_indices':ts.tolist(),'gold':y[ts].tolist(),'prediction':pred.tolist(),'actual_tokens':lengths})
  print(subject,method,result['mae'],flush=True)
 # Group bootstrap describes only this historically inspected cohort and fixed fit.
 groups=np.array(['|'.join(rows[i][k] for k in KEY) for i in ts]); unique=np.unique(groups); rng=np.random.default_rng(20261019)
 for method in METHODS:
  delta=np.abs(y[ts]-subjectpred[method])-np.abs(y[ts]-subjectpred['TrainMI-SafeTopK-3']); boot=[]
  for b in range(2000):
   draw=rng.choice(unique,len(unique),replace=True); boot.append(float(np.mean(np.concatenate([delta[groups==g] for g in draw]))))
  paired.append({'subject':subject,'method':method,'reference':'TrainMI-SafeTopK-3','delta_MAE':float(delta.mean()),'conditional_group_bootstrap_95':np.quantile(boot,[.025,.975]).tolist(),'scope':'descriptive fixed-fit old cohort; not independent confirmation or population guarantee'})
save('paired.json',paired)
assert hashes=={str(p.relative_to(ROOT)):digest(p) for p in paths}
save('completion.json',{'status':'COMPLETED','model_api_calls':0,'failed_fits':0,'summary_rows':len(summaries),'attacks':len(attacks)})
