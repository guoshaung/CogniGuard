"""Interface regression first. Refuse to start optimization before passing."""
import core as c
import numpy as np
P=c.P
if (P/'phaseB_lock.json').exists():raise RuntimeError('No overwrite')
c.save('phaseB_lock.json',{'status':'FROZEN_BEFORE_FIT','sources':{n:c.sha(P/n) for n in ['protocol.json','core.py','phase_b.py']},'2014J_access':False})
tr,dv=c.dataset();bg,bgl=c.background(tr,dv);summaries=[];attacks=[];locals={'background':bgl};gates=[];states={}
cached=c.load(c.OLD/'dev_results/summary.json')
for intent,wording in c.CONTEXTS:
    ids=c.field_sets(intent,wording);enc=c.Encoder(ids).fit(tr);v,_=enc.transform(tr);s=np.array([[r[a] for a in c.ATTRS] for r in tr])
    states[intent+'|'+wording]=enc.state()
    for method,t in [('Identity',c.identity()),('OPP-v2-style',c.covariance_projection(v,s))]:
        sm,aa,ll,model=c.evaluate(method,tr,dv,enc,t,intent,wording,bg)
        summaries.append(sm);attacks+=aa;locals[f'{method}|{intent}|{wording}']=ll
        if method=='Identity':
            ref=next(x for x in cached if x['method']=='SafeTaskTopK' and x['intent']==intent and x['wording']==wording)
            gates.append({'intent':intent,'wording':wording,'Identity_MAE':sm['MAE'],'same_source_cached_raw_MAE':ref['MAE'],
                          'delta_MAE':sm['MAE']-ref['MAE'],'passed':sm['MAE']<=ref['MAE']+1.0 and sm['actual_tokens_max']<=64})
        print('PhaseB',method,intent,wording,round(sm['MAE'],4),round(sm['actual_tokens_mean'],2),flush=True)
    c.save('phaseB_summary.json',summaries);c.save('phaseB_attacks.json',attacks);c.save('phaseB_predictions_LOCAL.json',locals)
c.save('background_attacks.json',bg);c.save('encoder_states.json',states)
c.save('phaseB_gate.json',{'all_contexts_pass':all(g['passed'] for g in gates),'cells':gates,'epsilon_interface':1.0,'next':'PhaseC authorized by protocol' if all(g['passed'] for g in gates) else 'STOP before optimization; PIVOT'})
print('PhaseB gate',all(g['passed'] for g in gates),flush=True)
