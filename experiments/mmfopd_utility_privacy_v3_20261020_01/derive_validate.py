"""No fitting: student bootstrap, wire/constraint audit, CSVs and honest gate."""
import core as c
import numpy as np
import json,csv,copy
from sklearn.metrics import roc_auc_score,balanced_accuracy_score
P=c.P
def csvout(name,rows):
    columns=list(dict.fromkeys(k for row in rows for k in row))
    with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
def interval(v):return np.nanquantile(v,[.025,.975]).tolist()

def main():
    for lock in ['phaseB_lock.json','phaseC_lock.json']:
        assert all(c.sha(P/n)==h for n,h in c.load(P/lock)['sources'].items())
    preserved=c.load(P/'preservation.json');assert all(c.sha(c.ROOT/n)==h for n,h in preserved.items())
    assert all(c.sha(P/n)==h for n,h in c.load(P/'reference_sources.json')['files'].items())
    tr,dv=c.dataset();summaries=c.load(P/'all_summary.json');attacks=c.load(P/'all_attacks.json');local=c.load(P/'all_predictions_LOCAL.json');transforms=c.load(P/'transforms.json');background=c.load(P/'background_attacks.json')
    students=np.array([r['student'] for r in dv]);unique,inverse=np.unique(students,return_inverse=True);rng=np.random.default_rng(20261020)
    draws=rng.integers(0,len(unique),(500,len(unique)));counts=np.zeros((500,len(unique)),float)
    np.add.at(counts,(np.repeat(np.arange(500),len(unique)),draws.ravel()),1.)
    weights=counts[:,inverse];den=weights.sum(1)
    labels={a:np.array([r[a] for r in dv]) for a in c.ATTRS}
    def aucboots(y,prob):
        order=np.argsort(prob,kind='stable');ps=np.asarray(prob)[order];starts=np.r_[0,np.flatnonzero(ps[1:]!=ps[:-1])+1]
        pos=weights[:,order]*y[order];neg=weights[:,order]*(1-y[order]);pg=np.add.reduceat(pos,starts,axis=1);ng=np.add.reduceat(neg,starts,axis=1)
        denom=pg.sum(1)*ng.sum(1)
        result=np.divide(np.sum(pg*(np.cumsum(ng,axis=1)-.5*ng),axis=1),denom,out=np.full(len(weights),np.nan),where=denom>0)
        assert abs(result[0]-roc_auc_score(y,prob,sample_weight=weights[0]))<1e-10
        return result
    def babooots(y,pred):
        pp=weights@y;nn=weights@(1-y)
        return .5*((weights@(y*(np.asarray(pred)==1)))/pp+(weights@((1-y)*(np.asarray(pred)==0)))/nn)
    bgboots={};metricboots={};maeboots={}
    for b in background:
        key=b['attribute']+'|'+b['attacker'];z=local['background'][key]
        au=aucboots(labels[b['attribute']],z['prob']);ba=babooots(labels[b['attribute']],z['pred']);bgboots[key]=au
        b.update(AUC95_low=interval(au)[0],AUC95_high=interval(au)[1],BA95_low=interval(ba)[0],BA95_high=interval(ba)[1])
    validations=[];stages=[];checks={};wire_count=0
    for sm in summaries:
        key=f'{sm["method"]}|{sm["intent"]}|{sm["wording"]}';ll=local[key];state=transforms[key];enc=c.Encoder(state['encoder']['indices'])
        for name in ['median','mean','scale']:setattr(enc,name,np.array(state['encoder'][name]))
        t={a:np.array(state[a]) for a in ['P','bias']};views,wires,v,vp,m=c.emit(dv,enc,t)
        assert wires==ll['wire'];wire_count+=len(wires)
        actual=np.array([[x[f'h{i}'] for i in range(3)] for x in views]);mask=np.array([[x[f'm{i}'] for i in range(3)] for x in views])
        assert np.array_equal(mask,m)
        actualdist=float(np.sum((actual-v)**2)/max(1e-30,np.sum(v**2)))
        sm['actual_wire_relative_squared_distortion']=actualdist
        sm['geometric_distortion_pre_quantization']=sm['relative_squared_distortion']
        err=np.asarray(ll['error']);boot=weights@err/den;maeboots[key]=boot;lo,hi=interval(boot);sm.update(MAE95_low=lo,MAE95_high=hi)
        sm['constraint_epsilon']=1.;sm['constraint_delta']=.20
        base=next(x for x in summaries if x['method']=='Identity' and x['intent']==sm['intent'] and x['wording']==sm['wording'])
        sm['delta_MAE_vs_Identity']=sm['MAE']-base['MAE'];sm['outer_utility_constraint_met']=sm['MAE']<=base['MAE']+1.
        sm['outer_geometric_distortion_constraint_met']=sm['relative_squared_distortion']<=.20
        sm['outer_actual_wire_distortion_constraint_met']=actualdist<=.20
        sm['outer_budget_constraint_met']=sm['actual_tokens_max']<=64
        sm['source_fields_public']=','.join(c.FIELDS[j] for j in enc.indices)
        for cutoff in [42,98,154]:
            ix=[i for i,r in enumerate(dv) if r['cutoff']==cutoff]
            stages.append({'method':sm['method'],'intent':sm['intent'],'wording':sm['wording'],'cutoff':cutoff,'n':len(ix),'MAE':float(err[ix].mean())})
        if sm['method'] in ['V3-rank1','V3-rank2']:
            w=np.array(c.load(P/'geometry.json')[sm['intent']+'|'+sm['wording']]['teacher_value_weight'])
            identity=np.array([[float(dict(z.split('=') for z in payload.splitlines())[f'h{i}']) for i in range(3)] for payload in local['Identity|'+sm['intent']+'|'+sm['wording']]['wire']])
            sm['teacher_linear_score_change_max_on_actual_wire']=float(np.max(abs((actual-identity)@w)))
        if sm['method']=='Identity':
            delta=actual*enc.scale+enc.mean-enc.raw(dv)
            checks[key]={'maximum_original_unit_reconstruction_error_by_field':{c.FIELDS[j]:float(np.nanmax(abs(delta[:,i]))) for i,j in enumerate(enc.indices)},'missing_flags_exact':True}
    for a in attacks:
        key=f'{a["method"]}|{a["intent"]}|{a["wording"]}';ak=a['attribute']+'|'+a['attacker'];z=local[key]['attacks'][ak]
        au=aucboots(labels[a['attribute']],z['prob']);ba=babooots(labels[a['attribute']],z['pred']);metricboots[(key,ak)]=(au,ba)
        lo,hi=interval(au);bl,bh=interval(ba);dl,dh=interval(au-bgboots[ak]);el,eh=interval(np.maximum(0,au-bgboots[ak]))
        a.update(AUC95_low=lo,AUC95_high=hi,BA95_low=bl,BA95_high=bh,delta_AUC_public95_low=dl,delta_AUC_public95_high=dh,nonnegative_excess95_low=el,nonnegative_excess95_high=eh)
    paired=[];gate=[];rank_pairs=[]
    for intent,wording in c.CONTEXTS:
        k='V3|'+intent+'|'+wording;ik='Identity|'+intent+'|'+wording
        sm=next(x for x in summaries if (x['method'],x['intent'],x['wording'])==('V3',intent,wording))
        ml,mh=interval(maeboots[k]-maeboots[ik]);rows=[]
        for attr in c.ATTRS:
            for kind in ['LR','RF']:
                ak=attr+'|'+kind;aa,bb=metricboots[(k,ak)];ia,ib=metricboots[(ik,ak)]
                al,ah=interval(aa-ia);bl,bh=interval(bb-ib)
                row={'intent':intent,'wording':wording,'comparison':'V3-minus-Identity','attribute':attr,'attacker':kind,'n_students':len(unique),
                     'delta_AUC':float(next(x['AUC'] for x in attacks if (x['method'],x['intent'],x['wording'],x['attribute'],x['attacker'])==('V3',intent,wording,attr,kind))-next(x['AUC'] for x in attacks if (x['method'],x['intent'],x['wording'],x['attribute'],x['attacker'])==('Identity',intent,wording,attr,kind))),
                     'delta_AUC95':[al,ah],'delta_BA95':[bl,bh],'delta_MAE95':[ml,mh]}
                paired.append(row);rows.append(row)
        improvements=[]
        for attr in c.ATTRS:
            v3=next(a for a in attacks if (a['method'],a['intent'],a['wording'],a['attribute'],a['attacker'])==('V3',intent,wording,attr,'RF'))
            base=next(a for a in attacks if (a['method'],a['intent'],a['wording'],a['attribute'],a['attacker'])==('Identity',intent,wording,attr,'RF'))
            ci=next(x['delta_AUC95'] for x in rows if x['attribute']==attr and x['attacker']=='RF')
            improvements.append({'attribute':attr,'RF_excess_reduction':base['nonnegative_excess_AUC']-v3['nonnegative_excess_AUC'],'AUC_delta95_upper':ci[1]})
        otherworse=any(r['delta_AUC']>.01 for r in rows)
        mainrisk=max(a['nonnegative_excess_AUC'] for a in attacks if (a['method'],a['intent'],a['wording'],a['attacker'])==('V3',intent,wording,'RF'))
        simple_no_greater=[]
        for reference in ['Identity','NoAtt-Identity','RoleReward-history','INLP3','LEACE','nonorth-half']:
            refsm=next(z for z in summaries if (z['method'],z['intent'],z['wording'])==(reference,intent,wording))
            identitysm=next(z for z in summaries if (z['method'],z['intent'],z['wording'])==('Identity',intent,wording))
            refrisk=max(a['nonnegative_excess_AUC'] for a in attacks if (a['method'],a['intent'],a['wording'],a['attacker'])==(reference,intent,wording,'RF'))
            if refsm['MAE']<=identitysm['MAE']+1. and refrisk<=mainrisk+1e-12 and refsm['actual_tokens_max']<=64:
                simple_no_greater.append(reference)
        passed=bool(sm['projection_rank_removed']>0 and sm['outer_utility_constraint_met'] and sm['outer_actual_wire_distortion_constraint_met'] and not otherworse and any(r['RF_excess_reduction']>=.02 and r['AUC_delta95_upper']<0 for r in improvements))
        passed=passed and not simple_no_greater
        gate.append({'intent':intent,'wording':wording,'rank':sm['projection_rank_removed'],'utility_met':sm['outer_utility_constraint_met'],
                     'distortion_met':sm['outer_actual_wire_distortion_constraint_met'],'improvements':improvements,
                     'references_within_utility_bound_and_no_greater_worst_RF_excess':simple_no_greater,'passed':passed})
        for probe in ['V3-rank1','V3-rank2']:
            pk=probe+'|'+intent+'|'+wording
            for attr in c.ATTRS:
                for kind in ['LR','RF']:
                    ak=attr+'|'+kind;pa,pb=metricboots[(pk,ak)];ia,ib=metricboots[(ik,ak)]
                    rank_pairs.append({'method':probe,'intent':intent,'wording':wording,'attribute':attr,'attacker':kind,
                        'delta_AUC95':interval(pa-ia),'delta_BA95':interval(pb-ib),
                        'delta_MAE95':interval(maeboots[pk]-maeboots[ik]),'role':'predeclared rank diagnostic; not used for outer-dev rank selection'})
    # Posthoc algebraic review only: rank2 in3D often is ordinary teacher-score compression.
    simple_readout=[];geometry=c.load(P/'geometry.json')
    for intent,wording in c.CONTEXTS:
        key='V3-rank2|'+intent+'|'+wording;state=transforms[key]
        w=np.array(geometry[intent+'|'+wording]['teacher_value_weight']);t=w/np.linalg.norm(w)
        smatrix=np.outer(t,t);p=np.array(state['P']);enc=c.Encoder(state['encoder']['indices'])
        for name in ['median','mean','scale']:setattr(enc,name,np.array(state['encoder'][name]))
        _,rewire,_,_,_=c.emit(dv,enc,{'P':smatrix,'bias':np.array(state['bias'])})
        ref=local[key]['wire']
        simple_readout.append({'intent':intent,'wording':wording,'P_rank2_minus_teacher_outer_frobenius':float(np.linalg.norm(p-smatrix)),
            'actual_wire_exact_equal_count':sum(x==y for x,y in zip(rewire,ref)),'n':len(dv),
            'status':'POSTHOC_ALGEBRAIC_AUDIT_ONLY; no model fit or changed method selection'})
    # Public aliases are explicitly labelled; they do not add independent fits.
    for method in ['TaskOnly-B5','V3-no-projection']:
        for intent,wording in c.CONTEXTS:
            base=copy.deepcopy(next(x for x in summaries if (x['method'],x['intent'],x['wording'])==('Identity',intent,wording)))
            base.update(method=method,exact_input_alias_of='Identity|'+intent+'|'+wording);summaries.append(base)
            copies=[copy.deepcopy(a) for a in attacks if (a['method'],a['intent'],a['wording'])==('Identity',intent,wording)]
            for a in copies:a.update(method=method,exact_input_alias_of=base['exact_input_alias_of'])
            attacks.extend(copies)
    # Pure posthoc wire replay with counterfactual forbidden columns: no new models.
    flips=0
    for row in dv[:12]:
        altered=copy.deepcopy(row);altered.update(student=-1,gender_F=1-row['gender_F'],disability_Y=1-row['disability_Y'],target_score=-999)
        for key in ['V3|trajectory|explicit','V3-rank1|trajectory|explicit']:
            state=transforms[key];enc=c.Encoder(state['encoder']['indices'])
            for name in ['median','mean','scale']:setattr(enc,name,np.array(state['encoder'][name]))
            t={a:np.array(state[a]) for a in ['P','bias']}
            before=c.emit([row],enc,t)[1];after=c.emit([altered],enc,t)[1];assert before==after
            assert c.parse(before[0],row)==c.parse(after[0],altered);flips+=1
    c.save('bootstrap.json',{'draws':500,'unit':'student_cluster','same_draws_all_methods':True,'intervals_for':'MAE/AUC/BA all methods, paired candidate-vsIdentity and background augmentation','conditional_on_fitted_models':True,'paired_primary':paired,'paired_rank_diagnostics':rank_pairs})
    c.save('teacher_readout_equivalence.json',simple_readout)
    c.save('identity_reconstruction.json',checks);c.save('validated_summary.json',summaries);c.save('validated_attacks.json',attacks);c.save('background_with_intervals.json',background);c.save('stage_results.json',stages)
    c.save('phaseD_gate.json',{'decision':'PIVOT' if not any(g['passed'] for g in gate) else 'ANALYZE','passed_contexts':sum(g['passed'] for g in gate),'n_contexts':6,'cells':gate,'independent_test_run':False,'no_posthoc_rank_selection':True})
    pu=[]
    for sm in summaries:
        for a in attacks:
            if (a['method'],a['intent'],a['wording'])==(sm['method'],sm['intent'],sm['wording']):pu.append({**sm,**a})
    for b in background:pu.append({'method':'Public-only','scope':'public_background_only','intent':'all','wording':'all','n':473,'n_students':166,**b})
    ab=[]
    for sm in summaries:
        row=copy.deepcopy(sm);row['attention']='fixed_train_MI3' if sm['method'].startswith('NoAtt-') else 'task_TFIDF_or_historical'
        for a in attacks:
            if (a['method'],a['intent'],a['wording'])==(sm['method'],sm['intent'],sm['wording']):
                row[a['attribute']+'_'+a['attacker']+'_AUC']=a['AUC'];row[a['attribute']+'_'+a['attacker']+'_BA']=a['BA']
        ab.append(row)
    csvout('mmfopd_v3_ablation.csv',ab);csvout('mmfopd_v3_privacy_utility.csv',pu)
    c.save('validation.json',{'status':'PASSED','preserved_prior_hashes':len(preserved),'locked_sources_unchanged':True,'vendor_unchanged':True,'wire_replays':wire_count,
        'forbidden_column_flip_cases':flips,'all_missing_flags_exact':True,'all_tokens_le64':all(x['actual_tokens_max']<=64 for x in summaries),
        'ablation_rows':len(ab),'privacy_utility_rows':len(pu),'new_fits_in_validator':0,'test_data_reads':0,'individual_data_synced':False,
        'note':'selection used pre-quantization geometric distortion; exact parsed-wire distortion independently checked and reported; no claim they are numerically identical'})
    print(json.dumps(c.load(P/'validation.json'),indent=2))

if __name__=='__main__':main()
