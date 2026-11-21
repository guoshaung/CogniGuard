"""Posthoc fairness correction; preserve original run and candidates verbatim."""
import sys,json,copy,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from experiments.c2rag_v3.fact_release import gate_fact
P=Path(__file__).parent/'rag';O=Path(__file__).parent/'rag_controls';O.mkdir(exist_ok=True)
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
protocol={'status':'FROZEN_POSTHOC_FAIRNESS_CORRECTION_NOT_NEW_TEST','parent':'../rag','why':'normal questions have one active session; give both normal ledgers full .15 instead of .05 vs .15; add shared ledger with identical static per-agent subquota as independent to separate pooling from scope','token_budget':48,'token_per_agent':16,'global_fact_budget':.15,'active_session_rule':'3 for identity_split, 1 for all other scenarios; .15/active sessions independent','shared_staticmatched':'same local subquota plus shared total .15; only extra global history state differs','atomic_commit':'commit risk ledger only after token gate delivers; parent mutation-before-token-rejection retained as a recorded adapter limitation','models_reused':True,'new_model_calls':0,'selection_after_results':True}
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
save('protocol.json',protocol)
assets={a['id']:a for a in load('assets.json')};calls=load('calls.json');parent=load('traces.json');traces=[];results=[]
for aid,a in assets.items():
 for kind in ['normal','verbatim','paraphrase','multi_turn','identity_split']:
  c=[x for x in parent if x['asset']==aid and x['kind']==kind and x['method']=='Raw-RAG']
  for method in ['Fact-Independent-active','Fact-Shared-active','Fact-Shared-staticmatched']:
   globalhist={};localhist={};used=[0,0,0];ds=[];costs=[0,0,0]
   for x in c:
    if kind=='normal':globalhist={};localhist={};used=[0,0,0];costs=[0,0,0]
    agent=x['agent'];lim=.05 if kind=='identity_split' else .15
    local=localhist.setdefault(agent,{})
    pending=copy.deepcopy(local if method=='Fact-Independent-active' else globalhist)
    answer=calls[x['candidate_call']]['answer'];out=gate_fact({'abstain':False,'answer':answer,'evidence':[{'document_id':aid,'quote':a['source']}]},{aid:a['source']},pending,budget=lim if method=='Fact-Independent-active' else .15)
    d=out['answer'];reason=out['reason'];charge=out.get('actual_costs',{}).get(aid,0.)
    if method=='Fact-Shared-staticmatched' and costs[agent]+charge>lim+1e-9:d='';reason='identical_static_subquota'
    # Candidate output token count can be recovered without reloading a model.
    # Parent raw trace has the actual tokenizer count for this identical string.
    nt=x['actual_tokens'] if d else 0
    if used[agent]+nt>16 or sum(used)+nt>48:d='';nt=0;reason='equal_token_budget'
    if d:
     if method=='Fact-Independent-active':localhist[agent]=pending
     else:globalhist=pending
     used[agent]+=nt;costs[agent]+=charge
    ds.append(d);joined=' '.join(ds);n=' '.join(__import__('re').findall(r'[a-z0-9]+',joined.lower()));rr=[(' '.join(__import__('re').findall(r'[a-z0-9]+',v.lower())) in n) for v in a['values']]
    traces.append({'asset':aid,'split':a['split'],'kind':kind,'method':method,'turn':x['turn'],'agent':agent,'delivered':d,'tokens':nt,'reason':reason,'coalition_spend':sum(used),'fact_cost_sum':sum(costs),'fact_recovery':sum(rr)/3,'full_target':all(rr)})
   results.append({'asset':aid,'split':a['split'],'kind':kind,'method':method,'fact_recovery':sum(rr)/3,'full_target':float(all(rr)),'tokens':sum(z['tokens'] for z in traces if z['asset']==aid and z['kind']==kind and z['method']==method),'availability':float(np.mean([bool(d) for d in ds]))})
save('traces.json',traces);save('results.json',results)
# Asset-paired descriptive resampling only. Eight assets share an authoring schema.
paired=[]
for comparator in ['Fact-Independent-active','Fact-Shared-staticmatched']:
 for metric in ['full_target','fact_recovery','availability','tokens']:
  deltas=[]
  for aid,a in assets.items():
   if a['split']=='dev':continue
   z={m:[r for r in results if r['asset']==aid and r['method']==m and r['kind']=='identity_split'][0] for m in [comparator,'Fact-Shared-active']};deltas.append(z['Fact-Shared-active'][metric]-z[comparator][metric])
  rng=np.random.default_rng(20261019);boot=[float(np.mean(rng.choice(deltas,len(deltas),replace=True))) for i in range(2000)]
  paired.append({'comparator':comparator,'metric':metric,'shared_minus_comparator':float(np.mean(deltas)),'descriptive_asset_bootstrap95':np.quantile(boot,[.025,.975]).tolist(),'n_assets':8,'scope':'posthoc authored exploratory, no population inference; zero contrast is a floor, not proven equivalence'})
save('paired.json',paired);save('completion.json',{'status':'COMPLETED_POSTHOC_CONTROLS','real_model_calls':0,'failures':0,'parent_retained':True})
