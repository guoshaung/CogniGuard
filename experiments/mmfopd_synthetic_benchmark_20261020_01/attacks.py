"""Student-disjoint actual-wire attacks, plus an explicitly proxy-only diagnostic."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import json,sys,hashlib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score,balanced_accuracy_score,accuracy_score
from generator import FIELDS
P=Path(__file__).parent;KEYS=list(FIELDS)+[f'history_noise_{j}' for j in range(8)];PUB=50
def run(phase):
    out=P/('attacks_dev' if phase=='dev' else 'attacks_test');out.mkdir(exist_ok=False)
    if phase=='dev':
        raw=np.load(P/'var/results/dev/features_LOCAL.npz');tasks=[json.loads(x) for x in (P/'data/dev/tasks.jsonl').read_text().splitlines()]
        fit=np.array([int(t['student_id'][3:])%10<7 for t in tasks]);ev=~fit;train=raw;test=raw
    else:
        lock=json.loads((P/'final_freeze.json').read_text());assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in lock['sources'].items())
        train=np.load(P/'var/results/train/features_LOCAL.npz');test=np.load(P/'var/results/test/features_LOCAL.npz');fit=slice(None);ev=slice(None)
    yt=train['labels'][fit];yv=test['labels'][ev]
    execution=json.loads((P/('var/results/dev/execution.json' if phase=='dev' else 'var/results/test/execution.json')).read_text());arms=execution['arms'];rows=[];predictions={};cache={}
    def fitone(method,k,scope,xt,xv):
        fingerprint=hashlib.sha256(xt.tobytes()+xv.tobytes()).hexdigest()
        for ai,attr in enumerate(['gender_F','disability_Y']):
            for kind in ['LR','RF']:
                key=(fingerprint,ai,kind)
                if key in cache:prob,pred=cache[key]
                else:
                    est=LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261020) if kind=='LR' else RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=20261020,n_jobs=1)
                    model=make_pipeline(StandardScaler(with_mean=False),est).fit(xt,yt[:,ai]);prob=model.predict_proba(xv)[:,1];pred=model.predict(xv);cache[key]=(prob,pred)
                label=f'{method}|{k}|{scope}|{attr}|{kind}';predictions[label+'|prob']=prob.astype(np.float32);predictions[label+'|pred']=pred.astype(np.int8)
                rows.append({'method':method,'K':k,'scope':scope,'attribute':attr,'attacker':kind,'n_train_cases':len(yt),'n_eval_cases':len(yv),'positive_eval_cases':int(yv[:,ai].sum()),'AUC':float(roc_auc_score(yv[:,ai],prob)),'BA':float(balanced_accuracy_score(yv[:,ai],pred)),'Accuracy':float(accuracy_score(yv[:,ai],pred)),'prediction_key':label})
    xt=np.zeros_like(train['arm0'][fit]);xv=np.zeros_like(test['arm0'][ev]);xt[:,:PUB]=train['public'][fit];xv[:,:PUB]=test['public'][ev]
    fitone('Public-only',0,'public',xt,xv)
    for j,(method,k) in enumerate(arms):
        if phase=='dev' and k!=3:continue
        xt=train[f'arm{j}'][fit].copy();xv=test[f'arm{j}'][ev].copy();fitone(method,k,'actual_release',xt,xv)
        for name in ['gender_F','disability_Y']:
            index=PUB+KEYS.index(name)*3;xt[:,index:index+3]=0.;xv[:,index:index+3]=0.
        fitone(method,k,'proxy_only_ignores_direct_attributes',xt,xv)
        (out/'metrics.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
        print('attacks',phase,method,k,flush=True)
    np.savez_compressed(out/'predictions.npz',**predictions,labels=yv)
    (out/'execution.json').write_text(json.dumps({'status':'COMPLETED','phase':phase,'metric_rows':len(rows),'unique_fitted_attackers':len(cache),'no_target_labels_in_features':True,'same_feature_dimension_for_public_and_release':xt.shape[1],'proxy_scope':'same actual wire; diagnostic attacker voluntarily ignores both direct attribute triplets, including their presence. Not an output repair.','student_disjoint':'train/test official split' if phase!='dev' else '350 fit /150 dev students by stable id split','paid_calls':0},indent=2),encoding='utf8')
if __name__=='__main__':run(sys.argv[1])
