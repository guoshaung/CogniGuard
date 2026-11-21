"""Independent Boolean worlds, exhaustive plans and causal Bellman references.

No imports of engines, old planner, core.Backend, or scipy.optimize.
"""
from collections import defaultdict
from fractions import Fraction as F
from functools import lru_cache
import itertools
import json
import time
from experiments.c2rag_r35_20261029_01.common import *

def observer_tables(bank):
    obs=bank['observations'];J=len(obs);possible=[]
    for assignment in itertools.product([False,True],repeat=J+1):
        values=dict(zip(obs+['TARGET'],assignment))
        if all(not all(values[a] for a in b) or values[h] for b,h in bank['case']['rules']):possible.append(values)
    rows=[]
    for bits in range(1<<J):
        remaining=[w for w in possible if all(not bits&(1<<j) or w[o] for j,o in enumerate(obs))]
        assert remaining
        recover=all(w['TARGET'] for w in remaining)
        rows.append({'recover':recover,'compatible_world_count':len(remaining),
            'countermodel':next((w for w in remaining if not w['TARGET']),None)})
    return rows

class Reference:
    def __init__(self,bank):
        self.bank=bank;self.table=observer_tables(bank);self.answers={a['id']:a for q in bank['queries'] for a in q['answers']}
        self.answers['EMPTY']={'reply':''};self.bits={k:self.parse(a['reply']) for k,a in self.answers.items()}
        self.cost={k:len(a['reply'].encode('utf8')) for k,a in self.answers.items()}
        self.menus=list(itertools.product(*[self.options(q) for q in range(len(bank['queries']))]))
    def parse(self,reply):
        if not reply:return 0
        x=json.loads(reply);assert set(x)=={'asset','positive'} and x['asset']==self.bank['id']
        assert all(a in self.bank['observations'] for a in x['positive']) and len(set(x['positive']))==len(x['positive'])
        return sum(1<<self.bank['observations'].index(a) for a in x['positive'])
    def from_engine(self,bits):
        names=sorted(self.bank['case']['facts']);return sum(1<<j for j,o in enumerate(self.bank['observations']) if bits&(1<<names.index(o)))
    def options(self,q):return [a['id'] for a in self.bank['queries'][q]['answers']]+['EMPTY']
    @lru_cache(None)
    def opt(self,known,sequence):
        best=None
        for plan in itertools.product(*(self.options(q) for q in sequence)):
            final=known
            for a in plan:final|=self.bits[a]
            if self.table[final]['recover']:continue
            key=(-sum(a!='EMPTY' for a in plan),sum(self.cost[a] for a in plan),plan)
            if best is None or key<best:best=key
        assert best is not None
        return (-best[0],best[1],list(best[2]))
    @lru_cache(None)
    def menu_value(self,known,sequence):
        best=0
        for menu in self.menus:
            final=known;u=0
            for q in sequence:final|=self.bits[menu[q]];u+=int(menu[q]!='EMPTY')
            if not self.table[final]['recover']:best=max(best,u)
        return best
    @lru_cache(None)
    def causal(self,known,remaining,probs):
        if remaining==0:return F(0)
        total=F(0)
        for q,p in enumerate(probs):
            values=[]
            for a in self.options(q):
                after=known|self.bits[a]
                if not self.table[after]['recover']:values.append(F(a!='EMPTY')+self.causal(after,remaining-1,probs))
            total+=p*max(values)
        return total

def coalitions():return [tuple(g) for k in [1,2,3] for g in itertools.combinations(range(3),k)]

