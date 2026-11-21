"""Finite predeclared ablations; final rank chosen on outer TRAIN students only."""
import core as c
import candidate as algo
import numpy as np
import hashlib,copy,time
P=c.P
if not c.load(P/'phaseB_gate.json')['all_contexts_pass']:raise RuntimeError('PhaseB failed: stop optimization')
if (P/'phaseC_lock.json').exists():raise RuntimeError('No overwrite')
c.save('phaseC_lock.json',{'status':'FROZEN_BEFORE_CANDIDATE_FITS','sources':{n:c.sha(P/n) for n in ['protocol.json','core.py','candidate.py','phase_c.py']},'outer_dev_not_for_rank_selection':True})
started=time.perf_counter();tr,dv=c.dataset()
is_inner=lambda r:int(hashlib.sha256(('mmfopd-v3-inner:'+str(r['student'])).encode()).hexdigest(),16)%4==0
innerfit=[r for r in tr if not is_inner(r)];innerval=[r for r in tr if is_inner(r)]
assert {r['student'] for r in innerfit}.isdisjoint({r['student'] for r in innerval})
assert {r['student'] for r in innerfit+innerval}=={r['student'] for r in tr}
bg=c.load(P/'background_attacks.json');innerbg,_=c.background(innerfit,innerval)
summaries=c.load(P/'phaseB_summary.json');attacks=c.load(P/'phaseB_attacks.json');local=c.load(P/'phaseB_predictions_LOCAL.json')
cache={};selection_cache={};selection={};transforms_out={};records={};aliases=[]

def final_eval(method,enc,t,intent,wording,extra=None):
    # Reuse only byte-identical serialized inputs to identical fixed models.
    _,wtr,_,_,_=c.emit(tr,enc,t);_,wdv,_,_,_=c.emit(dv,enc,t)
    fingerprint=hashlib.sha256('\x1e'.join(wtr+wdv).encode()).hexdigest()
    if fingerprint in cache:
        sm,aa,ll=copy.deepcopy(cache[fingerprint]);prior=sm['method']+'|'+sm['intent']+'|'+sm['wording'];aliases.append({'method':method,'intent':intent,'wording':wording,'exact_input_alias_of':prior})
        for x in [sm]+aa:x.update(method=method,intent=intent,wording=wording)
        sm['source_schema_recall_proxy']=len({c.FIELDS[j] for j in enc.indices}&set(c.d.INTENTS[intent]['required']))/3
        sm['exact_input_alias_of']=prior
    else:
        sm,aa,ll,_=c.evaluate(method,tr,dv,enc,t,intent,wording,bg);cache[fingerprint]=copy.deepcopy((sm,aa,ll))
    if extra:sm.update(extra)
    summaries.append(sm);attacks.extend(aa);local[f'{method}|{intent}|{wording}']=ll
    transforms_out[f'{method}|{intent}|{wording}']={'encoder':enc.state(),'P':t['P'].tolist(),'bias':t['bias'].tolist()}
    print('PhaseC',method,intent,wording,'MAE',round(sm['MAE'],4),'rank',sm['projection_rank_removed'],flush=True)

# Seed exact input cache from PhaseB without repeating its fits.
for intent,wording in c.CONTEXTS:
    enc=c.Encoder(c.field_sets(intent,wording)).fit(tr);v,_=enc.transform(tr);s=np.array([[r[a] for a in c.ATTRS] for r in tr])
    for method,t in [('Identity',c.identity()),('OPP-v2-style',c.covariance_projection(v,s))]:
        _,wt,_,_,_=c.emit(tr,enc,t);_,wv,_,_,_=c.emit(dv,enc,t);fingerprint=hashlib.sha256('\x1e'.join(wt+wv).encode()).hexdigest()
        sm=next(x for x in summaries if (x['method'],x['intent'],x['wording'])==(method,intent,wording))
        aa=[x for x in attacks if (x['method'],x['intent'],x['wording'])==(method,intent,wording)]
        cache[fingerprint]=copy.deepcopy((sm,aa,local[f'{method}|{intent}|{wording}']))
        transforms_out[f'{method}|{intent}|{wording}']={'encoder':enc.state(),'P':t['P'].tolist(),'bias':t['bias'].tolist()}

