"""Frozen-metric aggregation, grouped uncertainty and paired component audit.

No parameter learning or data rejection. Structural tasks share32 rule families.
"""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from pathlib import Path
import json,gzip,csv,hashlib,collections,copy
import numpy as np
from sklearn.metrics import roc_auc_score
from generator import FIELDS
P=Path(__file__).parent;ROOT=P.parents[1]
METRICS=['Recall','Precision','F1','completion','answered_success','reference_answerable','correct_clarification','fields','tokens','high_sensitive_selection_ratio','direct_sensitive_field_count','weighted_privacy_exposure','released_sensitivity_mass','budget_feasible_oracle','legacy_three_unit_recall','any_direct_release']
def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def csvout(name,rows):
    cols=list(dict.fromkeys(k for row in rows for k in row))
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
def interval(x):return np.nanquantile(x,[.025,.975]).tolist()
def weights(labels,rng):
    names,idx=np.unique(labels,return_inverse=True);n=len(names);draws=rng.integers(0,n,(500,n));cnt=np.zeros((500,n),dtype=np.float32)
    np.add.at(cnt,(np.repeat(np.arange(500),n),draws.ravel()),1.)
    return cnt[:,idx],n
def aucbootstrap(y,prob,w):
    order=np.argsort(prob,kind='stable');pr=np.asarray(prob)[order];starts=np.r_[0,np.flatnonzero(pr[1:]!=pr[:-1])+1]
    pp=np.add.reduceat(w[:,order]*y[order],starts,axis=1);nn=np.add.reduceat(w[:,order]*(1-y[order]),starts,axis=1);den=pp.sum(1)*nn.sum(1)
    return np.divide(np.sum(pp*(np.cumsum(nn,axis=1,dtype=np.float64)-.5*nn),axis=1),den,out=np.full(len(w),np.nan),where=den>0)