def main():
    frozen();start=time.perf_counter();write('verification_started.json',{'wall_budget':600})
    banks={b['id']:b for b in read('banks.json')};refs={k:Reference(b) for k,b in banks.items()};oracle={x['leaf']:x for x in read('oracles.json')}
    matrices={k:r.table for k,r in refs.items()};write('independent_boolean_tables.json',matrices)
    num_ip=0
    for ident,r in refs.items():
        for certificate in read(f'MILP/{ident}.json')['certificates']:
            known=r.from_engine(certificate['known_engine_bits']);seq=tuple(certificate['sequence'])
            independent=r.opt(known,seq)[0];menu=r.menu_value(known,seq)
            assert independent==certificate['value']==menu,(ident,known,seq,independent,menu)
            num_ip+=1
    for leaf in read('test_leaves.json'):
        independent=refs[leaf['asset']].opt(0,tuple(leaf['sequence']));o=oracle[leaf['id']]
        assert independent==(o['utility'],o['bytes'],o['plan'])
    policy_index={(x['asset'],x['law'],x['error'],x['method']):x for x in read('policy_index.json')}
    trees={k:{tuple(v['prefix']):v for v in read(x['path'])} for k,x in policy_index.items()}
    packets={(p['asset'],p['law'],p['error'],tuple(p['prefix'])):p for p in read('forecast_packets.json')}
    paired_score_checks=0;sample_variation=[]
    # Every B current-candidate score checked against a separate static-menu/plan
    # enumerator, not just equality of selected actions.
    for key,tree in trees.items():
        ident,law,error,method=key;r=refs[ident]
        if method!='B-SAA':continue
        other=trees[ident,law,error,'MenuRecourse']
        for prefix,node in tree.items():
            assert node['answer_id']==other[prefix]['answer_id']
            assert node['known_before']==other[prefix]['known_before']
            a_scores=node['detail'].get('scores',[]);b_scores=other[prefix]['detail'].get('scores',[])
            assert a_scores==b_scores
            known=0
            for x in node['known_before'][:3]:known|=r.from_engine(x)
            scenarios=packets[ident,law,error,prefix]['scenarios']
            for item in a_scores:
                a=item['id'];after=known|r.bits[a]
                recomputed=F(a!='EMPTY')+sum((F(r.opt(after,tuple(s))[0]) for s in scenarios),F(0))/32
                assert recomputed==F(item['score_fraction']);paired_score_checks+=1
    totals=[];coalition_checks=0;nonanticipative={};risk_errors=0
    weighted=defaultdict(lambda:defaultdict(F))
    for trace in read('replays.json'):
        ident=trace['asset'];r=refs[ident];bank=banks[ident];views=[0]*3;prefix=[];complete=False;first=None;refusals=0;voluntary=0;by_k={1:False,2:False,3:False};spent=0;known_inputs=0
        key=(ident,trace['law'],trace['error'],trace['method']);tree=trees[key]
        for s in trace['steps']:
            prefix.append(s['query_id']);node=tree[tuple(prefix)]
            assert s['query']==bank['queries'][s['query_id']]['request'] and s['recipient']==RECIPIENTS[s['step']]
            assert s['answer_id'] in r.options(s['query_id']) and s['reply']==r.answers[s['answer_id']]['reply']
            before=views[0]|views[1]|views[2]
            assert tuple(r.from_engine(x) for x in node['known_before'][:3])==tuple(views)
            signature=(ident,trace['law'],trace['error'],trace['method'],tuple(prefix),tuple(views))
            if signature in nonanticipative:assert nonanticipative[signature]==s['answer_id']
            nonanticipative[signature]=s['answer_id']
            if not s['reply']:
                refusals+=1;voluntary+=int(any(not r.table[before|r.bits[a]]['recover'] for a in r.options(s['query_id']) if a!='EMPTY'))
            views[s['recipient']]|=r.parse(s['reply']);spent+=len(s['reply'].encode('utf8'))
            for g in coalitions():
                union_bits=0
                for who in g:union_bits|=views[who]
                recovered=r.table[union_bits]['recover'];by_k[len(g)]|=recovered;coalition_checks+=1
                if recovered:complete=True;first=s['step'] if first is None else first
            known_inputs=(views[0]|views[1]|views[2]).bit_count()
        assert spent==trace['bytes']<=bank['budget_bytes']
        if trace['method'] not in ['NoGate','Counter4']:assert not complete
        row={k:trace[k] for k in ['asset','law','error','method','leaf','probability','correct','bytes']}
        row.update(refusals=refusals,voluntary_safe_refusals=voluntary,full_reconstruction=int(complete),first_recovery=first,
            released_input_fraction=known_inputs/len(bank['observations']),unknown=0,offline_utility=oracle[trace['leaf']]['utility'],
            **{f'recovery_exact_k{k}':int(v) for k,v in by_k.items()})
        totals.append(row);p=F(trace['probability'])
        for metric in ['correct','bytes','refusals','voluntary_safe_refusals','full_reconstruction','offline_utility']:
            weighted[key][metric]+=p*F(row[metric])
        weighted[key]['weight']+=p
        deadline(start)
    summary=[]
    for key,values in weighted.items():
        assert values['weight']==1
        summary.append(dict(zip(['asset','law','error','method'],key))|{m:str(v) for m,v in values.items()})
    info=[]
    for bound in read('information_bounds.json'):
        r=refs[bound['asset']];probs=tuple(map(F,r.bank['evaluation_true_probabilities'][bound['law']]));D=r.causal(0,H,probs)
        assert D==F(bound['optimal_causal_value']);offline=F(0)
        for seq in itertools.product(range(len(probs)),repeat=H):
            p=F(1)
            for q in seq:p*=probs[q]
            offline+=p*r.opt(0,seq)[0]
        R=F(bound['B_exact_root_information_relaxation']);assert offline>=R>=D
        actual=weighted[bound['asset'],bound['law'],'0','B-Expectation']['correct']
        assert actual<=D and weighted[bound['asset'],bound['law'],'0','Causal-DP']['correct']==D
        for key,values in weighted.items():
            if key[:2]==(bound['asset'],bound['law']) and key[3] not in ['NoGate','Counter4']:assert values['correct']<=D
        info.append(bound|{'expected_offline_optimum':str(offline),'B_expectation_actual_causal_policy_utility':str(actual),
            'B_actual_regret_to_optimal_causal':str(D-actual)})
    for ident,r in refs.items():
        for length in range(1,H+1):
            for prefix in itertools.product(range(len(r.bank['queries'])),repeat=length):
                ps=[packets[ident,'uniform',e,prefix] for e in ['0','1/2','1']]
                assert all(p['scenarios']==ps[0]['scenarios'] and p['probability']==ps[0]['probability'] for p in ps)
    write('evaluated_replays.json',totals);write('weighted_summary.json',summary);write('verified_information_bounds.json',info)
    old=read('history_preservation_before.json');after={p:sha((PROJECT_ROOT/p).read_bytes()) for p in old};assert after==old;write('history_preservation_after.json',after)
    write('independent_verification.json',{'complete':True,'MILP_subproblems_certified':num_ip,'unique_offline_sequences_certified':len(oracle),
        'B_current_candidate_scores_checked':paired_score_checks,'replay_rows':len(totals),'coalition_prefix_checks':coalition_checks,
        'B_MenuRecourse_all_scores_and_actions_equal':True,'nonanticipativity_unique_contexts':len(nonanticipative),
        'boolean_subset_contracts':sum(len(t) for t in matrices.values()),'unknown':0,'non_baseline_violations':0,
        'history_files_unchanged':len(old),'wall_seconds':time.perf_counter()-start})
    print('Independent verification complete:',len(totals),'replays;',num_ip,'MILPs;',paired_score_checks,'B scores',flush=True)

if __name__=='__main__':main()
