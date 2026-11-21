"""Calibration: how much attribute prediction already comes from public context?"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score,roc_auc_score
P=Path(__file__).parent;sys.path.insert(0,str(P));import selection_engine as e
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,z):(P/n).write_text(json.dumps(z,indent=2),encoding='utf8')
if (P/'public_context_attack.json').exists():raise RuntimeError('no overwrite')
save('public_context_attack_protocol.json',{'status':'POSTHOC_BACKGROUND_CALIBRATION','driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'private_fields_released':0,'not_a_K3_competitor':True,'purpose':'separate public module/stage/calendar attribute predictability from claims about release-caused risk; no new model selection','parameters':'same fixed LR/RF as primary experiment','cohorts':'same existing dev and forward holdout; no changes'})
allrows=load('dev_data/snapshots_LOCAL.json');train=[x for x in allrows if x['split']=='train'];trainviews=[e.view(x,[]) for x in train];out=[]
for attr in ['gender_F','disability_Y']:
 ytr=np.array([x[attr] for x in train])
 for name,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261020)),('RF',RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=20261020,n_jobs=1))]:
  m=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit(trainviews,ytr)
  for phase,rows in [('dev',[x for x in allrows if x['split']=='dev']),('test',load('test_data/snapshots_LOCAL.json'))]:
   views=[e.view(x,[]) for x in rows];y=np.array([x[attr] for x in rows]);pred=m.predict(views);prob=m.predict_proba(views)[:,1];out.append({'phase':phase,'attribute':attr,'attacker':name,'n_snapshots':len(rows),'BA':float(balanced_accuracy_score(y,pred)),'AUC':float(roc_auc_score(y,prob)),'scope':'public-only calibration, not a protected-release defense arm'})
save('public_context_attack.json',out);print(json.dumps(out,indent=2))