def main():
    lock=load(P/'final_freeze.json');assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in lock['sources'].items())
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in load(P/'preservation.json').items())
    assert load(P/'var/results/train/strict_attention_equivalence.json')['all_equal'] and load(P/'var/results/test/strict_attention_equivalence.json')['all_equal']
    execution=load(P/'var/results/test/execution.json');assert execution['tasks']==10000
    arms=[tuple(x) for x in execution['arms']];index={x:i for i,x in enumerate(arms)};n=10000
    meta=[]
    with (P/'data/test/tasks.jsonl').open(encoding='utf8') as f:
        for line in f:
            t=json.loads(line);meta.append({k:t[k] for k in ['request_id','student_id','family','task_type','difficulty']})
    ids={t['request_id']:i for i,t in enumerate(meta)};values=np.zeros((len(arms),n,len(METRICS)),float);selection=np.zeros((len(arms),n),np.uint64);wires=np.zeros_like(selection);examples=[]
    seen=np.zeros((len(arms),n),dtype=bool);firstcase={}
    with gzip.open(P/'var/results/test/raw_rows.jsonl.gz','rt',encoding='utf8') as f:
        for line in f:
            r=json.loads(line);j=index[(r['method'],r['K'])];i=ids[r['case']];assert not seen[j,i];seen[j,i]=True
            units={FIELDS[k][0] for k in r['selected'] if k in FIELDS};r['legacy_three_unit_recall']=len(units&{'mastery','error_pattern','preference'})/3;r['any_direct_release']=int(r['direct_sensitive_field_count']>0)
            values[j,i]=[r[k] for k in METRICS]
            selection[j,i]=int(hashlib.sha256('|'.join(sorted(r['selected'])).encode()).hexdigest()[:16],16);wires[j,i]=int(hashlib.sha256(r['wire'].encode()).hexdigest()[:16],16)
            if r['K']==3 and r['method'] in ['MM-FOPD','SafeTaskTopK','MM-no-attention','MM-no-taskslot']:
                firstcase.setdefault(r['case'],{})[r['method']]=r
    assert seen.all()
    rng=np.random.default_rng(20261020);ws,ns=weights(np.array([t['student_id'] for t in meta]),rng);wf,nf=weights(np.array([t['family'] for t in meta]),rng);ww=ws*wf
    groups={'student':ws,'family':wf,'two_way':ww};summaries=[];paired=[];bootcache={}
    for j,(method,k) in enumerate(arms):
        z=values[j];row={'method':method,'K':k,'n_tasks':n,'n_students':ns,'n_families':nf,**{name:float(z[:,m].mean()) for m,name in enumerate(METRICS)}}
        row['answer_completion_rate']=float(z[:,4].sum()/z[:,5].sum());row['clarification_success_rate']=float(z[:,6].sum()/max(1,n-z[:,5].sum()))
        for name,w in groups.items():
            boot=w@z/w.sum(1)[:,None];bootcache[(j,name)]=boot
            for m,metric in enumerate(METRICS):row[f'{metric}_{name}95_low'],row[f'{metric}_{name}95_high']=interval(boot[:,m])
        summaries.append(row)
    for k in [2,3,5]:
        full=index[('MM-FOPD',k)]
        for method in ['MM-no-projection','MM-no-attention','MM-no-bottleneck','MM-no-taskslot','SafeTaskTopK','RelevanceCostRule']:
            j=index[(method,k)];row={'method':method,'K':k,'field_set_change_rate':float(np.mean(selection[j]!=selection[full])),'wire_change_rate':float(np.mean(wires[j]!=wires[full])),
                'interpretation':'COMPOUND_LEGACY_SCORE_SCALE_AND_SHORTLIST' if method=='MM-no-attention' else 'same caps; single mechanism or explicit simple selector comparison'}
            for metric in ['F1','completion','fields','tokens','weighted_privacy_exposure']:
                m=METRICS.index(metric);row['delta_'+metric]=float((values[j,:,m]-values[full,:,m]).mean())
                row['delta_'+metric+'_two_way95_low'],row['delta_'+metric+'_two_way95_high']=interval(bootcache[(j,'two_way')][:,m]-bootcache[(full,'two_way')][:,m])
            paired.append(row)
        alias=copy.deepcopy(next(x for x in summaries if x['method']=='MM-FOPD' and x['K']==k));alias.update(method='MM-no-attention-strict-uniform',provenance='supplementary actual wire equivalence, not initial preregistered row');summaries.append(alias)
        paired.append({'method':'MM-no-attention-strict-uniform','K':k,'field_set_change_rate':0.,'wire_change_rate':0.,'delta_F1':0.,'delta_F1_two_way95_low':0.,'delta_F1_two_way95_high':0.,'delta_completion':0.,'delta_completion_two_way95_low':0.,'delta_completion_two_way95_high':0.,'interpretation':'supplementary normalized uniform weights, sameTop8, all other flags/caps unchanged; actual equivalence over all train/test cases'})
    group_rows=[]
    for category,key in [('type','task_type'),('difficulty','difficulty'),('family','family')]:
        for label in sorted({t[key] for t in meta}):
            mask=np.array([t[key]==label for t in meta]);count=int(mask.sum());wg=ws[:,mask];den=wg.sum(1)
            for j,(method,k) in enumerate(arms):
                z=values[j,mask];gr={'category':category,'group':label,'method':method,'K':k,'n_tasks':count,'n_students':len({meta[i]['student_id'] for i in np.flatnonzero(mask)}),'n_families':len({meta[i]['family'] for i in np.flatnonzero(mask)}),**{name:float(z[:,m].mean()) for m,name in enumerate(METRICS)}}
                for metric in ['completion','F1']:
                    m=METRICS.index(metric);b=wg@z[:,m]/den;gr[metric+'_student95_low'],gr[metric+'_student95_high']=interval(b)
                group_rows.append(gr)
    save('summary.json',summaries);csvout('ten_method_comparison.csv',[x for x in summaries if x['method'] in [z[0] for z in arms[:10]]]);csvout('all_budget_results.csv',summaries);csvout('strict_ablation.csv',paired);csvout('group_results.csv',group_rows)
    # Fixed first examples, retained successes as well as failures; no dataset changes.
    buckets={'MM_fail_Safe_success':[],'MM_success_Safe_fail':[],'both_fail':[]}
    for case in sorted(firstcase):
        rr=firstcase[case];full=rr['MM-FOPD']['completion'];safe=rr['SafeTaskTopK']['completion'];bucket='MM_fail_Safe_success' if safe and not full else ('MM_success_Safe_fail' if full and not safe else ('both_fail' if not full and not safe else None))
        if bucket and len(buckets[bucket])<5:buckets[bucket].append(rr)
    save('failure_success_examples.json',buckets)
    # Old saved results verified numerically, no reuse as an independent holdout.
    oldbase=ROOT/'experiments/results/mmfopd_v3_test_supplement_v2'
    with (oldbase/'rows.csv').open(encoding='utf-8-sig',newline='') as f:oldrows=list(csv.DictReader(f))
    oldsum=[]
    for method in dict.fromkeys(r['method'] for r in oldrows):
        rr=[x for x in oldrows if x['method']==method];oldsum.append({'method':method,'n':len(rr),'students':len({x['student_id'] for x in rr}),'required_unit_recall':float(np.mean([float(x['required_unit_recall']) for x in rr])),'unit_reconstruction_f1':float(np.mean([float(x['unit_reconstruction_f1']) for x in rr])),'selected_count':float(np.mean([float(x['selected_count']) for x in rr]))})
    save('historical_144_reaggregation.json',oldsum)
    # All raw attributes are artificial; bootstrap actual released representations only.
    attacks=load(P/'attacks_test/metrics.json');probs=np.load(P/'attacks_test/predictions.npz');max_rounding=0.
    for number,row in enumerate(attacks):
        ai=0 if row['attribute']=='gender_F' else 1;y=probs['labels'][:,ai].astype(float);prob=probs[row['prediction_key']+'|prob'];pred=probs[row['prediction_key']+'|pred'];max_rounding=max(max_rounding,abs(roc_auc_score(y,prob)-row['AUC']))
        for name,w in groups.items():
            ab=aucbootstrap(y,prob,w);pos=w@y;neg=w@(1-y);ba=.5*((w@(y*(pred==1)))/pos+(w@((1-y)*(pred==0)))/neg)
            row[f'AUC_{name}95_low'],row[f'AUC_{name}95_high']=interval(ab);row[f'BA_{name}95_low'],row[f'BA_{name}95_high']=interval(ba)
        public=next(x for x in attacks if x['method']=='Public-only' and x['attribute']==row['attribute'] and x['attacker']==row['attacker'])
        row['delta_AUC_vs_public']=row['AUC']-public['AUC'];row['nonnegative_observed_AUC_excess']=max(0.,row['delta_AUC_vs_public'])
        if number%20==0:print('bootstrap attacks',number,'/',len(attacks),flush=True)
    for k in [2,3,5]:
        aliases=[copy.deepcopy(x) for x in attacks if x['method']=='MM-FOPD' and x['K']==k]
        for r in aliases:r.update(method='MM-no-attention-strict-uniform',provenance='actual train/test wire equality; identical attacks reused')
        attacks.extend(aliases)
    csvout('attribute_inference.csv',attacks);save('attribute_inference.json',attacks)
    save('analysis_validation.json',{'status':'COMPLETED','primary_rows':n*len(arms),'unique_students_test':ns,'structural_families':nf,'bootstrap_draws':500,'cluster_modes':list(groups),'test_rows_preserved':True,'all_candidate_programs_execute_correctly':execution['all_candidate_program_correct']==10000,'max_AUC_drift_from_float32_prediction_cache':max_rounding,'formal_sources_unchanged':all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in lock['sources'].items()),'historical_files_unchanged':True,'dataset_resampling':False})
    print('ANALYSIS_COMPLETED',flush=True)
if __name__=='__main__':main()
