"""Independent finite-contract checks; no new model or performance experiment."""
from pathlib import Path
from fractions import Fraction
import hashlib,importlib.util,json,itertools,inspect,re

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def sha(b):return hashlib.sha256(b).hexdigest()
spec=importlib.util.spec_from_file_location('experiment',P/'run_experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
proto=load('protocol.json');assert sha((P/'run_experiment.py').read_bytes())==proto['runner_sha256']
assert sha((P/'legacy_content_risk.py').read_bytes())==proto['legacy_sha256']
assert not 'source' in inspect.signature(e.detect).parameters
assert not 'world' in inspect.signature(e.detect).parameters
assert list(inspect.signature(e.ngram_coverage).parameters)==['output']
count=0
for a,b in itertools.product(range(-10,11),repeat=2):
    for xs in [(0,1),(1,0),(0,0)]:
        for end in [1,2]:
            pts=tuple((Fraction(x),Fraction(a*x+b)) for x in xs[:end])
            oracle={(aa,bb) for aa,bb in itertools.product(range(-10,11),repeat=2)
                    if all(aa*x+bb==y for x,y in pts)}
            assert set(e.rational_elimination(pts))==oracle
            count+=1
    for x in [0,1]:assert e.ngram_coverage(f'y={a*x+b}.')==0
rows=load('online_results.json')
assert len(rows)==44
for r in rows:
    n=1 if r['plan']=='single_identity' else 2
    assert sum(t['tokens'] for t in r['turns'])==r['actual_tokens']<=72
    assert all(t['tokens']<=24 for t in r['turns'])
    for agent in {t['agent'] for t in r['turns']}:
        assert sum(t['tokens'] for t in r['turns'] if t['agent']==agent)<=72/n
        assert sum(bool(t['delivered']) for t in r['turns'] if t['agent']==agent)*.5<=1/n
    assert r['additive_cost']==sum(bool(t['delivered']) for t in r['turns'])*.5<=1
    assert r['normal_accuracy']==sum(t['correct'] for t in r['turns'])/2
    assert r['policy_aware_worlds']>=1
    for t in r['turns']:
        if t['kind']=='teaching_substitute':
            assert t['correct'] is False
            assert t['candidate_decisions'][-1]['candidate_type']=='teaching_substitute'
            assert t['candidate_decisions'][-1]['predicted_risk']==0
            assert t['candidate_decisions'][-1]['decision']=='allow'
for s in ['distinct','repeat']:
    for plan in ['single_identity','identity_split']:
        z={r['method']:r for r in rows if r['scenario']==s and r['plan']==plan}
        for k in ['turns']:
            assert [(x['delivered'],x['token_ids']) for x in z['Arithmetic-Closure'][k]]==[(x['delivered'],x['token_ids']) for x in z['Conditional-Risk-Adapted'][k]]
old=ROOT/'experiments/relation_closure_20261019_01'
first=json.loads((old/'online_results.json').read_text(encoding='utf8'))
assert len(first)==len(rows)
for a,b in zip(first,rows):
    for k in ['scenario','plan','method','normal_accuracy','actual_tokens','complete_recovery','policy_aware_worlds']:
        assert a[k]==b[k]
    assert [t['delivered'] for t in a['turns']]==[t['delivered'] for t in b['turns']]
oldhash=load('preservation_before.json')
assert oldhash==load('preservation_after.json')
assert all(sha((ROOT/f).read_bytes())==h for f,h in oldhash.items())
doc=load('document_preparation/frozen_document_protocol.json')
for f,h in doc['frozen_file_hashes'].items():assert sha((P/'document_preparation'/f).read_bytes())==h
registry=load('document_preparation/source_registry.json')
dev=[x for x in registry['sources'] if x['split']=='development']
hold=[x for x in registry['sources'] if x['split']=='prospective_holdout']
for key in ['book','group']:
    assert not {x[key] for x in dev}&{x[key] for x in hold}
assert not {a for x in dev for a in x['authors']}&{a for x in hold for a in x['authors']}
assert all(load('document_preparation/qasc_readiness.json')['cached_files_verified'].values())
out={'status':'PASS_FINITE_CONTRACT_VALIDATION','exhaustive_exact_solver_reference_checks':count,
     'ngram_source_independent_candidate_checks':882,'online_episodes_resource_checked':44,
     'arithmetic_adapted_matched_conditions':4,'retained_attempt01_same_actual_outputs':True,
     'legacy_selected_files_unchanged':len(oldhash),'document_books_authors_declared_families_disjoint':True,
     'p2_evaluations':0,'new_independent_assets_in_validation':0,
     'not_proven':['natural language semantic completeness','unknown attacker prior safety',
                   'all possible adaptive query histories','out of affine-family relations','paper-level generalization']}
with (P/'validation.json').open('x',encoding='utf8',newline='\n') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(out,ensure_ascii=False))
