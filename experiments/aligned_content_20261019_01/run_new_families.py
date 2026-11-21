"""New synthetic heldout task families; public arithmetic, no real student data."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import sys,json,copy,hashlib,time,itertools
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;sys.path[:0]=[str(ROOT),str(P)]
import numpy as np
from sklearn.feature_selection import mutual_info_regression
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_absolute_error,accuracy_score,balanced_accuracy_score,roc_auc_score
from transformers import AutoTokenizer
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from experiments.mmfopd_uci.runner import CONFIG
import aligned_selector as alg
O=P/'new_families';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
lock=json.loads((P/'mm_v2/selected_config_lock.json').read_text(encoding='utf8'));cfg=lock['selected'];plan=json.loads((P/'protocol.json').read_text(encoding='utf8'));methods=plan['methods']
assert sha(P/'aligned_selector.py')==lock['algorithm_sha256']
fields={'prior_test':'mastery','recent_test':'mastery','practice_minutes':'behavior_aggregate','absence_count':'behavior_aggregate','error_rate':'learning_state','school_support':'educational_context','home_support':'educational_context','hint_usage':'educational_context','device_access':'access_context','concept_error':'error_pattern','format_preference':'preference','interest_topic':'educational_context'}
spec=[(['prior_test','recent_test','practice_minutes'],[1,2,1]),(['recent_test','absence_count','error_rate'],[2,-1,-1]),(['format_preference','concept_error','prior_test'],[1,3,2]),(['device_access','practice_minutes','home_support'],[1,2,1]),(['school_support','hint_usage','recent_test'],[1,-1,3]),(['absence_count','error_rate','home_support'],[2,1,1]),(['recent_test','concept_error','hint_usage'],[2,3,-1]),(['format_preference','device_access','error_rate'],[1,1,-2]),(['practice_minutes','absence_count','prior_test'],[1,-1,2]),(['interest_topic','school_support','concept_error'],[2,1,3])]
save('protocol.json',{'status':'FROZEN_NEW_SYNTHETIC_TASK_FAMILIES','seed':20261019,'train':200,'dev':40,'heldout':160,'task_families_train':[0,1,2,3,4],'task_families_dev':[5],'task_families_test':[6,7,8,9],'selected_config_lock_sha256':sha(P/'mm_v2/selected_config_lock.json'),'algorithm_sha256':sha(P/'aligned_selector.py'),'driver_sha256':sha(Path(__file__)),'spec':spec,'necessary':'three explicit operands of public weighted arithmetic task; teaching computation, not LLM quality','TrainMI':'task-conditioned MI using training rows and the public task formula, never test labels; stronger than a global train-MI ranking','prediction':'public expression using released operands; missing operands imputed by train means; real deterministic algorithm explicitly not LLM','scope':'new synthetic identities and heldout task combinations, author-designed schema; not independent real students or human-blind evaluation'})
rng=np.random.default_rng(20261019);data=[]
for family,(need,coef) in enumerate(spec):
 for j in range(40):
  values={k:int(rng.integers(1,21)) for k in fields};ps=int(rng.integers(0,2));ph=int(rng.integers(0,2));values['home_support']=int(np.clip(values['home_support']+4*ps,1,20));values['absence_count']=int(np.clip(values['absence_count']+3*ph,1,20));values['private_support']=ps;values['private_health']=ph
  data.append({'id':f'new-taskfamily-{family}-{j}','family':family,'split':'train' if family<5 else 'dev' if family==5 else 'test','values':values,'necessary':need,'coefficients':coef,'target':sum(c*values[k] for c,k in zip(coef,need))})
save('authored_data.json',data);train=[x for x in data if x['split']=='train'];test=[x for x in data if x['split']=='test'];tok=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True);means={k:float(np.mean([x['values'][k] for x in train])) for k in fields};mi={}
for family,(need,coef) in enumerate(spec):
 target=[sum(c*x['values'][k] for c,k in zip(coef,need)) for x in train];scores=mutual_info_regression(np.array([[x['values'][k] for k in fields] for x in train]),target,random_state=20261019);mi[family]=[k for _,k in sorted(zip(scores,fields),reverse=True)]
namespace={};old=ROOT/'experiments/strong_evidence_20261019_01/mm/strict_select_enhanced.py.txt';exec(compile(old.read_text(encoding='utf8'),str(old),'exec'),ProfileSelector.select_enhanced.__globals__,namespace);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':namespace['select_enhanced']})
traces=[];selected={m:[] for m in methods};preds={m:[] for m in methods};times={m:0. for m in methods};selectioncache={}
for item in data:
 row=item['values'];records=[ProfileRecord(k,typ,'new_lesson',f'{k}={row[k]}',1.,.30,'') for k,typ in fields.items()]+[ProfileRecord(k,'sensitive_profile','private',row[k],1.,.95,'') for k in ['private_support','private_health']];p=StudentProfile(item['id'],{},records);expression=' + '.join(f'{c}*{k}' for c,k in zip(item['coefficients'],item['necessary']));task=Task(item['id'],item['id'],'Compute the learning index '+expression+' using these observations.','new_lesson','arithmetic',False);eligible=records[:-2];ids=list(fields)
 combos=[z for n in [1,2,3] for z in itertools.combinations(ids,n)];strings=['\n'.join(f'{k}={row[k]}' for k in sorted(s)) for s in combos];length={frozenset(z):len(v) for z,v in zip(combos,tok(strings,add_special_tokens=False)['input_ids'])};length[frozenset()]=0;allfit=max(length.values())<=32;counter=lambda z:length[frozenset(z)]
 for method in methods:
  start=time.perf_counter();trace={}
  if method.startswith('Repaired'):
   key=(item['family'],method) if allfit else None
   if key is not None and key in selectioncache:s,trace=selectioncache[key]
   else:
    s,trace=alg.choose(eligible,task,counter,cfg,method)
    if key is not None:selectioncache[key]=(s,trace)
  elif method=='TrainMI':
   s=set()
   for k in mi[item['family']]:
    if len(s)<3 and counter(s|{k})<=32:s.add(k)
  elif method=='SafeTaskTopK':
   cos,_,_=alg.attention_values(eligible,task,cfg['temperature']);s=set()
   for i in sorted(range(len(eligible)),key=lambda i:(-float(cos[i]),eligible[i].record_id)):
    k=eligible[i].record_id
    if len(s)<3 and counter(s|{k})<=32:s.add(k)
  else:
   c=copy.deepcopy(CONFIG);c['fopd']['attention']={'top_k_dimensions':len(records)};c['fopd']['unit_budget']['allowed']=sorted(set(fields.values()));c['fopd']['unit_budget']['distinct_requested_types']=['mastery'] if method=='TaskSlot-commonpool' else [];s=set()
   for x in Frozen(c).select(p,task):
    k=x.record.record_id
    if k in fields and len(s)<3 and counter(s|{k})<=32:s.add(k)
  times[method]+=time.perf_counter()-start;assert len(s)<=3 and s<=set(fields) and counter(s)<=32;selected[method].append(s);pred=sum(c*(row[k] if k in s else means[k]) for c,k in zip(item['coefficients'],item['necessary']));preds[method].append(pred);tp=len(s&set(item['necessary']));prec=tp/len(s) if s else 0.;rec=tp/3
  traces.append({'id':item['id'],'family':item['family'],'split':item['split'],'method':method,'selected_fields':sorted(s),'Precision':prec,'Recall':rec,'F1':2*prec*rec/(prec+rec) if prec+rec else 0.,'tokens':counter(s),'prediction':pred,'target':item['target'],'projection_nonzero':trace.get('projection_nonzero'),'top3_rank':trace.get('rank',[])[:3],'net_positive_candidates':trace.get('net_positive_count'),'direct_exposure':False})
save('rows.json',traces);attacks=[];summary=[];trainids=[i for i,x in enumerate(data) if x['split']=='train'];testids=[i for i,x in enumerate(data) if x['split']=='test']
for method in methods:
 for target in ['private_support','private_health']:
  labels=np.array([x['values'][target] for x in data]);views=[{**{f'present:{k}':float(k in s) for k in fields},**{f'value:{k}':float(x['values'][k]) for k in s}} for x,s in zip(data,selected[method])]
  for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261019)),('RF',RandomForestClassifier(n_estimators=100,max_depth=6,min_samples_leaf=3,class_weight='balanced_subsample',random_state=20261019,n_jobs=1))]:
   model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit([views[i] for i in trainids],labels[trainids]);pred=model.predict([views[i] for i in testids]);prob=model.predict_proba([views[i] for i in testids])[:,1];attacks.append({'method':method,'target':target,'attacker':name,'n':len(testids),'positive_count':int(labels[testids].sum()),'Accuracy':float(accuracy_score(labels[testids],pred)),'BA':float(balanced_accuracy_score(labels[testids],pred)),'AUC':float(roc_auc_score(labels[testids],prob))})
 z=[x for x in traces if x['split']=='test' and x['method']==method];a=[x for x in attacks if x['method']==method];summary.append({'dataset':'new_synthetic_families','method':method,'test_n':len(z),'independent_test_task_families':4,'MAE_arithmetic':float(np.mean([abs(x['prediction']-x['target']) for x in z])),'necessary_recall':float(np.mean([x['Recall'] for x in z])),'necessary_precision':float(np.mean([x['Precision'] for x in z])),'necessary_F1':float(np.mean([x['F1'] for x in z])),'BA_macro':float(np.mean([x['BA'] for x in a])),'AUC_macro':float(np.mean([x['AUC'] for x in a])),'tokens_mean':float(np.mean([x['tokens'] for x in z])),'fields_mean':float(np.mean([len(x['selected_fields']) for x in z])),'projection_nonzero_rate':float(np.mean([bool(x['projection_nonzero']) for x in z])) if method.startswith('Repaired') else None,'selection_ms_per_row':1000*times[method]/len(data),'failures':0})
save('attacks.json',attacks);save('summary.json',summary);save('completion.json',{'status':'COMPLETED_ONCE_NEW_SYNTHETIC_HELDOUT_FAMILIES','n_profiles':400,'test_profiles':160,'test_families':4,'model_api_calls':0,'failures':0,'independent_human_blind':False,'config_changed_after_test':False,'no_population_CI':'only4 deliberately authored test families, no natural task population sampling'})
print(json.dumps(summary,indent=2))
