"""Independent SymPy backend checks and source/budget/denominator audit."""
from pathlib import Path
import hashlib,json,sys
sys.stdout.reconfigure(encoding='utf8')
import sympy as S
import engine as E
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
def read(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,x):
    with (P/n).open('x',encoding='utf8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
contracts={x['id']:x for x in read('public_contracts.json')}
assert all('target_parameters' not in c for c in contracts.values())
def rational(x):return S.Rational(x)
def independent(history,c):
    facts,unknown=E.history_facts(history,c)
    if unknown:return None,'UNSUPPORTED'
    eq=[]
    if c['kind']=='affine':
        variables=S.symbols('a b')
        for a in facts:
            if a[0]=='point':eq.append(variables[0]*rational(a[1])+variables[1]-rational(a[2]))
    elif c['kind']=='ohm':
        variables=(S.Symbol('R'),);vs={(a[1],a[2]):rational(a[3]) for a in facts if a[0]=='value'}
        if ('operating','I') in vs and ('operating','V') in vs:
            eq.append(vs['operating','I']*variables[0]-vs['operating','V'])
    else:
        variables=S.symbols('R_hot R_cold');vs={(a[1],a[2]):rational(a[3]) for a in facts if a[0]=='value'}
        if ('hot','P') in vs:eq.append(vs['hot','P']*variables[0]-rational(c['known_voltage'])**2)
        if ('cold','R') in vs:eq.append(variables[1]-vs['cold','R'])
    if not eq:return None,'NONUNIQUE'
    sol=S.linsolve(eq,variables)
    if sol==S.EmptySet:return None,'INCONSISTENT'
    v=next(iter(sol))
    return (tuple(str(x) for x in v),'UNIQUE') if not any(x.free_symbols for x in v) else (None,'NONUNIQUE')

solver_checks=0;budget_checks=0
for r in read('e2_raw_results.json'):
    if 'turns' not in r:continue
    ts=r['turns'];active=len(set(t['agent'] for t in ts))
    assert sum(t['tokens'] for t in ts)==r['actual_tokens']<=128
    for agent in {t['agent'] for t in ts}:
        sub=[t for t in ts if t['agent']==agent]
        assert sum(t['tokens'] for t in sub)<=128/active
        assert sum(bool(t['delivered']) for t in sub)*.5<=1/active+1e-9
    assert all(t['tokens']<=64 for t in ts);budget_checks+=1
    if r['status']=='SCORED':
        output,status=independent([(t['query'],t['delivered']) for t in ts],contracts[r['asset']])
        assert status!='INCONSISTENT'
        expected=tuple(r['attacker']['parameters']) if r['attacker']['parameters'] is not None else None
        assert output==expected,(r['asset'],r['scenario'],r['method'],output,expected)
        solver_checks+=1
    else:assert r['complete_recovery'] is None
for r in read('e3_raw_results.json'):
    history=[tuple(x) for x in r['prefix_visible']]+[(r['query'],r['delivered'])]
    output,status=independent(history,contracts[r['asset']])
    expected=tuple(r['attacker']['parameters']) if r['attacker']['parameters'] is not None else None
    assert output==expected
    assert r['risk_checked'] is True
    if r['strategy']!='Original-Full' and r['delivered']:assert r['proposed_risk']==0
    assert r['reply_tokens']<=64 and r['total_history_reply_tokens']<=128
    solver_checks+=1
    assert r['normal_correct']==(set(tuple(x) for x in r['required_atoms'])<=set(tuple(x) for x in r['delivered_atoms']))

single=[]
for plan in read('e2_frozen_plans.json'):
    if plan['scenario']!='cross_agent':continue
    c=contracts[plan['asset']]
    single.append({'asset':c['id'],'single_candidate_risks':[
        E.assess([(f['q'],f['r'])],c)['risk'] for f in plan['candidates']],
        'combined_candidate_risk':E.assess([(f['q'],f['r']) for f in plan['candidates']],c)['risk']})
novelty=[]
for r in read('e3_raw_results.json'):
    c=contracts[r['asset']];before,_=E.history_facts([tuple(x) for x in r['prefix_visible']],c)
    if c['kind']=='affine':before.add(E.atom('family','affine'))
    if 'time_origin' in c:before.add(E.atom('time_origin',c['time_origin']))
    if c['kind']=='hotcold':before.add(E.atom('premise','hot_cold_distinct'))
    required={tuple(x) for x in r['required_atoms']};reply={tuple(x) for x in r['delivered_atoms']}
    novelty.append({'asset':r['asset'],'strategy':r['strategy'],
                    'new_required_task_atoms':len((required&reply)-before),
                    'partial_coverage_includes_public_or_previous_facts':bool(required&reply&before)})
save('utility_information_gain_audit.json',novelty)
save('single_union_risk_audit.json',single)
before=read('preservation_before.json')
assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in before.items())
assert before==read('preservation_after.json')
save('validation.json',{'status':'PASS_BOUNDED_CONTRACT_AUDIT','independent_backend':'SymPy '+S.__version__+' linsolve; same typed frontend, NOT independent semantic labels',
    'independent_backend_checks':solver_checks,'resource_checked_episodes':budget_checks,
    'same_input_matched_closure_diagnostics':len(read('matched_representation_checks.json')),
    'unknown_unscorable_plans_not_counted_as_attack_failures':True,
    'source_and_old_artifacts_preserved':len(before),'blind_test_assets':0,'human_annotators':0,
    'annotation_authors':1,'additional_model_calls':0,
    'limits':['no independent human semantic truth','no free-language completeness','no general adaptive/refusal-sidechannel guarantee',
              'no inference from low recovery of all-UNKNOWN/all-refusal current frontend']})
print(json.dumps(read('validation.json'),ensure_ascii=False))
