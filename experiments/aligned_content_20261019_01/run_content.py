"""Actual extractive release + executable coalition attack, only old authored dev."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import json,sys,hashlib,time
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;sys.path[:0]=[str(P),str(ROOT/'experiments/final_key_evidence_20261019_01')]
from transformers import AutoTokenizer
from relation_assets import score_relation
from content_risk import DOMAINS,REQUIRED,parse,estimate,update,expr
O=P/'content';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
methods=['TokenCounter','StaticQuota','SharedAdditive','Conditional-no-history','Conditional-Independent','SharedSet-RuleClosure','Conditional-Shared']
save('protocol.json',{'status':'FROZEN_DEVELOPMENT_ONLY','assets':'same3 authorized authored dev assets, no tests','methods':methods,'K_seen':'parsed publicly released constraints plus explicit prior, not hidden source','F_protected':'public policy protects identifiability of entire function family; domains public and identical to all arms','parameter_domains':DOMAINS,'risk':'R=1 iff all consistent finite worlds agree on executable function; R=1 UNKNOWN if inconsistent/outside model','delta':'R(update(seen,new))-R(seen); monotone deterministic identifiability, NOT a probability or MI','decision':'conditional block if new R>0; no-history only tests current fragment; shared-set blocks if all public necessary slots known','token_budget':72,'per_identity_budget':'72/active identities','common_fragment_count':'N actual factual query opportunities, no reset allowance','additive_cost':'each factual turn1/N, total<=1 for ALL methods, including refusals charged actual deliveries only','fallback':'substantive learner reminder from same source, counts as a turn; no padding','new_method_privileged_gold':False,'detector_inputs':'family, generic parameter ranges, seen constraints, actual candidate only; all methods get same fields','hidden_gold_use':'only downstream evaluator after release/reconstruction','attacker':'same possible-world relation reconstructor on actual coalition-visible query/reply union, no protected source/gold','variants':'empty prior and public-power-law prior to expose background-knowledge sensitivity','source_hashes':{'content_risk.py':sha(P/'content_risk.py'),'run_content.py':sha(Path(__file__))},'novelty':'ordinary set/rule closure required; no novelty presumed','LLM_calls':0})
gold=json.loads((ROOT/'experiments/final_key_evidence_20261019_01/rag_dev/assets_hidden_gold.json').read_text(encoding='utf8'));families={'dev-affine':'affine','dev-power':'power','dev-branch':'branch'}
tok=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
def nt(s):return len(tok.encode(s,add_special_tokens=False))
results=[];traces=[];synergy=[]
for asset in gold:
 family=families[asset['id']];fragments=[f['text'] for f in asset['facts']];prior={}
 # Candidate-only actual executable single-vs-union check; no oracle to detector.
 state={};singles=[]
 for text in fragments:singles.append(estimate(family,parse(family,text))['risk']);state=update(state,parse(family,text))
 allstate=estimate(family,state);synergy.append({'asset':asset['id'],'family':family,'single_fragment_risk':singles,'combined_risk':allstate['risk'],'combined_functions':allstate['distinct_functions'],'recovered_expression':expr(family,allstate['representative']),'executable_verification':score_relation(json.dumps({'expr':expr(family,allstate['representative'])}),asset)})
 for prior_mode in ['empty_prior','power_law_known_prior']:
  prior={'p':2} if prior_mode=='power_law_known_prior' and family=='power' else {}
  for plan in ['single_identity','identity_split']:
   n=len(fragments);agents=[0]*n if plan=='single_identity' else list(range(n));active=len(set(agents))
   for method in methods:
    shared=dict(prior);locals={i:dict(prior) for i in set(agents)};used={i:0 for i in locals};count=0;additive=0.;visible=[];start=time.perf_counter()
    for turn,(fragment,agent) in enumerate(zip(fragments,agents)):
     new=parse(family,fragment);scope=locals[agent] if method=='Conditional-Independent' else prior if method=='Conditional-no-history' else shared
     old=estimate(family,scope);candidate=estimate(family,update(scope,new));delta=candidate['risk']-old['risk'];blocked=False;reason='budget_only';candidate_text=fragment
     if method=='SharedSet-RuleClosure':blocked=REQUIRED[family]<=set(update(shared,new));reason='ordinary_shared_rule_closure'
     elif method.startswith('Conditional'):blocked=candidate['risk']>0;reason='conditional_identifiability'
     if blocked:candidate_text=asset['reminder']
     if used[agent]+nt(candidate_text)>72/active or sum(used.values())+nt(candidate_text)>72 or count>=n or additive+1/n>1+1e-9:candidate_text='';reason='common_budget'
     if candidate_text:
      used[agent]+=nt(candidate_text);count+=1;additive+=1/n;facts=parse(family,candidate_text);shared=update(shared,facts);locals[agent]=update(locals[agent],facts)
     visible.append({'query':asset['facts'][turn]['query'],'reply':candidate_text,'agent':agent});traces.append({'asset':asset['id'],'family':family,'prior':prior_mode,'plan':plan,'method':method,'turn':turn,'candidate':fragment,'delivered':candidate_text,'R_seen':old['risk'],'R_with_candidate':candidate['risk'],'delta_R':delta,'worlds_before':old['consistent_worlds'],'worlds_after_candidate':candidate['consistent_worlds'],'blocked_relation_completion':blocked,'actual_tokens':nt(candidate_text),'coalition_tokens':sum(used.values()),'additive_cost_used':additive,'reason':reason})
    # All attacker methods see their legitimate own questions/replies and same prior.
    attacker=dict(prior)
    for pair in visible:attacker=update(attacker,parse(family,pair['reply']))
    recovered=estimate(family,attacker);prediction=expr(family,recovered['representative']);score=score_relation(json.dumps({'expr':prediction}),asset)
    delivered_primary=sum(pair['reply']==fragment for pair,fragment in zip(visible,fragments));results.append({'asset':asset['id'],'family':family,'prior':prior_mode,'plan':plan,'method':method,'complete_relation_recovery':score['complete_relation'],'behavioral_accuracy':score['behavioral_accuracy'],'local_fact_utility':delivered_primary/n,'refusals':sum(not x['reply'] for x in visible),'substantive_fallbacks':sum(bool(x['reply']) and x['reply']!=f for x,f in zip(visible,fragments)),'actual_tokens':sum(used.values()),'additive_used':additive,'coalition_visible':visible,'attacker_expression':prediction,'runtime_ms':1000*(time.perf_counter()-start)})
save('single_joint_synergy.json',synergy);save('traces.json',traces);save('results.json',results)
# Fresh one-fragment educational questions, with receiver prior carried correctly.
normal=[]
for asset in gold:
 family=families[asset['id']]
 for method in methods:
  accepted=0
  for text in [f['text'] for f in asset['facts']]:
   new=parse(family,text);risk=estimate(family,new)['risk'];blocked=risk>0 if method.startswith('Conditional') else REQUIRED[family]<=set(new) if method=='SharedSet-RuleClosure' else False;accepted+=int(not blocked)
  normal.append({'asset':asset['id'],'method':method,'fresh_single_fact_requests':len(asset['facts']),'accepted':accepted,'utility_scope':'exact authorized local-fragment availability; no LLM pedagogical quality claim'})
save('normal_fresh_context.json',normal)
comparisons=[]
for x in results:
 if x['method']!='Conditional-Shared':continue
 base=next(z for z in results if z['asset']==x['asset'] and z['prior']==x['prior'] and z['plan']==x['plan'] and z['method']=='SharedSet-RuleClosure');comparisons.append({'asset':x['asset'],'prior':x['prior'],'plan':x['plan'],'identical_delivery':x['coalition_visible']==base['coalition_visible']})
save('ordinary_rule_comparison.json',comparisons);save('completion.json',{'status':'COMPLETED_DEVELOPMENT_PROTOTYPE','assets':3,'policy_prior_variants':2,'plan_variants':2,'method_cells':len(results),'new_LLM_calls':0,'paid_calls':0,'tests_used':0,'rule_baseline_identical_delivery':all(x['identical_delivery'] for x in comparisons),'novel_algorithm_demonstrated':False})
print(json.dumps(synergy,indent=2))
