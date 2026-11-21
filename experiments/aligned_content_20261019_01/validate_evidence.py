"""Audit immutable results; output aggregates only for real students."""
from pathlib import Path
import json,hashlib,sys,itertools
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(P))
import aligned_selector as a
import content_risk as c
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
checks={};pres=load(P/'preservation.json');checks['core_unchanged']=all(sha(ROOT/k)==v for k,v in pres['core'].items());oldn=0
for old in pres['previous']:
 base=ROOT/'experiments'/old['directory'];assert sha(base/'evidence_manifest.json')==old['manifest_sha256']
 for row in old['files']:assert sha(base/row['path'])==row['sha256'];oldn+=1
checks['previous_files_unchanged']=oldn
plan=load(P/'protocol.json');checks['frozen_algorithm_unchanged']=sha(P/'aligned_selector.py')==plan['repair_source_sha256']
lock=load(P/'mm_v2/selected_config_lock.json');assert sha(P/'run_mm_v2.py')==lock['driver_sha256']
errors=[]
for bits in itertools.product([0.,1.],repeat=14):
 mask=np.array(bits);proj=np.diag(mask);z=np.arange(1,15,dtype=float)/14;u=proj@z;v=z-u
 errors.append(max(np.max(np.abs(proj-proj.T)),np.max(np.abs(proj@proj-proj)),abs(float(u@v))))
checks['projector_masks_checked']=len(errors);checks['max_symmetry_idempotency_residual_dot_error']=max(errors);assert max(errors)<1e-12
mechanics=[];fair=[];samples=0
for subject in ['Math','Portuguese']:
 data={m:load(P/('corrected_baselines' if m in ['Original-commonpool','TaskSlot-commonpool'] else 'mm_v2')/f'{subject}_{m}_LOCAL.json') for m in plan['methods']};full=data['Repaired-Full'];ts=full['test_indices']
 for m,d in data.items():
  assert all(len(z)==3 for z in d['selection_all']);assert max(d['tokens'])<=32;samples+=len(d['selection_all'])
  same=sum(d['selection_all'][i]==full['selection_all'][i] for i in ts);mechanics.append({'dataset':subject,'method':m,'n':len(ts),'same_final_fields_count':same})
  if m.startswith('Repaired'):
   for trace in d['traces']:
    if trace['attention_unit_scale'] is not None:assert min(trace['attention_unit_scale'])>=0 and max(trace['attention_unit_scale'])<=1+1e-12
 fair.append({'dataset':subject,'calls':len(full['selection_all'])*len(data),'all_K3':True,'max_tokens':max(max(d['tokens']) for d in data.values()),'Full_Safe_all_rows_identical':full['selection_all']==data['SafeTaskTopK']['selection_all'],'Full_Safe_test_canonical_bytes_identical':all(full['selection_all'][i]==data['SafeTaskTopK']['selection_all'][i] for i in ts)})
rows=[x for x in load(P/'new_families/rows.json') if x['method'] not in ['Original-commonpool','TaskSlot-commonpool']]+load(P/'corrected_baselines/new_rows.json');data=load(P/'new_families/authored_data.json');lookup={(x['id'],x['method']):x for x in rows};test=[x for x in data if x['split']=='test'];assert len(test)==160
for x in rows:assert len(x['selected_fields'])==3 and x['tokens']<=32 and not x['direct_exposure']
newpairs=[]
for method in plan['methods']:
 diff=sum(lookup[x['id'],method]['selected_fields']!=lookup[x['id'],'Repaired-Full']['selected_fields'] for x in test);pred=sum(abs(lookup[x['id'],method]['prediction']-lookup[x['id'],'Repaired-Full']['prediction'])>1e-10 for x in test)
 newpairs.append({'method':method,'n':160,'fields_changed_count':diff,'fields_changed_rate':diff/160,'prediction_changed_count':pred})
