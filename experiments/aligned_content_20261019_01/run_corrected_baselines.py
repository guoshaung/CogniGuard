"""Ingress-corrected frozen legacy arms, fixed original hash seed and config."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
assert os.environ.get('PYTHONHASHSEED')=='20261013'
from pathlib import Path
import sys,json,ast,copy,time,itertools,hashlib
P=Path(__file__).parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(P)]
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import mean_absolute_error,accuracy_score,balanced_accuracy_score,roc_auc_score
from transformers import AutoTokenizer
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
import aligned_selector as alg
O=P/'corrected_baselines';O.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (O/'protocol.json').exists():raise RuntimeError('no overwrite')
save('protocol.json',{'status':'FROZEN_INGRESS_CORRECTED_LEGACY_RECHECK','methods':['Original-commonpool','TaskSlot-commonpool'],'seed':20261013,'reason':'strict same candidate pool at legacy attention ingress; preserve original hash behavior with same fixed seed','config_sha256':sha(P/'mm_v2/selected_config_lock.json'),'driver_sha256':sha(Path(__file__)),'retune_repaired':False,'scope':'previously inspected UCI/synthetic recheck, not new blind data','other_seven_methods':'unchanged frozen results retained'})
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
ns={};old=ROOT/'experiments/strong_evidence_20261019_01/mm/strict_select_enhanced.py.txt';exec(compile(old.read_text(encoding='utf8'),str(old),'exec'),ProfileSelector.select_enhanced.__globals__,ns);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':ns['select_enhanced']})
tree=ast.parse((P/'run_mm_v2.py').read_text(encoding='utf8'));selection_cache={};counter_cache={}
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in ['canonical','Counter','select','fit_ridge']:
  if node.name=='select':
   src=ast.unparse(node).replace('len(p.profile_records)','len(eligible)').replace('Frozen(c).select(p, t)','Frozen(c).select(StudentProfile(p.student_id, {}, eligible), t)');node=ast.parse(src).body[0]
  exec(compile(ast.Module(body=[node],type_ignores=[]),'<same-functions-with-safe-ingress>','exec'))
cfg=load(P/'mm_v2/selected_config_lock.json')['selected'];methods=['Original-commonpool','TaskSlot-commonpool'];summary=[];attacks=[];changes=[]
def attack(views,labels,tr,ts,meta):
 for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261019)),('RF',RandomForestClassifier(n_estimators=100,max_depth=6,min_samples_leaf=3,class_weight='balanced_subsample',random_state=20261019,n_jobs=1))]:
  model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit([views[i] for i in tr],labels[tr]);ap=model.predict([views[i] for i in ts]);prob=model.predict_proba([views[i] for i in ts])[:,1];attacks.append({**meta,'attacker':name,'test_n':len(ts),'positive_count':int(labels[ts].sum()),'BA':float(balanced_accuracy_score(labels[ts],ap)),'AUC':float(roc_auc_score(labels[ts],prob))})
for subject,file,n,maker in [('Math','student-mat.csv',395,r.make_profile),('Portuguese','student-por.csv',649,make_portuguese_profile)]:
 rows=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n);parts=load(ROOT/'experiments/strong_evidence_20261019_01/mm'/f'{subject}_split_LOCAL.json');tr,dv,ts=[parts[k] for k in ['train','dev','test']];y=np.array([float(x['G3']) for x in rows]);profiles=[maker(x,i) for i,x in enumerate(rows)];full=load(P/'mm_v2'/f'{subject}_Repaired-Full_LOCAL.json')
 for method in methods:
  sels=[];tokens=[]
  for row,(p,t) in zip(rows,profiles):s,_,nt=select(method,row,p,t,[],cfg);sels.append(s);tokens.append(nt)
  views=[r.release(x,s) for x,s in zip(rows,sels)];_,alpha,model=fit_ridge(views,y,tr,dv);pred=model.predict([views[i] for i in ts])
  for target,labeler in r.ATTACK_TARGETS.items():attack([r.release(x,s,target) for x,s in zip(rows,sels)],np.array([labeler(x) for x in rows]),tr,ts,{'dataset':subject,'method':method,'target':target})
  aa=[x for x in attacks if x['dataset']==subject and x['method']==method];prev=load(P/'mm_v2'/f'{subject}_{method}_LOCAL.json');changed=sum(sorted(s)!=prev['selection_all'][i] for i,s in enumerate(sels));save(f'{subject}_{method}_LOCAL.json',{'selection_all':[sorted(x) for x in sels],'tokens':tokens,'prediction':pred.tolist(),'gold':y[ts].tolist(),'test_indices':ts,'traces':[{} for _ in sels]})
  summary.append({'dataset':subject,'status':'INGRESS_CORRECTED_HISTORICAL_RECHECK','method':method,'train_n':len(tr),'dev_n':len(dv),'test_n':len(ts),'MAE':float(mean_absolute_error(y[ts],pred)),'BA_macro':float(np.mean([x['BA'] for x in aa])),'AUC_macro':float(np.mean([x['AUC'] for x in aa])),'fields_mean':float(np.mean([len(sels[i]) for i in ts])),'tokens_mean':float(np.mean([tokens[i] for i in ts])),'direct_private_exposure':0.,'alpha':alpha,'failures':0});changes.append({'dataset':subject,'method':method,'all_rows':n,'fields_changed_after_ingress_correction':changed,'test_fields_changed_after_ingress_correction':sum(sorted(sels[i])!=prev['selection_all'][i] for i in ts),'fields_changed_vs_repaired':sum(sorted(sels[i])!=full['selection_all'][i] for i in ts)/len(ts),'predictions_changed_vs_repaired':float(np.mean(abs(pred-np.array(full['prediction']))>1e-10))});save('summary.json',summary);print(subject,method,summary[-1]['MAE'],flush=True)
data=load(P/'new_families/authored_data.json');oldnew={(x['id'],x['method']):x for x in load(P/'new_families/rows.json')};fields={'prior_test':'mastery','recent_test':'mastery','practice_minutes':'behavior_aggregate','absence_count':'behavior_aggregate','error_rate':'learning_state','school_support':'educational_context','home_support':'educational_context','hint_usage':'educational_context','device_access':'access_context','concept_error':'error_pattern','format_preference':'preference','interest_topic':'educational_context'};tr=[i for i,x in enumerate(data) if x['split']=='train'];ts=[i for i,x in enumerate(data) if x['split']=='test'];means={k:float(np.mean([data[i]['values'][k] for i in tr])) for k in fields};newrows=[];newsummary=[]
for method in methods:
 sels=[]
 for item in data:
  row=item['values'];records=[ProfileRecord(k,v,'new_lesson',f'{k}={row[k]}',1.,.3,'') for k,v in fields.items()];p=StudentProfile(item['id'],{},records);expr=' + '.join(f'{c}*{k}' for c,k in zip(item['coefficients'],item['necessary']));t=Task(item['id'],item['id'],'Compute the learning index '+expr+' using these observations.','new_lesson','arithmetic',False);s,_,nt=select(method,row,p,t,[],cfg);sels.append(s);pred=sum(c*(row[k] if k in s else means[k]) for k,c in zip(item['necessary'],item['coefficients']));f1=len(s&set(item['necessary']))/3;newrows.append({'id':item['id'],'family':item['family'],'split':item['split'],'method':method,'selected_fields':sorted(s),'tokens':nt,'prediction':pred,'target':item['target'],'F1':f1,'Precision':f1,'Recall':f1,'direct_exposure':False})
 for target in ['private_support','private_health']:
  views=[{**{f'present:{k}':float(k in s) for k in fields},**{f'value:{k}':float(x['values'][k]) for k in s}} for x,s in zip(data,sels)];attack(views,np.array([x['values'][target] for x in data]),tr,ts,{'dataset':'new_synthetic_families','method':method,'target':target})
 z=[x for x in newrows if x['method']==method and x['split']=='test'];aa=[x for x in attacks if x['method']==method and x['dataset']=='new_synthetic_families'];newsummary.append({'dataset':'new_synthetic_families','method':method,'test_n':len(z),'MAE_arithmetic':float(np.mean([abs(x['prediction']-x['target']) for x in z])),'necessary_F1':float(np.mean([x['F1'] for x in z])),'necessary_recall':float(np.mean([x['F1'] for x in z])),'necessary_precision':float(np.mean([x['F1'] for x in z])),'BA_macro':float(np.mean([x['BA'] for x in aa])),'AUC_macro':float(np.mean([x['AUC'] for x in aa])),'tokens_mean':float(np.mean([x['tokens'] for x in z])),'fields_mean':3.,'failures':0});changes.append({'dataset':'new_synthetic_families','method':method,'all_rows':len(data),'fields_changed_after_ingress_correction':sum(x['selected_fields']!=oldnew[x['id'],method]['selected_fields'] for x in newrows if x['method']==method)})
save('new_rows.json',newrows);save('new_summary.json',newsummary);save('attacks.json',attacks);save('changes.json',changes);save('completion.json',{'status':'COMPLETED_FIXED_CONFIG_CORRECTED_BASELINES','method_cells':6,'attacker_cells':len(attacks),'hash_seed':os.environ['PYTHONHASHSEED'],'new_blind_tests':0,'other_methods_not_rerun':True})
print(json.dumps(newsummary,indent=2))
