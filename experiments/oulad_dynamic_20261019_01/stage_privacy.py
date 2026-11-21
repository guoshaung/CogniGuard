"""Stage disaggregation with identical main-run attacker fits; no extra tuning."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
assert os.environ.get('PYTHONHASHSEED')=='20261013'
from pathlib import Path
import json,sys,hashlib,collections
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score,roc_auc_score
P=Path(__file__).parent;sys.path.insert(0,str(P));import design as d;import selection_engine as e
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if not (P/'stage_privacy_protocol.json').exists():
 save('stage_privacy_protocol.json',{'status':'FROZEN_DIAGNOSTIC_BEFORE_HELDOUT_COMPLETION','driver_sha256':sha(Path(__file__)),'main_test_completion_exists':(P/'test_results/completion.json').exists(),'purpose':'same main LR/RF fits, disaggregate prediction BA/AUC by42/98/154; also mean-probability pooling by student','no_new_hyperparameters':True,'no_better_attacker_selection':True,'pooled_scope':'mean of snapshot probabilities, NOT an optimal cumulative-history attacker','verification':'all reconstructed overall BA/AUC must match main run within1e-10','if_one_class':'report NA rather than manufacture AUC'})
assert load('stage_privacy_protocol.json')['driver_sha256']==sha(Path(__file__))
if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='freeze':print('FROZEN');sys.exit(0)
if (P/'stage_privacy_results.json').exists():raise RuntimeError('no overwrite')
main=load('test_results/attacks.json');train=[x for x in load('dev_data/snapshots_LOCAL.json') if x['split']=='train'];evalrows=load('test_data/snapshots_LOCAL.json');cases={(x['student'],x['cutoff'],x['intent'],x['wording'],x['method']):x for x in load('test_results/cases_LOCAL.json')};mi=load('test_results/TrainMI_train_only.json')['order']
from transformers import AutoTokenizer
e.tokenizer=AutoTokenizer.from_pretrained(str(P.parents[1]/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
class ExactLazyCounter:
 def __init__(self,row):self.row=row;self.count={frozenset():0};self.all_fit=False
 def __call__(self,fields):
  key=frozenset(fields)
  if key not in self.count:self.count[key]=len(e.tokenizer.encode(e.payload(self.row,key),add_special_tokens=False))
  return self.count[key]
# Exact train payloads are required for matching fits. Compute once per context.
counters=[ExactLazyCounter(x) for x in train];results=[];matches=[]
for intent in d.INTENTS:
 for wording in ['explicit','ambiguous']:
  for method in d.METHODS:
   if method.startswith('Repaired'):
    # Full optimizer is metadata-only when unconstrained optimum is feasible.
    # Cached optimum per stage is verified with true token counts for every row.
    metadata_choices={}
    for stage in d.CUTOFFS:
     row=next(x for x in train if x['cutoff']==stage)
     class AllFeasible:
      all_fit=True
      def __call__(self,fields):return 0
     # Call underlying choose directly, avoiding final actual-token assertions.
     from protection.common.schemas import ProfileRecord,Task
     records=[ProfileRecord(k,t,'oulad','meta',1.,s,'') for k,(t,s,r,desc) in d.FIELDS.items()];task=Task('oulad','meta',f'Task purpose {intent}. '+d.question(intent,wording,stage),'oulad','development',False);selected,_=e.alg.choose(records,task,lambda _:0,d.CFG,method);metadata_choices[stage]=sorted(selected)
    sels=[]
    for row,tc in zip(train,counters):
     chosen=metadata_choices[row['cutoff']]
     if tc(chosen)>64:chosen=e.select(method,row,intent,wording,tc,mi)[0]
     sels.append(chosen)
   else:sels=[e.select(method,row,intent,wording,tc,mi)[0] for row,tc in zip(train,counters)]
   trainviews=[e.view(x,s) for x,s in zip(train,sels)];evviews=[e.view(x,cases[x['student'],x['cutoff'],intent,wording,method]['selected_fields']) for x in evalrows]
   for attr in ['gender_F','disability_Y']:
    ytr=np.array([x[attr] for x in train]);yev=np.array([x[attr] for x in evalrows])
    for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261020)),('RF',RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=20261020,n_jobs=1))]:
     model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit(trainviews,ytr);pred=model.predict(evviews);prob=model.predict_proba(evviews)[:,1];ba=float(balanced_accuracy_score(yev,pred));auc=float(roc_auc_score(yev,prob));reference=next(x for x in main if x['intent']==intent and x['wording']==wording and x['method']==method and x['attribute']==attr and x['attacker']==name);assert abs(ba-reference['BA'])<1e-10 and abs(auc-reference['AUC'])<1e-10;matches.append(True)
     for stage in d.CUTOFFS:
      ix=np.array([i for i,x in enumerate(evalrows) if x['cutoff']==stage]);yy=yev[ix];one=len(np.unique(yy))<2;results.append({'intent':intent,'wording':wording,'method':method,'attribute':attr,'attacker':name,'subgroup':'stage','value':stage,'n':len(ix),'positive':int(yy.sum()),'negative':int(len(yy)-yy.sum()),'BA':None if one else float(balanced_accuracy_score(yy,pred[ix])),'AUC':None if one else float(roc_auc_score(yy,prob[ix])),'status':'NA_ONE_CLASS' if one else 'COMPLETED'})
     ids=sorted({x['student'] for x in evalrows});groups=[[i for i,x in enumerate(evalrows) if x['student']==sid] for sid in ids];py=np.array([yev[g[0]] for g in groups]);pp=np.array([float(prob[g].mean()) for g in groups]);results.append({'intent':intent,'wording':wording,'method':method,'attribute':attr,'attacker':name,'subgroup':'student_mean_probability','value':'all_stages','n':len(ids),'positive':int(py.sum()),'negative':int(len(py)-py.sum()),'BA':float(balanced_accuracy_score(py,pp>=.5)),'AUC':float(roc_auc_score(py,pp)),'status':'COMPLETED','scope':'simple probability pooling; not a cumulative attacker trained on joined history'})
   save('stage_privacy_results.json',results);print('privacy_stage',intent,wording,method,flush=True)
save('stage_privacy_completion.json',{'status':'COMPLETED','source_sha256':sha(Path(__file__)),'main_attack_cells_exactly_matched':len(matches),'stage_and_pooled_cells':len(results),'one_class_cells':sum(x['status']!='COMPLETED' for x in results),'LLM_calls':0,'tuning':False})
