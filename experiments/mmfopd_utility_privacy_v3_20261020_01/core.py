"""One actual6-component wire interface; no hidden extra features for attacks."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score,balanced_accuracy_score,accuracy_score
P=Path(__file__).parent;ROOT=P.parents[1];OLD=ROOT/'experiments/oulad_dynamic_20261019_01';V2=ROOT/'experiments/mmfopd_orthogonal_privacy_v2_20261019_01'
sys.path[:0]=[str(OLD),str(ROOT),str(P/'vendor')]
import design as d
FIELDS=list(d.FIELDS);ATTRS=['gender_F','disability_Y'];CONTEXTS=[(i,w) for i in d.INTENTS for w in ['explicit','ambiguous']]
TOKENIZER=None
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dataset():
    rows=load(OLD/'dev_data/snapshots_LOCAL.json');tr=[r for r in rows if r['split']=='train'];dv=[r for r in rows if r['split']=='dev']
    assert len(tr)==1337 and len(dv)==473
    assert {x['student'] for x in tr}.isdisjoint({x['student'] for x in dv})
    assert all(x['presentation']=='2013J' for x in tr+dv)
    return tr,dv
def field_sets(intent,wording,attention=True,historical=False):
    if historical:
        cc=[x for x in load(OLD/'dev_results/cases_LOCAL.json') if x['method']=='Repaired-Full' and x['intent']==intent and x['wording']==wording]
        choices={tuple(sorted(FIELDS.index(k) for k in x['selected_fields'])) for x in cc}
    elif attention:
        templates=load(V2/'readout_templates.json')
        choices={tuple(sorted(FIELDS.index(k) for k in templates[f'{intent}|{wording}|{c}']['fields'])) for c in d.CUTOFFS}
    else:choices={tuple(sorted(FIELDS.index(k) for k in load(OLD/'dev_results/TrainMI_train_only.json')['order'][:3]))}
    assert len(choices)==1,'Stage-varying field identities require a separately frozen adapter; stop'
    indices=list(next(iter(choices)));assert len(indices)==3 and all(d.FIELDS[FIELDS[k]][1]<=.7 for k in indices)
    return indices
def public(row):return {f'public:module={row["module"]}':1.,'public:cutoff':float(row['cutoff']),'public:days_to_due':float(row['target_due']-row['cutoff'])}

class Encoder:
    def __init__(self,indices):self.indices=indices
    def raw(self,rows):return np.array([[r['values'][FIELDS[j]] if r['values'][FIELDS[j]] is not None else np.nan for j in self.indices] for r in rows],float)
    def fit(self,rows):
        a=self.raw(rows);self.median=np.nanmedian(a,axis=0);assert np.isfinite(self.median).all()
        x=np.where(np.isnan(a),self.median,a);self.mean=x.mean(0);sd=x.std(0);self.scale=np.where(sd<1e-12,1.,sd);return self
    def transform(self,rows):
        a=self.raw(rows);return (np.where(np.isnan(a),self.median,a)-self.mean)/self.scale,np.isnan(a).astype(int)
    def state(self):return {'indices':self.indices,'fields':[FIELDS[j] for j in self.indices],'median':self.median.tolist(),'mean':self.mean.tolist(),'scale':self.scale.tolist()}

def wire(v,m,indices):
    assert np.isfinite(v).all() and len(v)==len(m)==len(indices)==3
    assert set(np.asarray(m).tolist())<={0,1}
    return 'f='+','.join(str(i) for i in indices)+'\n'+'\n'.join([f'h{i}={float(v[i]):.3f}' for i in range(3)]+[f'm{i}={int(m[i])}' for i in range(3)])
def parse(payload,row):
    pairs=dict(line.split('=') for line in payload.splitlines());assert set(pairs)=={'f','h0','h1','h2','m0','m1','m2'}
    indices=[int(s) for s in pairs['f'].split(',')];assert len(set(indices))==3 and all(0<=i<len(FIELDS) for i in indices)
    out=public(row)
    for j,i in enumerate(indices):
        out[f'schema:{j}:{FIELDS[i]}']=1.
        out[f'h{j}']=float(pairs[f'h{j}']);out[f'm{j}']=float(pairs[f'm{j}']);assert out[f'm{j}'] in [0.,1.]
    return out
def emit(rows,enc,t):
    v,m=enc.transform(rows);vp=(v-t['bias'])@t['P'].T+t['bias']
    payloads=[wire(x,b,enc.indices) for x,b in zip(vp,m)]
    views=[parse(w,r) for w,r in zip(payloads,rows)]
    return views,payloads,v,vp,m
def token_counts(wires):
    global TOKENIZER
    if TOKENIZER is None:
        from transformers import AutoTokenizer
        TOKENIZER=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
    ns=np.array([len(z) for z in TOKENIZER(wires,add_special_tokens=False)['input_ids']]);assert ns.max()<=64
    return ns
def basis(x):
    u,s,_=np.linalg.svd(x,full_matrices=False);return u[:,s>1e-10]
def crosscov(v,s):return (v-v.mean(0)).T@(s-s.mean(0))/(len(v)-1)
def identity():return {'P':np.eye(3),'bias':np.zeros(3)}
def covariance_projection(v,s,rank=2):
    u=basis(crosscov(v,s))[:,:rank];return {'P':np.eye(3)-u@u.T,'bias':v.mean(0)}
def predictor():return make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),Ridge(alpha=10.,solver='lsqr'))
def attacker(kind):
    clf=LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261020) if kind=='LR' else RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=20261020,n_jobs=1)
    return make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),clf)
def attack_fit(xt,xv,yt,yv,kind):
    model=attacker(kind).fit(xt,yt);prob=model.predict_proba(xv)[:,1];pred=model.predict(xv)
    return {'AUC':float(roc_auc_score(yv,prob)),'BA':float(balanced_accuracy_score(yv,pred)),'Accuracy':float(accuracy_score(yv,pred))},prob,pred
def background(tr,dv):
    out=[];local={}
    for attr in ATTRS:
        yt=np.array([r[attr] for r in tr]);yv=np.array([r[attr] for r in dv])
        for kind in ['LR','RF']:
            metrics,prob,pred=attack_fit([public(r) for r in tr],[public(r) for r in dv],yt,yv,kind)
            out.append({'attribute':attr,'attacker':kind,**metrics});local[attr+'|'+kind]={'prob':prob.tolist(),'pred':pred.tolist()}
    return out,local

def evaluate(method,tr,dv,enc,t,intent,wording,bg,fit_attacks=True):
    start=time.perf_counter();xt,wt,vt,vpt,mt=emit(tr,enc,t);xv,wv,vv,vpv,mv=emit(dv,enc,t);encode_s=time.perf_counter()-start
    nt=token_counts(wt);nv=token_counts(wv)
    yt=np.array([r['target_score'] for r in tr]);yv=np.array([r['target_score'] for r in dv])
    model=predictor().fit(xt,yt);pred=np.clip(model.predict(xv),0,100)
    available=np.array([r['target_observed'] for r in dv]);dist=float(np.sum((vpv-vv)**2)/max(1e-30,np.sum(vv**2)))
    required=set(d.INTENTS[intent]['required']);source_recall=len({FIELDS[i] for i in enc.indices}&required)/3
    summary={'method':method,'intent':intent,'wording':wording,'n_snapshots':len(dv),'n_students':len({r['student'] for r in dv}),
        'MAE':float(np.mean(abs(pred-yv))),'observed_MAE':float(np.mean(abs(pred[available]-yv[available]))),'observed_n':int(available.sum()),
        'relative_squared_distortion':dist,'actual_tokens_mean':float(nv.mean()),'actual_tokens_max':int(nv.max()),
        'representation_dimensions':6,'source_fields':3,'source_schema_recall_proxy':source_recall,
        'source_missing_fraction':float(mv.mean()),'missing_flags_preserved_rate':1.,'value_code_semantics':'latent numerical code; not original facts',
        'wire_bytes_mean':float(np.mean([len(w.encode('utf8')) for w in wv])),
        'encoding_projection_serialization_ms_per_row':1000*encode_s/(len(tr)+len(dv)),
        'projection_rank_removed':3-int(np.linalg.matrix_rank(t['P'],tol=1e-8)),
        'P_symmetry_error':float(np.linalg.norm(t['P']-t['P'].T)),'P_idempotence_error':float(np.linalg.norm(t['P']@t['P']-t['P'])),
        'actual_payload_changed_rate':float(np.mean([w!=wire(v,m,enc.indices) for w,v,m in zip(wv,vv,mv)])),
        'failures':0}
    attacks=[];local={'prediction':pred.tolist(),'wire':wv,'error':abs(pred-yv).tolist(),'attacks':{}}
    if fit_attacks:
        for attr in ATTRS:
            for kind in ['LR','RF']:
                met,prob,ap=attack_fit(xt,xv,np.array([r[attr] for r in tr]),np.array([r[attr] for r in dv]),kind)
                b=next(x for x in bg if x['attribute']==attr and x['attacker']==kind)
                attacks.append({'method':method,'intent':intent,'wording':wording,'attribute':attr,'attacker':kind,'scope':'actual_wire_plus_public','n':len(dv),**met,
                    'delta_AUC_vs_public':met['AUC']-b['AUC'],'nonnegative_excess_AUC':max(0.,met['AUC']-b['AUC']),'delta_BA_vs_public':met['BA']-b['BA']})
                local['attacks'][attr+'|'+kind]={'prob':prob.tolist(),'pred':ap.tolist()}
    return summary,attacks,local,model
