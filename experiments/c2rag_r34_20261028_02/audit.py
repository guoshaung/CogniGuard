"""Post-run independent method/structure audit; no changes to frozen definitions."""
from collections import Counter
from fractions import Fraction as F
import itertools
import json
import time
from experiments.c2rag_r34_20261028_02.common import *
from experiments.c2rag_r34_20261028_02.verify import parse, masks, union, tables

def canonical(obs,edges):
    signatures=[]
    for permutation in itertools.permutations(range(len(obs))):
        signatures.append(tuple(sorted(tuple(sorted(permutation[obs.index(o)] for o in edge)) for edge in edges)))
    return min(signatures)

def method_check(bank,truth,table,trace,packets):
    answers={a['id']:a for q in bank['queries'] for a in q['answers']};answers['EMPTY']={'reply':''}
    bits={i:parse(a['reply'],bank,truth) for i,a in answers.items()};cost={i:len(a['reply'].encode('utf8')) for i,a in answers.items()}
    bad_masks=[m for m in masks() if m not in bank['case']['assets'][0]['authorized']]
    menus=list(itertools.product(*[[a['id'] for a in q['answers']]+['EMPTY'] for q in bank['queries']]))
    state=[0]*4;checks=0
    def safe(v):return all(not table[union(v,m)]['recover'] for m in bad_masks)
    def add(v,who,a):w=v.copy();w[who]|=bits[a];return w
    def greedy(v,who,q):
        for a in [a['id'] for a in bank['queries'][q]['answers']]+['EMPTY']:
            w=add(v,who,a)
            if safe(w):return a,w
        raise AssertionError('Unsafe prefix in independent decision check')
    def universal(v,menu,recipients):
        # Reachability DP over slots rather than primary subset enumeration.
        for m in bad_masks:
            capacity=sum(bool(m&(1<<i)) for i in recipients);reach={union(v,m)}
            for _ in range(capacity):reach={b|bits[a] for b in reach for a in menu}
            if any(table[b]['recover'] for b in reach):return False
            if capacity==0 and table[union(v,m)]['recover']:return False
        return True
    def fixed():
        admissible=[]
        for menu in menus:
            v=[0]*4
            for a in menu:v[0]|=bits[a]
            if safe(v):admissible.append(menu)
        return min(admissible,key=lambda m:(-sum(a!='EMPTY' for a in m),sum(cost[a] for a in m),m))
    fixed_menu=fixed();name=trace['method'];comparisons=[]
    for t,e in enumerate(trace['steps']):
        if name=='M8-OPT':break
        recipients=[s['recipient'] for s in trace['steps'][t+1:]]
        if packets is None:scenarios=[[s['q'] for s in trace['steps'][t+1:]]]*32
        else:scenarios=packets[t]['scenarios']
        if name=='M0-NoGate':chosen=bank['queries'][e['q']]['answers'][0]['id']
        elif name=='M1-G-Shared' or e['recipient']==3:chosen,_=greedy(state,e['recipient'],e['q'])
        elif name=='M2-Fixed-Rules':chosen=fixed_menu[e['q']]
        elif 'Simple' in name:
            opts=[]
            for menu in menus:
                a=menu[e['q']];v=add(state,e['recipient'],a)
                if not safe(v) or not universal(v,menu,recipients):continue
                score=32*int(a!='EMPTY')
                for scenario in scenarios:
                    score+=sum(1 for r,q in zip(recipients,scenario) if r==3 or menu[q]!='EMPTY')
                opts.append(((-score,-int(a!='EMPTY'),cost[a],a,menu),a))
            chosen=min(opts)[1];checks+=len(opts)
        else:
            opts=[]
            for a in [x['id'] for x in bank['queries'][e['q']]['answers']]+['EMPTY']:
                child=add(state,e['recipient'],a)
                if not safe(child):continue
                score=32*int(a!='EMPTY')
                for scenario in scenarios:
                    sim=child
                    for r,q in zip(recipients,scenario):
                        action,sim=greedy(sim,r,q);score+=int(action!='EMPTY')
                opts.append(((-score,-int(a!='EMPTY'),cost[a],a),a))
            chosen=min(opts)[1];checks+=len(opts)
        assert chosen==e['answer_id'],(trace['stream'],name,t,chosen,e['answer_id'])
        state=add(state,e['recipient'],chosen);comparisons.append(t)
    # Independent best ACTUAL-future static menu, with no universal restriction.
    best=None
    for menu in menus:
        v=[0]*4;plan=[]
        for e in trace['steps']:
            a=bank['queries'][e['q']]['answers'][0]['id'] if e['recipient']==3 else menu[e['q']]
            v=add(v,e['recipient'],a);plan.append(a)
        if safe(v):
            key=(-sum(a!='EMPTY' for a in plan),sum(cost[a] for a in plan),tuple(plan))
            if best is None or key<best:best=key
    return {'decisions':len(comparisons),'candidate_scores':checks,'independent_static_utility':-best[0]}

