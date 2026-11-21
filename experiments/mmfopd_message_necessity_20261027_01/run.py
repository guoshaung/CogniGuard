"""Frozen single-message proxy experiment. Train first, evaluate dev exactly once."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',RAYON_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',CUDA_VISIBLE_DEVICES='-1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import ast,csv,datetime,hashlib,json,sys,time,warnings,traceback,collections
import numpy as np
import joblib
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_regression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
from threadpoolctl import threadpool_limits,threadpool_info
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from core.paths import PROJECT_ROOT
assert ROOT==PROJECT_ROOT
SAFE=['older_score','latest_score','score_delta','completion_rate','overdue_count','clicks_recent','clicks_earlier','active_days','inactive_days','forum_share','content_share','previous_attempts','studied_credits']
ALL=SAFE+['module','cutoff','days_to_due'];METHODS=['M0','M1','M2','M3','M4'];ATTRS=['gender_F','disability_Y'];KINDS=['LR','RF']
PUBLIC={'public:task=next_TMA_score':1.0}
ALLOWED=set(ALL)|{k+'_bin' for k in ALL}|{'predicted_score'}
def now():return datetime.datetime.now(datetime.timezone.utc)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,v):
    path=P/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def load(name):return json.loads((P/name).read_text(encoding='utf8'))
def csvout(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r));path=P/name
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def pseudo(s):return 'S'+hashlib.sha256(('message-necessity-20261027|'+str(s)).encode()).hexdigest()[:12]
def field_value(r,k):
    if k in SAFE:return r['values'][k]
    if k=='module':return r['module']
    if k=='cutoff':return float(r['cutoff'])
    if k=='days_to_due':return float(r['target_due']-r['cutoff'])
    raise ValueError('Forbidden source field '+k)
def num(v):return str(float(v))
def raw_pairs(r,fields):return [(k,'NA' if field_value(r,k) is None else (str(field_value(r,k)) if k=='module' else num(field_value(r,k)))) for k in fields]
def parse(wire):
    out={}
    for line in wire.splitlines():
        k,v=line.split('=',1)
        if k not in ALLOWED or k in out:raise ValueError('Forbidden/duplicate message field')
        if v=='NA':out[k]=None
        elif k=='module':
            if v not in ['BBB','DDD','FFF']:raise ValueError('Unknown course category')
            out[k]=v
        elif k.endswith('_bin'):
            if v not in ['low','mid','high','BBB','DDD','FFF']:raise ValueError('Bad summary category')
            out[k]=v
        else:
            x=float(v)
            if not np.isfinite(x):raise ValueError('Nonfinite value')
            out[k]=x
    return out
def emit(pairs,tokenizer,cap=None):
    chosen=[];dropped=[]
    for k,v in pairs:
        tentative='\n'.join([*(a+'='+b for a,b in chosen),k+'='+v])
        nt=len(tokenizer.encode(tentative,add_special_tokens=False).ids)
        if cap is None or nt<=cap:chosen.append((k,v))
        else:dropped.append(k)
    wire='\n'.join(k+'='+v for k,v in chosen);view=parse(wire)
    return {'wire':wire,'parsed':view,'tokens':len(tokenizer.encode(wire,add_special_tokens=False).ids),'bytes':len(wire.encode('utf8')),'items':len(view),'NA':sum(v is None for v in view.values()),'absent_items':len(dropped),'dropped':dropped}
def summary_pairs(r,fields,thresholds):
    out=[]
    for k in fields:
        v=field_value(r,k)
        if v is None:c='NA'
        elif k=='module':c=str(v)
        else:
            low,high=thresholds[k];c='low' if v<=low else ('mid' if v<=high else 'high')
        out.append((k+'_bin',c))
    return out
def medians(views):
    keys=set().union(*(v.keys() for v in views));out={}
    for k in keys:
        if k=='module' or k.endswith('_bin'):continue
        values=[v[k] for v in views if k in v and v[k] is not None]
        out[k]=float(np.median(values)) if values else 0.0
    return out
def encode(views,med):
    result=[]
    for view in views:
        x=dict(PUBLIC)
        for k,v in view.items():
            assert k in ALLOWED
            x['present:'+k]=1.;x['missing:'+k]=float(v is None)
            if k=='module' or k.endswith('_bin'):
                x['category:'+k+'='+('NA' if v is None else str(v))]=1.
            else:x['value:'+k]=med.get(k,0.) if v is None else float(v)
        result.append(x)
    return result
def union(auth,views):
    return [{**a,**v} for a,v in zip(auth,views)]
class Ledger:
    def __init__(self,cfg):self.cfg=cfg;self.count=0
    def log(self,event,**kw):
        row={'utc':now().isoformat(),'event':event,**kw}
        with (P/'run_log.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    def fit(self,name,fn):
        if now()>=datetime.datetime.fromisoformat(self.cfg['stop_new_fits_utc']):raise RuntimeError('STOP_NEW_FITS_70_MINUTE_DEADLINE')
        if self.count>=self.cfg['fit_limit']:raise RuntimeError('FIT_BUDGET_EXHAUSTED')
        self.count+=1;fid=self.count;self.log('FIT_START',fit_id=fid,name=name);start=time.perf_counter()
        try:
            with warnings.catch_warnings(record=True) as warns:
                warnings.simplefilter('always');value=fn()
            self.log('FIT_END',fit_id=fid,name=name,seconds=time.perf_counter()-start,warnings=[str(w.message) for w in warns]);print('FIT',fid,name,flush=True);return value
        except Exception as e:self.log('FIT_FAILED',fit_id=fid,name=name,error=repr(e));raise
def estimator(kind,cfg):
    if kind=='Ridge':z=Ridge(alpha=cfg['ridge_alpha'],solver='lsqr')
    elif kind=='LR':z=LogisticRegression(C=1.,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=cfg['attacker_seed'])
    elif kind=='RF':z=RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=cfg['attacker_seed'],n_jobs=2)
    else:raise ValueError(kind)
    return make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),z)
def fit_bundle(name,views,y,kind,cfg,ledger):
    med=medians(views);x=encode(views,med);model=ledger.fit(name,lambda:estimator(kind,cfg).fit(x,y))
    bundle={'median':med,'pipeline':model,'kind':kind,'fit_on':'train or train-only grouped subfold'}
    dst=P/'models_LOCAL'/(name+'.joblib');dst.parent.mkdir(exist_ok=True);joblib.dump(bundle,dst)
    return bundle
def predict(bundle,views,prob=False):
    x=encode(views,bundle['median']);model=bundle['pipeline']
    return model.predict_proba(x)[:,1] if prob else model.predict(x)
def interval(v):return [float(x) for x in np.quantile(v,[.025,.975])]
def aucboot(y,p,w):
    order=np.argsort(p,kind='stable');pr=p[order];starts=np.r_[0,np.flatnonzero(pr[1:]!=pr[:-1])+1]
    pos=np.add.reduceat(w[:,order]*y[order],starts,axis=1);neg=np.add.reduceat(w[:,order]*(1-y[order]),starts,axis=1);den=pos.sum(1)*neg.sum(1)
    return np.divide(np.sum(pos*(np.cumsum(neg,axis=1)-.5*neg),axis=1),den,out=np.full(len(w),np.nan),where=den>0)
def main():
    cfg=load('config.json');audit=load('audit.json');freeze=load('protocol_freeze.json')
    assert all(sha(P/n)==h for n,h in freeze['sha256'].items())
    assert all(sha(ROOT/n)==h for n,h in audit['sources_sha256'].items())
    if (P/'execution_lock.json').exists():raise RuntimeError('No overwrite: run already started')
    source_names=['run.py','audit.py','report.py','test_contract.py','config.json','PROTOCOL.md']
    assert all((P/n).exists() for n in source_names)
    save('execution_lock.json',{'status':'FROZEN_BEFORE_FIRST_FIT','utc':now().isoformat(),'source_sha256':{n:sha(P/n) for n in source_names},'input_sha256':audit['sources_sha256'][cfg['cache']],'expected_fits':45,'dev_evaluations_started':0})
    ledger=Ledger(cfg);start=time.perf_counter()
    try:
      with threadpool_limits(limits=1):
        rows=json.loads((ROOT/cfg['cache']).read_text());tr=[r for r in rows if r['split']=='train'];dv=[r for r in rows if r['split']=='dev']
        assert len(tr)==1337 and len(dv)==473 and {r['presentation'] for r in rows}=={'2013J'}
        assert {r['student'] for r in tr}.isdisjoint({r['student'] for r in dv})
        from tokenizers import Tokenizer
        tok=Tokenizer.from_file(str(ROOT/cfg['tokenizer']))
        y=np.array([r['target_score'] for r in tr]);labels={s:np.array([r[s] for r in tr]) for s in ATTRS}
        # All feature selection, quantiles, transforms and fits below use TRAIN only.
        matrix=np.array([[float(sorted({r['module'] for r in tr}).index(field_value(r,k))) if k=='module' else (np.nan if field_value(r,k) is None else field_value(r,k)) for k in ALL] for r in tr])
        med=np.nanmedian(matrix,axis=0);matrix=np.where(np.isnan(matrix),med,matrix)
        mi=ledger.fit('train_MI_selection',lambda:mutual_info_regression(matrix,y,discrete_features=np.array([k in ['module','cutoff'] for k in ALL]),n_neighbors=3,random_state=cfg['seed']))
        order=sorted(ALL,key=lambda k:(-mi[ALL.index(k)],k));selected=order[:3];thresholds={}
        for k in selected:
            if k!='module':thresholds[k]=np.quantile([field_value(r,k) for r in tr if field_value(r,k) is not None],cfg['summary_quantiles'],method='linear').tolist()
        save('train_state.json',{'selection':'TrainMI3','selected':selected,'candidate_MI':dict(zip(ALL,map(float,mi))),'order':order,'thresholds':thresholds,'candidate_count':16,'local_logical_reads':{'M0':0,'M1':3,'M2':3,'M3':16,'M4':16},'selection_train_reads':16,'common_cache_io_contains_all_fields':True})
        trmsg={'M0':[emit([],tok) for r in tr],'M1':[emit(raw_pairs(r,selected),tok,64) for r in tr],'M2':[emit(summary_pairs(r,selected,thresholds),tok,64) for r in tr],'M4':[emit(raw_pairs(r,ALL),tok) for r in tr]}
        trviews={m:[z['parsed'] for z in v] for m,v in trmsg.items()}
        oof=np.full(len(tr),np.nan);groups=np.array([r['student'] for r in tr]);fold_log=[]
        for j,(fit,ev) in enumerate(GroupKFold(n_splits=3,shuffle=True,random_state=cfg['seed']).split(np.arange(len(tr)),groups=groups)):
            assert set(groups[fit]).isdisjoint(set(groups[ev]));bundle=fit_bundle('M3_crossfit'+str(j),[trviews['M4'][i] for i in fit],y[fit],'Ridge',cfg,ledger)
            oof[ev]=np.clip(predict(bundle,[trviews['M4'][i] for i in ev]),0,100)
            fold_log.append({'fold':j,'fit_students':len(set(groups[fit])),'prediction_students':len(set(groups[ev])),'fit_snapshots':len(fit),'prediction_snapshots':len(ev),'prediction_group_hashes':[pseudo(x) for x in sorted(set(groups[ev]))],'overlap':0})
        assert np.isfinite(oof).all();save('crossfit_groups_LOCAL.json',fold_log)
        trmsg['M3']=[emit([('predicted_score',f'{v:.1f}')],tok) for v in oof];trviews['M3']=[z['parsed'] for z in trmsg['M3']]
        local=fit_bundle('M3_local_full',trviews['M4'],y,'Ridge',cfg,ledger)
        receivers={m:fit_bundle('receiver_'+m,trviews[m],y,'Ridge',cfg,ledger) for m in ['M0','M1','M2','M4']}
        assert np.allclose(local['pipeline'][-1].coef_,receivers['M4']['pipeline'][-1].coef_,atol=1e-12)
        attacks={};attack_status=[]
        for scope in ['public_plus_message','authorized_result_plus_message']:
            for m in METHODS:
                if scope=='authorized_result_plus_message' and m=='M3':
                    assert union(trviews['M3'],trviews['M3'])==union(trviews['M3'],trviews['M0'])
                    for attr in ATTRS:
                        for kind in KINDS:attacks[(scope,m,attr,kind)]=attacks[(scope,'M0',attr,kind)]
                    continue
                views=trviews[m] if scope=='public_plus_message' else union(trviews['M3'],trviews[m])
                for attr in ATTRS:
                    for kind in KINDS:
                        if len(np.unique(labels[attr]))<2:
                            attacks[(scope,m,attr,kind)]=None;attack_status.append({'scope':scope,'method':m,'attribute':attr,'attacker':kind,'status':'BLOCKED_ONE_TRAIN_CLASS'});continue
                        attacks[(scope,m,attr,kind)]=fit_bundle('attack_'+scope+'_'+m+'_'+attr+'_'+kind,views,labels[attr],kind,cfg,ledger)
        assert ledger.count<=50
        save('TRAIN_COMPLETE.json',{'utc':now().isoformat(),'fits':ledger.count,'dev_predictions_or_metrics_computed':False,'model_sha256':{p.name:sha(p) for p in (P/'models_LOCAL').glob('*.joblib')},'threadpools':threadpool_info(),'OOF_is_student_disjoint':True})
        # One final dev pass. No model or threshold fitting is allowed below.
        if (P/'DEV_EVAL_LOCK.json').exists():raise RuntimeError('Dev already evaluated')
        save('DEV_EVAL_LOCK.json',{'utc':now().isoformat(),'final_evaluation_number':1,'fit_count':ledger.count,'all_models_frozen':True})
        ledger.log('FINAL_DEV_EVALUATION_START',fits=ledger.count)
        dvmsg={};timings={}
        for m in ['M0','M1','M2','M4']:
            before=time.perf_counter()
            dvmsg[m]=[emit([] if m=='M0' else (summary_pairs(r,selected,thresholds) if m=='M2' else raw_pairs(r,selected if m=='M1' else ALL)),tok,64 if m in ['M1','M2'] else None) for r in dv]
            timings[m]={'message_generation_seconds':time.perf_counter()-before}
        dvviews={m:[v['parsed'] for v in messages] for m,messages in dvmsg.items()}
        before=time.perf_counter();local_pred=np.clip(predict(local,dvviews['M4']),0,100)
        local_predict_seconds=time.perf_counter()-before;before=time.perf_counter()
        dvmsg['M3']=[emit([('predicted_score',f'{v:.1f}')],tok) for v in local_pred];dvviews['M3']=[z['parsed'] for z in dvmsg['M3']]
        timings['M3']={'message_generation_seconds':time.perf_counter()-before,'local_prediction_seconds':local_predict_seconds,'local_full_encoding_seconds_shared_with_M4':timings['M4']['message_generation_seconds']}
        forecast={}
        for m,b in receivers.items():
            before=time.perf_counter();forecast[m]=np.clip(predict(b,dvviews[m]),0,100);timings[m]['receiver_prediction_seconds']=time.perf_counter()-before
        forecast['M3']=np.array([v['predicted_score'] for v in dvviews['M3']]);save('timings.json',timings)
        assert np.max(abs(forecast['M4']-local_pred))<1e-8
        assert np.max(abs(forecast['M3']-forecast['M4']))<=.05000001
        actual=np.array([r['target_score'] for r in dv]);observed=np.array([r['target_observed'] for r in dv],bool)
        attributes={attr:np.array([r[attr] for r in dv]) for attr in ATTRS}
        sid,sidx=np.unique([r['student'] for r in dv],return_inverse=True);rng=np.random.default_rng(cfg['seed']);draw=rng.integers(0,len(sid),(200,len(sid)));counts=np.zeros((200,len(sid)))
        np.add.at(counts,(np.repeat(np.arange(200),len(sid)),draw.ravel()),1);weights=counts[:,sidx];den=weights.sum(1)
        errors={m:abs(forecast[m]-actual) for m in METHODS};boot={m:weights@errors[m]/den for m in METHODS}
        summary=[]
        for m in METHODS:
            msg=dvmsg[m];nt=np.array([v['tokens'] for v in msg]);items=np.array([v['items'] for v in msg]);nmiss=sum(v['NA'] for v in msg);nitems=int(items.sum());delta=float(np.mean(errors[m]-errors['M4']));dci=interval(boot[m]-boot['M4'])
            row={'method':m,'status':'COMPLETED','n_students':len(sid),'n_snapshots':len(dv),'MAE':float(errors[m].mean()),'MAE95_low':interval(boot[m])[0],'MAE95_high':interval(boot[m])[1],'observed_MAE':float(errors[m][observed].mean()),'observed_n':int(observed.sum()),'delta_MAE_vs_M4':delta,'delta95_low':dci[0],'delta95_high':dci[1],'point_within_M4_plus1':delta<=1.,'upper_CI_within_M4_plus1':dci[1]<=1.,'local_logical_fields_read':0 if m=='M0' else (3 if m in ['M1','M2'] else 16),'uploaded_items_mean':float(items.mean()),'tokens_mean':float(nt.mean()),'tokens_max':int(nt.max()),'bytes_mean':float(np.mean([v['bytes'] for v in msg])),'message_NA_fraction':nmiss/nitems if nitems else None,'dropped_items_total':sum(v['absent_items'] for v in msg),'over_64_count':int(np.sum(nt>64)),'budget_role':'unbudgeted_local_shadow' if m=='M4' else 'actual_message','decoder_dimensions':len(receivers[m]['pipeline'][0].feature_names_) if m in receivers else 1,'message_generation_ms_per_row':1000*timings[m]['message_generation_seconds']/len(dv)}
            summary.append(row)
        contrasts=[]
        for left,right in [('M4','M0'),('M1','M4'),('M2','M4'),('M3','M4'),('M2','M1'),('M3','M0')]:
            b=boot[left]-boot[right];contrasts.append({'left':left,'right':right,'delta_MAE':float(np.mean(errors[left]-errors[right])),'student95':interval(b),'meaning':'negative favors left'})
        attack_rows=[];allprob={};allpred={};aucboots={}
        for scope in ['public_plus_message','authorized_result_plus_message']:
            for m in METHODS:
                views=dvviews[m] if scope=='public_plus_message' else union(dvviews['M3'],dvviews[m])
                if scope=='authorized_result_plus_message' and m=='M3':assert views==union(dvviews['M3'],dvviews['M0'])
                for attr in ATTRS:
                    yy=attributes[attr]
                    for kind in KINDS:
                        key=(scope,m,attr,kind);bundle=attacks[key]
                        if bundle is None or len(np.unique(yy))<2:
                            attack_rows.append({'scope':scope,'method':m,'attribute':attr,'attacker':kind,'status':'BLOCKED_ONE_CLASS','AUC':None,'BA':None});continue
                        if scope=='authorized_result_plus_message' and m=='M3':
                            old=(scope,'M0',attr,kind);prob=allprob[old];pred=allpred[old];ab=aucboots[old]
                        else:
                            prob=predict(bundle,views,True);pred=predict(bundle,views);ab=aucboot(yy,prob,weights)
                        allprob[key]=prob;allpred[key]=pred;aucboots[key]=ab
                        base=(scope,'M0',attr,kind);baseline=allprob[base];b=ab-aucboots[base]
                        attack_rows.append({'scope':scope,'method':m,'attribute':attr,'attacker':kind,'status':'COMPLETED','AUC':float(roc_auc_score(yy,prob)),'AUC95_low':interval(ab)[0],'AUC95_high':interval(ab)[1],'BA':float(balanced_accuracy_score(yy,pred)),'delta_AUC_vs_scope_baseline':float(roc_auc_score(yy,prob)-roc_auc_score(yy,baseline)),'delta95_low':interval(b)[0],'delta95_high':interval(b)[1],'reuse_exact_same_view':scope=='authorized_result_plus_message' and m=='M3','baseline':'Public-only' if scope=='public_plus_message' else 'Public+Y_auth'})
        save('method_summary.json',summary);csvout('method_summary.csv',summary);save('utility_contrasts.json',contrasts);save('attribute_inference.json',attack_rows);csvout('attribute_inference.csv',attack_rows)
        individual=[];wire_rows=[]
        for i,r in enumerate(dv):
            case=f'D{i:04d}';anon=pseudo(r['student'])
            for m in METHODS:
                v=dvmsg[m][i];individual.append({'case':case,'student_pseudonym':anon,'method':m,'true_score_LOCAL':float(actual[i]),'prediction':float(forecast[m][i]),'absolute_error':float(errors[m][i]),'observed_score':bool(observed[i]),'uploaded_items':v['items'],'tokens':v['tokens'],'message_NA':v['NA'],'dropped_items':v['absent_items']})
                wire_rows.append({'case':case,'student_pseudonym':anon,'method':m,'wire':v['wire'],'tokens':v['tokens'],'parsed':v['parsed']})
        csvout('per_sample_LOCAL.csv',individual)
        with (P/'actual_messages_LOCAL.jsonl').open('w',encoding='utf8') as f:
            for r in wire_rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
        np.savez_compressed(P/'predictions_LOCAL.npz',target=actual,**{'forecast_'+m:forecast[m] for m in METHODS},**{'prob|'+'|'.join(k):v for k,v in allprob.items()},**attributes,student_cluster=sidx)
        # Predeclared example selection only illustrates the already fixed evaluation.
        selected_cases=[]
        missing=next((i for i,r in enumerate(dv) if any(field_value(r,k) is None for k in selected)),None)
        candidates=[0,int(np.argmax(errors['M2']-errors['M1'])),int(np.argmax(errors['M1']-errors['M4'])),int(np.argmax(errors['M4']))]
        if missing is not None:candidates.append(missing)
        for i in candidates+list(range(len(dv))):
            if i not in selected_cases:selected_cases.append(i)
            if len(selected_cases)==5:break
        cases=[]
        for i in selected_cases:
            r=dv[i];cases.append({'case':f'D{i:04d}','student_pseudonym':pseudo(r['student']),'task':'Predict next scheduled TMA score; raw score/submission composite truth','target_score_LOCAL':float(actual[i]),'target_observed':bool(observed[i]),'methods':{m:{'local_read_fields':[] if m=='M0' else (selected if m in ['M1','M2'] else ALL),'uploaded':dvmsg[m][i]['wire'],'tokens':dvmsg[m][i]['tokens'],'prediction':float(forecast[m][i]),'absolute_error':float(errors[m][i]),'omitted_source_fields':[k for k in ALL if k not in dvviews[m][i]] if m in ['M0','M1','M4'] else (ALL if m=='M3' else [k for k in ALL if k not in selected]),'transformation':'none' if m in ['M0','M1','M4'] else ('tercile categories, no source values' if m=='M2' else 'only forecast, no source facts')} for m in METHODS}})
        save('five_cases_LOCAL.json',cases)
        fit_end=ledger.count
        integrity={n:sha(ROOT/n)==h for n,h in audit['sources_sha256'].items()};assert all(integrity.values())
        save('completion.json',{'status':'COMPLETED','utc':now().isoformat(),'runtime_seconds':time.perf_counter()-start,'fits_started':fit_end,'fit_limit':50,'expected_fits':45,'dev_evaluations':1,'no_fits_after_dev_evaluation_start':True,'train_students':484,'dev_students':166,'train_snapshots':1337,'dev_snapshots':473,'input_sources_unchanged':integrity,'no2014J_reads':True,'GPU_used':False,'downloads':0,'paid_calls':0,'external_data_uploads':0,'M3_vs_M4_max_score_difference':float(np.max(abs(forecast['M3']-forecast['M4']))),'auth_M3_exactly_equals_baseline':True,'deadline_respected':now()<datetime.datetime.fromisoformat(cfg['hard_stop_utc']),'cpu_worker_threads_max':2,'no_followup_queue':True})
        ledger.log('COMPLETED',fits=ledger.count,seconds=time.perf_counter()-start)
        print('FINAL_DEV_COMPLETE',json.dumps({'fits':ledger.count,'method_MAE':{r['method']:r['MAE'] for r in summary}}),flush=True)
    except Exception as ex:
        save('INCOMPLETE.json',{'status':'INCOMPLETE','utc':now().isoformat(),'fits_started':ledger.count,'error':repr(ex),'traceback':traceback.format_exc(),'no_failure_metric_replaced_by_zero':True})
        ledger.log('INCOMPLETE',error=repr(ex),fits=ledger.count);raise
if __name__=='__main__':main()
