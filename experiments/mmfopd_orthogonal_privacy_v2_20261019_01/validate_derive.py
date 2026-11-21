"""No new fits: exact wire replay, preservation, cached anchor import, paired strata."""
from pathlib import Path
import sys,json,hashlib,csv,copy,collections
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];OLD=ROOT/'experiments/oulad_dynamic_20261019_01'
sys.path[:0]=[str(P),str(OLD),str(ROOT)]
import run_dev as r
import privacy_core as pc

def load(p):return json.loads(p.read_text(encoding='utf8'))
def save(n,v):r.save(n,v)

def main():
    lock=load(P/'execution_lock.json')
    assert all(r.sha(P/n)==h for n,h in lock['sources_sha256'].items())
    preserved=load(P/'preservation.json')
    assert all(r.sha(ROOT/n)==h for n,h in preserved.items())
    refs=load(P/'reference_sources.json')['references']
    assert all(r.sha(P/'vendor/concept_erasure'/x['url'].split('/')[-1])==x['sha256'] for x in refs)
    rows=load(OLD/'dev_data/snapshots_LOCAL.json');tr=[x for x in rows if x['split']=='train'];dv=[x for x in rows if x['split']=='dev']
    encdata=load(P/'representation.json');enc=pc.ProfileEncoding(r.d.FIELDS)
    enc.medians=np.array(encdata['train_medians']);enc.mean=np.array(encdata['train_mean']);enc.scale=np.array(encdata['train_scale'])
    transforms={k:{a:np.array(b) for a,b in t.items()} for k,t in load(P/'projection_matrices.json').items()}
    local=load(P/'predictions_LOCAL.json');templates=load(P/'readout_templates.json');fields=list(r.d.FIELDS)
    replay=0;flip=0
    for idx,row in enumerate(dv[:12]):
        changed=copy.deepcopy(row);changed['gender_F']=1-row['gender_F'];changed['disability_Y']=1-row['disability_Y'];changed['target_score']=-999;changed['student']=-1
        assert np.array_equal(enc.transform([row]),enc.transform([changed]));flip+=1
        for intent in r.d.INTENTS:
            for wording in ['explicit','ambiguous']:
                slots=[fields.index(k) for k in templates[f'{intent}|{wording}|{row["cutoff"]}']['fields']]
                for method,t in [('Att+Identity','Identity'),('Att+OPP','OPP'),('Att+LEACE','LEACE'),('Att+INLP3','INLP3')]:
                    z=pc.apply_transform(enc.transform([row]),transforms[t])[0]
                    actual=r.wire(z[slots]);assert actual==local[f'{method}|{intent}|{wording}']['wire'][idx]
                    assert r.parsed_view(row,actual)==r.parsed_view(changed,actual)
                    replay+=1
    # Import actual earlier raw-field fits. No claim of having rerun these fits.
    cached=load(OLD/'dev_results/summary.json');cached_attacks=load(OLD/'dev_results/attacks.json');cases=load(OLD/'dev_results/cases_LOCAL.json')
    lookup={(x['student'],x['cutoff']):x for x in dv}
    anchors=['SafeTaskTopK','Repaired-Full','Repaired-no-projection','TaskSlot','TrainMI']
    anchor_results=[];anchor_attacks=[];strata=[];fairness=[]
    for entry in cached:
        if entry['method'] not in anchors:continue
        key=(entry['method'],entry['intent'],entry['wording'])
        cc=[c for c in cases if (c['method'],c['intent'],c['wording'])==key]
        assert len(cc)==473
        missing=[sum(lookup[(c['student'],c['cutoff'])]['values'][k] is None for k in c['selected_fields'])/3 for c in cc]
        anchor_results.append({'method':entry['method'],'intent':entry['intent'],'wording':entry['wording'],
            'interface':'raw_top3_fields','provenance':'REUSED_FROZEN_OULAD_DEV_FIT',
            'n_snapshots':473,'n_students':166,'MAE':entry['MAE'],'observed_grade_MAE':entry['observed_score_MAE'],
            'observed_grade_n':entry['observed_score_n'],'actual_tokens_mean':entry['actual_tokens_mean'],
            'actual_tokens_max':entry['actual_tokens_max'],'scalar_count':3,'raw_fact_recall':None,
            'source_slot_contract_recall':entry['contract_schema_recall'],'source_slot_missing_fraction':float(np.mean(missing)),
            'physical_output_missing_fraction':float(np.mean(missing)),'mean_delivery_ms_amortized':None,
            'cached_selector_ms_not_comparable':entry['mixed_cache_selector_ms'],'direct_sensitive_release_count':0,'failures':0})
        for a in cached_attacks:
            if (a['method'],a['intent'],a['wording'])==key:
                public=next(x for x in load(P/'attack_results.json') if x['scope']=='public_only' and x['attribute']==a['attribute'] and x['attacker']==a['attacker'])
                anchor_attacks.append({**a,'scope':'actual_release_plus_public','Accuracy':None,'accuracy_note':'not recorded in frozen original; not invented or retrained',
                    'delta_AUC_vs_public':a['AUC']-public['AUC'],'delta_BA_vs_public':a['BA']-public['BA'],
                    'nonnegative_observed_AUC_excess':max(0.,a['AUC']-public['AUC']),'provenance':'REUSED_FROZEN_OULAD_DEV_FIT'})
        if entry['method']=='SafeTaskTopK':
            src=local[f'Att+Identity|{entry["intent"]}|{entry["wording"]}']
            sd={(c['student'],c['cutoff']):set(c['selected_fields']) for c in cc}
            fairness.append({'intent':entry['intent'],'wording':entry['wording'],
                             'Att_identity_vs_SafeTaskTopK_source_fields_equal_rate':float(np.mean([sd[(row['student'],row['cutoff'])]==set(s) for row,s in zip(dv,src['slots'])])),
                             'interface_information_difference':'raw has NA/availability flags; summaryIdentity only3 train-imputed rounded values. Projection summary mixes all13 fields+missingness.'})
    summaries=load(P/'summary_results.json')
    for s in summaries:
        key=f'{s["method"]}|{s["intent"]}|{s["wording"]}';x=local[key]
        for label in [42,98,154]:
            ix=[i for i,row in enumerate(dv) if row['cutoff']==label]
            strata.append({'method':s['method'],'intent':s['intent'],'wording':s['wording'],'cutoff':label,'n_snapshots':len(ix),
                           'MAE':float(np.mean([abs(x['prediction'][i]-dv[i]['target_score']) for i in ix])),
                           'actual_tokens_mean':float(np.mean([x['tokens'][i] for i in ix]))})
    save('field_anchor_results.json',anchor_results);save('field_anchor_attacks.json',anchor_attacks);save('interface_fairness.json',fairness)
    save('stage_results.json',strata)
    allsum=summaries+anchor_results;allatt=load(P/'attack_results.json')+anchor_attacks
    save('all_method_results.json',allsum)
    ab=[];pu=[]
    for s in allsum:
        actual=[a for a in allatt if a['scope']=='actual_release_plus_public' and (a['method'],a['intent'],a['wording'])==(s['method'],s['intent'],s['wording'])]
        abrow={**s,'attention': 'task_TFIDF_only' if s['method'].startswith('Att+') else ('fixed_train_MI3' if s['method'].startswith('NoAtt+') else 'legacy_field_anchor'),
               'projection':s['method'].split('+')[-1] if '+' in s['method'] else ('legacy_role_reward_NOT_privacy' if s['method']=='Repaired-Full' else 'none'),
               'token_cap':64,'output_slots':3,'sensitivity_threshold':.7,
               'pure_projection_control':'Att+Identity' if s['method']=='Att+OPP' else ('NoAtt+Identity' if s['method']=='NoAtt+OPP' else ''),
               'common_hardgate':'13 explicitly safe source fields; no direct gender/disability or IDs'}
        for a in actual:
            abrow[a['attribute']+'_'+a['attacker']+'_AUC']=a['AUC']
            abrow[a['attribute']+'_'+a['attacker']+'_BA']=a['BA']
            pu.append({**s,**a})
        ab.append(abrow)
    for a in load(P/'internal_attacks.json')+[x for x in allatt if x['scope']=='public_only']:
        calibration={}
        if a['scope']=='z_plus_public':
            b=next(x for x in allatt if x['scope']=='public_only' and x['attribute']==a['attribute'] and x['attacker']==a['attacker'])
            calibration={'delta_AUC_vs_public':a['AUC']-b['AUC'],'delta_BA_vs_public':a['BA']-b['BA'],
                         'nonnegative_observed_AUC_excess':max(0.,a['AUC']-b['AUC'])}
        pu.append({**a,**calibration,'MAE':None,'actual_tokens_mean':None,'interface':'internal_not_delivered' if a['scope']!='public_only' else 'public_background_only'})
    r.writecsv('mmfopd_v2_ablation.csv',ab);r.writecsv('mmfopd_v2_privacy_utility.csv',pu)
    save('validation.json',{'status':'PASSED','frozen_source_hashes_unchanged':True,'prior_source_and_core_hashes_unchanged':len(preserved),
        'vendor_reference_hashes_unchanged':True,'exact_wire_replays':replay,'dev_label_target_ID_flip_invariance_cases':flip,
        'new_model_fits_in_validator':0,'test_data_reads':0,'ablation_rows':len(ab),'privacy_utility_rows':len(pu),
        'all_reply_token_cap64':all(s['actual_tokens_max']<=64 for s in allsum),'all_new_summaries_exactly3_scalars':all(s['scalar_count']==3 for s in summaries),
        'per_record_outputs_only_LOCAL':True,'raw_field_vs_summary_budget_equivalent':False,
        'repeat_snapshots_not_independent_students':True})
    print(json.dumps(load(P/'validation.json'),indent=2))

if __name__=='__main__':main()