def main():
    frozen();start=time.process_time();banks={b['id']:b for b in read('public/banks.json')};truths={t['id']:t for t in read('private/truth.json')}
    rows=read('evaluated_rows.json');proof=[];structure=[]
    for row in rows:
        bank=banks[row['asset']];truth=truths[row['asset']];name=row['method'];packet=None
        if name=='M3-Simple-Prior':condition='prior'
        elif 'Forecast' in name:condition=name.rsplit('-',1)[1]
        else:condition=None
        if condition:packet=read(f'forecasts/{row["stream"]}__{condition}.json')
        checked=method_check(bank,truth,tables(truth),read(row['trace']),packet)
        assert checked['independent_static_utility']==row['static_menu_oracle_utility']
        proof.append({'stream':row['stream'],'method':name,**checked})
    for asset,truth in truths.items():
        bank=banks[asset];obs=bank['observations'];incomparable=[]
        for q in bank['queries']:
            for a,b in itertools.combinations(q['answers'],2):
                A=truth['table'][parse(a['reply'],bank,truth)]['compatible_worlds'];B=truth['table'][parse(b['reply'],bank,truth)]['compatible_worlds']
                incomparable.append({'query':q['id'],'a':a['id'],'b':b['id'],'incomparable':not set(A)<=set(B) and not set(B)<=set(A),
                    'A_not_B_world':next((w for w in A if w not in B),None),'B_not_A_world':next((w for w in B if w not in A),None)})
        structure.append({'asset':asset,'family':bank['family'],'split':bank['split'],'subject':bank['subject'],
            'worlds':len(truth['worlds']),'observation_count':len(obs),'minimal_sets':truth['minimal_obs_sets'],
            'minimal_arity_histogram':dict(Counter(len(x) for x in truth['minimal_obs_sets'])),
            'hypergraph_signature':canonical(obs,truth['minimal_obs_sets']),'answer_incomparability':incomparable})
    iso=[]
    for a,b in itertools.combinations(structure,2):
        if a['observation_count']==b['observation_count'] and a['hypergraph_signature']==b['hypergraph_signature']:iso.append([a['asset'],b['asset']])
    # A genuine three-person prefix is stronger than a three-person action support
    # inside a later view that already has a one-person alternate recovery path.
    witnesses=read('minimal_witnesses.json');three=[];boundary=[]
    for row in rows:
        if row['method']!='M0-NoGate':continue
        bank=banks[row['asset']];trace=read(row['trace']);observed=read(f'observer/{row["stream"]}__{row["method"]}.json')
        for step in observed:
            sizes=[c['coalition'].bit_count() for c in step['coalitions'] if c['recover'] and not c['authorized']]
            if sizes and min(sizes)==3:three.append({'stream':row['stream'],'prefix_last_step':step['step'],'k_min_entire_prefix':3,
                'any_pair_insufficient':True,'coalition':next(c['coalition'] for c in step['coalitions'] if c['recover'] and not c['authorized'])})
        final=observed[-1];sizes=[c['coalition'].bit_count() for c in final['coalitions'] if c['recover'] and not c['authorized']]
        # Same observed bytes with all groups unentitled: policy effect, not a new stream.
        all_sizes=[c['coalition'].bit_count() for c in final['coalitions'] if c['recover']]
        boundary.append({'stream':row['stream'],'asset':row['asset'],'heterogeneous_k_min':min(sizes) if sizes else None,
            'all_unauthorized_k_min':min(all_sizes) if all_sizes else None,
            'safe_no_full_reconstruction':not bool(sizes),'cross_question_support_count':sum(w['cross_question'] for w in witnesses[row['stream']]),
            'support_k_counts':dict(Counter(w['k_min_for_this_support'] for w in witnesses[row['stream']]))})
    write('independent_planning_verification.json',{'complete':True,'decisions':sum(p['decisions'] for p in proof),
        'candidate_scores':sum(p['candidate_scores'] for p in proof),'same_choices':True,'rows':proof,'cpu_seconds':time.process_time()-start})
    write('structure_audit.json',{'assets':structure,'isomorphic_observation_hypergraphs':iso,'distinct_hypergraph_classes':len(structure)-len(iso),
        'three_person_entire_prefix_certificates':three,'boundary_controls':boundary})
    # Explicit broader-domain countermodels. These do NOT replace frozen domains.
    write('FINITE_DOMAIN_LIMITATIONS.json',[
        {'asset':'S02','frozen_domain_inference':['N','WA'],'nominal_observations':{'N':'115','WA':'96'},
         'continuous_positive_counterworld':{'F':'160','f':'45','d':'3/5','WA':'96','N':'115'},
         'consequence':'N and WA identify full tuple only inside frozen discrete domains; not a generally sound continuous-physics rule'},
        {'asset':'S03','frozen_domain_inference':['PV','PT'],'nominal_observations':{'PV':'8','PT':'1'},
         'continuous_positive_counterworld':{'P':'1','V':'8','T':'1','nR':'8'},
         'nominal_nR':'4','consequence':'extra finite-domain shortcut; does not hold for continuous positive gas states'}])
    assert F(160)-F(45)==115 and F(160)*F(3,5)==96
    assert F(1)*F(8)==8 and F(1)/F(1)==1 and F(1)*F(8)/F(1)!=4
    print('Independent method audit complete; isomorphic pairs:',iso,'3-person prefixes:',len(three))

if __name__=='__main__':main()