for intent,wording in c.CONTEXTS:
    for attention in [True,False]:
        ids=c.field_sets(intent,wording,attention=attention);enc=c.Encoder(ids).fit(tr)
        skey=tuple(ids)
        if skey not in selection_cache:
            choices={}
            for label,protect,lossgate in [('primary',True,True),('no-loss-gate',True,False),('no-teacher-protection',False,True)]:
                choices[label]=algo.select_rank(innerfit,innerval,ids,innerbg,protect=protect,loss_gate=lossgate)
            selection_cache[skey]=choices
        choices=selection_cache[skey];prefix='' if attention else 'NoAtt-'
        family,geo=algo.family(tr,enc,True)
        rank,sel=choices['primary'];selection[prefix+intent+'|'+wording]=sel
        final_eval(prefix+'V3',enc,family[rank],intent,wording,{'selected_rank_requested':rank,'training_selection':'inner_students_only'})
        records[prefix+intent+'|'+wording]=geo
        if not attention:
            final_eval('NoAtt-Identity',enc,c.identity(),intent,wording)
            continue
        # All ablations predeclared; none chosen using outer-dev metrics.
        for r in [1,2]:final_eval('V3-rank'+str(r),enc,family[r],intent,wording,{'rank_requested':r})
        r,_=choices['no-loss-gate'];final_eval('V3-no-loss-gate',enc,family[r],intent,wording,{'selected_rank_requested':r})
        selection['no-loss-gate|'+intent+'|'+wording]=choices['no-loss-gate'][1]
        unprotected,ug=algo.family(tr,enc,False);r,_=choices['no-teacher-protection']
        final_eval('V3-no-teacher-protection',enc,unprotected[r],intent,wording,{'selected_rank_requested':r})
        selection['no-teacher-protection|'+intent+'|'+wording]=choices['no-teacher-protection'][1]
        half={'P':.5*(np.eye(3)+family[rank]['P']),'bias':family[rank]['bias']}
        final_eval('nonorth-half',enc,half,intent,wording)
        v,_=enc.transform(tr);s=np.array([[r[a] for a in c.ATTRS] for r in tr]);refs,refmeta=algo.references(v,s)
        records['INLP3|'+intent+'|'+wording]=refmeta
        for name,t in refs.items():final_eval(name,enc,t,intent,wording)
        historical=c.Encoder(c.field_sets(intent,wording,historical=True)).fit(tr)
        final_eval('RoleReward-history',historical,c.identity(),intent,wording)
    c.save('all_summary.json',summaries);c.save('all_attacks.json',attacks);c.save('all_predictions_LOCAL.json',local)
    c.save('selection_inner.json',selection);c.save('transforms.json',transforms_out);c.save('geometry.json',records)

# B5/task-selection-only and no-projection are exact Identity aliases, not extra fits.
aliases.extend([{'method':m,'intent':i,'wording':w,'exact_input_alias_of':'Identity|'+i+'|'+w} for i,w in c.CONTEXTS for m in ['TaskOnly-B5','V3-no-projection']])
c.save('aliases.json',aliases)
c.save('inner_background.json',innerbg)
c.save('phaseC_completion.json',{'status':'COMPLETED_TRAIN_DEV_ONLY','total_method_context_rows':len(summaries),'actual_attack_rows':len(attacks),
    'distinct_actual_input_model_fits':len(cache),'outer_train_students':len({r['student'] for r in tr}),'outer_dev_students':len({r['student'] for r in dv}),
    'inner_fit_students':len({r['student'] for r in innerfit}),'inner_validation_students':len({r['student'] for r in innerval}),
    'inner_fit_snapshots':len(innerfit),'inner_validation_snapshots':len(innerval),'candidate_rank_set':[0,1,2],
    'actual_seconds':time.perf_counter()-started,'selection_used_outer_dev':False,'paid_calls':0,'data_or_model_downloads':False,'2014J_access':False,'failures':0})
print('PhaseC complete; no independent test authorized or run',flush=True)