fair.append({'dataset':'new_synthetic_families','calls':len(rows),'all_K3':True,'max_tokens':max(x['tokens'] for x in rows),'Full_Safe_test_canonical_bytes_identical':newpairs[2]['fields_changed_count']==0})
# Typed finite hypotheses: monotonic risk under consistent constraints.
monotonic=0
for family,domain in c.DOMAINS.items():
 world={k:v[len(v)//2] for k,v in domain.items()};keys=list(world)
 for n in range(len(keys)+1):
  for subset in itertools.combinations(keys,n):
   known={k:world[k] for k in subset};before=c.estimate(family,known)['risk']
   for k in keys:
    after=c.estimate(family,c.update(known,{k:world[k]}))['risk'];assert after>=before;monotonic+=1
assert c.estimate('affine',{'a':100})['status']=='UNKNOWN_OUT_OF_HYPOTHESIS'
assert c.estimate('affine',c.update({'a':3},{'a':4}))['risk']==1
checks['risk_consistent_extensions_monotonic_checked']=monotonic
# Deliberate scope failure: naked parse returns {} for unsupported semantics.
checks['free_text_frontend_limitation']={'input':'The increment equals seven units, so use it after scaling.','parse':c.parse('affine','The increment equals seven units, so use it after scaling.'),'status':'UNSUPPORTED_NATURAL_LANGUAGE; generic deployment requires UNKNOWN, current prototype only accepts frozen typed grammar'}
results=load(P/'content/results.json');tr=load(P/'content/traces.json');assert all(x['actual_tokens']<=72 and x['additive_used']<=1+1e-9 for x in results)
assert all(x['coalition_tokens']<=72 and x['additive_cost_used']<=1+1e-9 for x in tr)
assert all(x['identical_delivery'] for x in load(P/'content/ordinary_rule_comparison.json'))
assert all(all(v==0 for v in x['single_fragment_risk']) and x['combined_risk']==1 and x['executable_verification']['complete_relation'] for x in load(P/'content/single_joint_synergy.json'))
main=[x for x in results if x['prior']=='empty_prior' and x['plan']=='identity_split'];agg=[]
for method in load(P/'content/protocol.json')['methods']:
 z=[x for x in main if x['method']==method];den=sum(len(x['coalition_visible']) for x in z);facts=sum(round(x['local_fact_utility']*len(x['coalition_visible'])) for x in z)
 agg.append({'method':method,'n_assets':len(z),'complete_recovery_n':sum(x['complete_relation_recovery'] for x in z),'complete_recovery_rate':np.mean([x['complete_relation_recovery'] for x in z]),'fact_utility_macro':np.mean([x['local_fact_utility'] for x in z]),'fact_utility_micro':facts/den,'facts_delivered':facts,'factual_requests':den,'actual_tokens_mean':np.mean([x['actual_tokens'] for x in z]),'refusals':sum(x['refusals'] for x in z),'fallbacks':sum(x['substantive_fallbacks'] for x in z)})
save('fairness_checks.json',fair);save('new_families/paired_mechanisms.json',newpairs);save('content/aggregate_main.json',agg);save('mm_v2/paired_field_counts.json',mechanics)
audit=load(P/'visibility_audit/aggregate_main.json');assert next(x for x in audit if x['method']=='Conditional-Shared')['complete_recovery_n']==1
checks.update({'status':'VERIFIED_RESULTS_WITH_REAL_SEMANTIC_FAILURE','old_MM_selection_records_audited':samples,'new_MM_selection_records_audited':len(rows),'content_method_cells':len(results),'shared_rule_identical_scenarios':12,'corrected_baselines':load(P/'corrected_baselines/completion.json'),'ingress_changes':load(P/'corrected_baselines/changes.json'),'fallback_semantic_audit':load(P/'visibility_audit/completion.json'),'NOT_A_SAFETY_CERTIFICATE':True})
assert checks['core_unchanged'] and checks['frozen_algorithm_unchanged'];assert checks['corrected_baselines']['status'].startswith('COMPLETED')
save('validation.json',checks);print(json.dumps(checks,indent=2))
