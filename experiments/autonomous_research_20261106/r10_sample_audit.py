# Read-only retrospective audit of frozen R10 episodes; no models/tokenizers.
import ast, collections, hashlib, itertools, json, re
from fractions import Fraction as F
from types import SimpleNamespace
from pathlib import Path
root=Path('experiments/c2rag_r10_20261020_01')
def load(name): return json.loads((root/name).read_text(encoding='utf-8'))
tree=ast.parse((root/'engine.py').read_text(encoding='utf-8'))
names={'parse','collect','worlds','typedset'}
module=ast.Module(body=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names],type_ignores=[])
namespace={'re':re,'itertools':itertools,'F':F,'NUM':r'-?\d+(?:/\d+)?(?:\.\d+)?'}
exec(compile(module,str(root/'engine.py'),'exec'),namespace)
e=SimpleNamespace(**{n:namespace[n] for n in names})
contracts={x['id']:x for x in load('public_contracts.json')}
episodes=load('C_D_episodes.json')
plans={(x['asset'],x['scenario']):x for x in load('plans.json')}
methods=['B4-SharedClosure','B5-Conditional-Matched','S-TypedSet']
scenarios=['two_complementary','cross_agent']
rows=[]
for ep in episodes:
    if ep['scenario'] not in scenarios or ep['method'] not in methods: continue
    plan=plans[(ep['asset'],ep['scenario'])]; c=contracts[ep['asset']]; hist=[]
    for index, (turn,can) in enumerate(zip(ep['turns'],plan['candidates'])):
        prospective=hist+[(can['q'],can['r'])]
        sym=turn['detector']; finite=e.worlds(prospective,c); typed=e.typedset(prospective,c)
        rows.append({'asset':ep['asset'],'scenario':ep['scenario'],'method':ep['method'],
                     'turn':index+1,'agent':turn['agent'],'candidate_keys':sorted(e.parse(can['r'],c)[0]),
                     'previous_delivered_keys':sorted(e.collect(hist,c)[0]),
                     'allowed':bool(turn['reply']),'reason':turn['reason'],'observed_correct':turn['correct'],
                     'symbolic_risk':sym['risk'],'world_risk':finite['risk'], 'world_n':finite['world_n'],
                     'typed_risk':typed['risk'],'unknown':sym['unknown'], 'budget_ok':ep['budget_ok']})
        hist.append((can['q'],turn['reply']))
assert len(rows)==17*2*3*2
assert all(r['symbolic_risk']==r['world_risk']==r['typed_risk'] for r in rows)
assert all(r['allowed']==(r['symbolic_risk']==0) for r in rows)
assert all((r['allowed'] and r['turn']==1 and r['observed_correct']) or (not r['allowed'] and r['turn']==2 and not r['observed_correct'] and r['reason']=='risk_or_UNKNOWN' and r['world_n']==1) for r in rows)
summary={}
for scenario in scenarios:
 for method in methods:
  rr=[r for r in rows if r['scenario']==scenario and r['method']==method]
  summary[scenario+' / '+method]={'episodes':len(rr)//2,'allowed':sum(r['allowed'] for r in rr),'blocked':sum(not r['allowed'] for r in rr),'blocked_known_safe':sum(not r['allowed'] and r['world_risk']==0 for r in rr),'blocked_unknown':sum(not r['allowed'] and r['unknown'] for r in rr),'blocked_risk1':sum(not r['allowed'] and r['world_risk']==1 for r in rr)}
source_hashes={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['engine.py','run.py','plans.json','public_contracts.json','C_D_episodes.json']}
print(json.dumps({'source_hashes':source_hashes,'summary':summary,'sample_rows':rows},indent=2))

