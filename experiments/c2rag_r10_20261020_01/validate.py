"""Post-freeze verification; never changes data, parser, decisions or scores."""
from pathlib import Path
import json,hashlib,sys
from fractions import Fraction as F
import engine as E
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def read(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,x):
 with (P/n).open('x',encoding='utf8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
protocol=read('protocol.json');assets=read('adjudicated_assets.json');plans=read('plans.json');rows=read('C_D_episodes.json')
cs={a['id']:a for a in read('public_contracts.json')};gold={a['id']:a['values'] for a in read('evaluator_gold.json')}
assert all('values' not in c and 'target_parameters' not in c for c in cs.values())
assert all(hashlib.sha256((P/n).read_bytes()).hexdigest()==h for n,h in protocol['hashes'].items())
preserve={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in read('preservation_before.json')}
assert preserve==read('preservation_before.json');save('preservation_after.json',preserve)
# Independent arithmetic implementation from frozen source rules, without SymPy.
funcs={
 'kinetic':lambda d:d['m']*d['v']**2/2,'gravity':lambda d:d['m']*F('49/5')*d['h'],
 'momentum':lambda d:d['m']*d['v'],'hooke':lambda d:d['k']*d['x'],'wave':lambda d:d['f']*d['l'],
 'capacitor':lambda d:d['C']*d['V'],'density':lambda d:d['m']/d['V'],'molarity':lambda d:d['n']/d['V'],
 'ideal-gas':lambda d:d['n']*F('8314/1000')*300/d['V'],'heat':lambda d:d['m']*4200*d['dT'],
 'pressure':lambda d:d['F']/d['A'],'electric-power':lambda d:d['V']*d['I'],
 'discriminant':lambda d:d['b']**2-4*d['c']>0,'log-domain':lambda d:d['x']-d['h']>0,
 'root-domain':lambda d:d['r']-d['x']**2>=0,'geometric-series':lambda d:abs(d['u']/d['v'])<1,
 'internal-reflection':lambda d:d['theta']>d['critical']}
derivations=[]
for i,g in gold.items():
 v=funcs[i]({k:F(v) for k,v in g.items()});actual=E.derived(g,cs[i]);assert str(v)==actual,(i,v,actual)
 derivations.append({'asset':i,'fraction_or_boolean_result':str(v),'sympy_result':actual,'equal':True})
save('independent_derivation_checks.json',derivations)
# Reference risk from author candidate labels, independent of text parsing and solvers.
annotation_checks=[]
for p in plans:
 hist=[];bound={};unsupported=False
 for turn,can in enumerate(p['candidates']):
  hist.append((can['q'],can['r']))
  if can['expected'] is None:unsupported=True
  else:bound.update(can['expected'])
  truth=None if unsupported else int(set(cs[p['asset']]['variables'])<=set(bound))
  actual=E.symbolic(hist,cs[p['asset']])['risk'];assert truth==actual,(p['asset'],p['scenario'],turn,truth,actual)
  annotation_checks.append({'asset':p['asset'],'scenario':p['scenario'],'turn':turn,'annotation_truth':truth,'symbolic':actual,'equal':True})
save('annotation_reference_checks.json',annotation_checks)
matched=[]
for p in plans:
 rr=[r for r in rows if r['asset']==p['asset'] and r['scenario']==p['scenario']]
 a=next(r for r in rr if r['method']=='B4-SharedClosure')
 for method in ['B5-Conditional-Matched','S-TypedSet']:
  b=next(r for r in rr if r['method']==method)
  same=[t['reply_token_ids'] for t in a['turns']]==[t['reply_token_ids'] for t in b['turns']]
  assert same;matched.append({'asset':p['asset'],'scenario':p['scenario'],'method':method,'same_reply_token_ids':same})
assert all(r['budget_ok'] for r in rows if 'budget_ok' in r)
save('matched_checks.json',matched)
save('validation.json',{'frozen_file_hashes_ok':True,'old_json_artifacts_unchanged':len(preserve),
 'symbolic_vs_finite_reference_prefix_checks':len(read('reference_checks.json')),
 'author_annotation_vs_solver_prefix_checks':len(annotation_checks),'independent_fraction_derivations':len(derivations),
 'matched_output_comparisons':len(matched),'method_episode_budget_checks':sum('budget_ok' in r for r in rows),
 'no_hidden_gold_fields_in_public_detector_contracts':True,'limitations':'same relation frontend shared by solvers; independent numeric backend and author labels are NOT independent human semantic annotation; no adaptive web/source/refusal-side-channel attacker'})
print(json.dumps(read('validation.json'),ensure_ascii=False,indent=2))
