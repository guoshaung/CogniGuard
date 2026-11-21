"""Frozen-model real-record paired development/forward holdout experiment."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
assert os.environ.get('PYTHONHASHSEED')=='20261013'
from pathlib import Path
import json,sys,hashlib,time,collections
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import mutual_info_regression
from sklearn.metrics import mean_absolute_error,balanced_accuracy_score,roc_auc_score
P=Path(__file__).parent;sys.path.insert(0,str(P));import design as d;import selection_engine as e
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(folder,n,z):(folder/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sources():return {n:sha(P/n) for n in ['design.py','build_data.py','selection_engine.py','run_experiment.py','protocol.json','frozen/aligned_selector.py','frozen/strict_select_enhanced.py.txt']}
def run(phase):
 assert phase in ['dev','test'];O=P/(phase+'_results');O.mkdir(exist_ok=True)
 if (O/'execution_lock.json').exists():raise RuntimeError('no overwrite')
 if phase=='test':
  lock=load(P/'independent_protocol.json');assert lock['authorized_by_frozen_dev_gate'];assert lock['source_sha256']==sources()
 save(O,'execution_lock.json',{'status':'FROZEN_BEFORE_MODEL_FIT','phase':phase,'sources_sha256':sources(),'hash_seed':os.environ['PYTHONHASHSEED'],'no_hyperparameter_search':True})
 devdata=load(P/'dev_data/snapshots_LOCAL.json');train=[x for x in devdata if x['split']=='train'];evalrows=[x for x in devdata if x['split']=='dev'] if phase=='dev' else load(P/'test_data/snapshots_LOCAL.json');rows=train+evalrows;tr=np.arange(len(train));ev=np.arange(len(train),len(rows));y=np.array([x['target_score'] for x in rows]);assert set(x['student'] for x in train).isdisjoint({x['student'] for x in evalrows})
 matrix=np.array([[x['values'][k] if x['values'][k] is not None else np.nan for k in d.FIELDS] for x in train]);med=np.nanmedian(matrix,axis=0);matrix=np.where(np.isnan(matrix),med,matrix);mi_values=mutual_info_regression(matrix,y[tr],random_state=20261020);mi_order=[k for _,k in sorted(zip(mi_values,d.FIELDS),key=lambda z:(-z[0],z[1]))];save(O,'TrainMI_train_only.json',{'n_train_snapshots':len(train),'order':mi_order,'MI':{k:float(v) for k,v in zip(d.FIELDS,mi_values)},'target':'next deadline score, same label for all intents; public side context common'})
 counters=[]
 for i,row in enumerate(rows):
  counters.append(e.Counter(row))
  if i%400==0:print('token_tables',phase,i,'/',len(rows),flush=True)
 summary=[];attackresults=[];paired=[];subgroups=[];details=[];templates={};casecounts=[];intervals=[]
 for intent in d.INTENTS:
  for wording in ['explicit','ambiguous']:
   collected={};predictions={}
   for method in d.METHODS:
    selected=[];tokens=[];timings=[];views=[];traces=[];wires=[]
    for row,tc in zip(rows,counters):
     fields,trace,nt,ms,wire=e.select(method,row,intent,wording,tc,mi_order);selected.append(fields);tokens.append(nt);timings.append(ms);views.append(e.view(row,fields));traces.append(trace);wires.append(wire)
     if trace:templates[f'{method}|{intent}|{wording}|{row["cutoff"]}']=trace
    model=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),Ridge(alpha=10.,solver='lsqr')).fit(views[:len(train)],y[tr]);pred=np.clip(model.predict(views[len(train):]),0,100);predictions[method]=pred
    for attr in ['gender_F','disability_Y']:
     labels=np.array([x[attr] for x in rows])
     for attacker,est in [('LR',LogisticRegression(C=1,class_weight='balanced',solver='liblinear',max_iter=2000,random_state=20261020)),('RF',RandomForestClassifier(n_estimators=64,max_depth=6,min_samples_leaf=5,class_weight='balanced_subsample',random_state=20261020,n_jobs=1))]:
      if len(np.unique(labels[ev]))<2 or len(np.unique(labels[tr]))<2:
       attackresults.append({'intent':intent,'wording':wording,'method':method,'attribute':attr,'attacker':attacker,'status':'BLOCKED_ONE_CLASS','n':len(ev),'BA':None,'AUC':None});continue
      am=make_pipeline(DictVectorizer(),StandardScaler(with_mean=False),est).fit(views[:len(train)],labels[tr]);ap=am.predict(views[len(train):]);prob=am.predict_proba(views[len(train):])[:,1];attackresults.append({'intent':intent,'wording':wording,'method':method,'attribute':attr,'attacker':attacker,'status':'COMPLETED','n':len(ev),'positive_snapshots':int(labels[ev].sum()),'negative_snapshots':int(len(ev)-labels[ev].sum()),'BA':float(balanced_accuracy_score(labels[ev],ap)),'AUC':float(roc_auc_score(labels[ev],prob))})
    necessary=set(d.INTENTS[intent]['required']);recall=[];avail_recall=[];avail_num=0;avail_den=0
    for j,i in enumerate(ev):
     present=set(selected[i]);available={k for k in necessary if rows[i]['values'][k] is not None};num=len(present&available);den=len(available);recall.append(len(present&necessary)/3);avail_num+=num;avail_den+=den
     if den:avail_recall.append(num/den)
     details.append({'student':rows[i]['student'],'module':rows[i]['module'],'cutoff':rows[i]['cutoff'],'intent':intent,'wording':wording,'method':method,'selected_fields':selected[i],'payload':wires[i],'actual_tokens':tokens[i],'prediction':float(pred[j]),'target':float(y[i]),'target_observed':rows[i]['target_observed'],'schema_contract_recall':recall[-1],'available_contract_num':num,'available_contract_den':den,'trace_key':f'{method}|{intent}|{wording}|{rows[i]["cutoff"]}' if traces[i] else None})
    aa=[x for x in attackresults if x['intent']==intent and x['wording']==wording and x['method']==method and x['status']=='COMPLETED'];observed=np.array([rows[i]['target_observed'] for i in ev]);result={'phase':phase,'intent':intent,'wording':wording,'method':method,'n_snapshots':len(ev),'n_students':len({rows[i]['student'] for i in ev}),'MAE':float(mean_absolute_error(y[ev],pred)),'observed_score_MAE':float(mean_absolute_error(y[ev][observed],pred[observed])) if observed.any() else None,'observed_score_n':int(observed.sum()),'contract_schema_recall':float(np.mean(recall)),'available_contract_recall_macro':float(np.mean(avail_recall)) if avail_recall else None,'available_contract_recall_micro':avail_num/avail_den if avail_den else None,'available_contract_den':avail_den,'BA_macro':float(np.mean([x['BA'] for x in aa])) if aa else None,'AUC_macro':float(np.mean([x['AUC'] for x in aa])) if aa else None,'fields_mean':float(np.mean([len(selected[i]) for i in ev])),'actual_tokens_mean':float(np.mean([tokens[i] for i in ev])),'actual_tokens_max':int(max(tokens[i] for i in ev)),'direct_sensitive_release_rate':0.,'mixed_cache_selector_ms':float(np.mean([timings[i] for i in ev])),'failures':0};summary.append(result);collected[method]={'fields':selected,'traces':traces,'wires':wires}
    # Per-stage and per-module utilities share fits and exact paired sample sets.
    for name,values in [('cutoff',d.CUTOFFS),('module',d.MODULES)]:
     for value in values:
      pos=[j for j,i in enumerate(ev) if rows[i][name]==value]
      if pos:subgroups.append({'intent':intent,'wording':wording,'method':method,'subgroup':name,'value':value,'n_snapshots':len(pos),'MAE':float(np.mean(abs(pred[pos]-y[ev][pos]))),'contract_schema_recall':float(np.mean(np.array(recall)[pos])),'actual_tokens_mean':float(np.mean([tokens[ev[j]] for j in pos]))})
    freq=collections.Counter(tuple(selected[i]) for i in ev)
    for fields,count in freq.items():casecounts.append({'intent':intent,'wording':wording,'method':method,'fields':list(fields),'count_snapshots':count})
    print('fit',phase,intent,wording,method,round(result['MAE'],4),flush=True)
   full=collected['Repaired-Full'];fullerr=abs(predictions['Repaired-Full']-y[ev]);students=np.array([rows[i]['student'] for i in ev]);unique=np.unique(students)
   for method in d.METHODS:
    part=collected[method];tc=[part['traces'][i] for i in ev];fc=[full['traces'][i] for i in ev];paired.append({'intent':intent,'wording':wording,'method':method,'n_snapshots':len(ev),'projection_nonzero_rate':float(np.mean([x.get('projection_nonzero',False) for x in tc])) if method.startswith('Repaired') else None,'projection_internal_changed_rate':float(np.mean([x.get('projection_values')!=z.get('projection_values') for x,z in zip(tc,fc)])) if method.startswith('Repaired') else None,'attention_internal_changed_rate':float(np.mean([x.get('attention_unit_scale')!=z.get('attention_unit_scale') for x,z in zip(tc,fc)])) if method.startswith('Repaired') else None,'top3_rank_changed_rate':float(np.mean([x.get('rank',[])[:3]!=z.get('rank',[])[:3] for x,z in zip(tc,fc)])) if method.startswith('Repaired') else None,'slot_changes_rank_rate':float(np.mean([x.get('rank')!=x.get('pre_slot_rank') for x in tc])) if method.startswith('Repaired') else None,'final_fields_changed_rate':float(np.mean([part['fields'][i]!=full['fields'][i] for i in ev])),'actual_payload_changed_rate':float(np.mean([part['wires'][i]!=full['wires'][i] for i in ev])),'prediction_changed_rate':float(np.mean(abs(predictions[method]-predictions['Repaired-Full'])>1e-10)),'net_positive_candidates_mean':float(np.mean([x.get('net_positive_count',0) for x in tc])) if method.startswith('Repaired') else None})
    difference=fullerr-abs(predictions[method]-y[ev]);sums=np.array([difference[students==sid].sum() for sid in unique]);counts=np.array([(students==sid).sum() for sid in unique]);rng=np.random.default_rng(20261020);draw=rng.integers(0,len(unique),(1000,len(unique)));boot=sums[draw].sum(axis=1)/counts[draw].sum(axis=1);intervals.append({'intent':intent,'wording':wording,'reference':method,'n_students':len(unique),'delta_MAE_Full_minus_reference':float(difference.mean()),'student_group_bootstrap95':np.quantile(boot,[.025,.975]).tolist(),'scope':'fixed fitted models; sampled cohort conditional interval, not complete population uncertainty'})
   save(O,'summary.json',summary);save(O,'attacks.json',attackresults);save(O,'paired_mechanisms.json',paired);save(O,'subgroups.json',subgroups);save(O,'cases_LOCAL.json',details);save(O,'trace_templates.json',templates);save(O,'fieldsets.json',casecounts);save(O,'paired_intervals.json',intervals)
 save(O,'completion.json',{'status':'COMPLETED','phase':phase,'method_context_cells':len(summary),'attribute_attack_cells':len(attackresults),'train_students':len({x['student'] for x in train}),'eval_students':len({x['student'] for x in evalrows}),'train_snapshots':len(train),'eval_snapshots':len(evalrows),'same_eval_set_all_methods':True,'source_sha256':sources(),'LLM_calls':0,'paid_API_calls':0,'failures':0,'all_three_fields':all(x['fields_mean']==3 for x in summary),'all_tokens_within64':all(x['actual_tokens_max']<=64 for x in summary),'tuning_after_eval':False})
 print('COMPLETED',phase,flush=True)
if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'dev')
