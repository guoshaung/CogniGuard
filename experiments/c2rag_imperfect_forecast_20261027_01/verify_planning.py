"""Independently recompute every menu score and greedy-rollout score from sets."""
from collections import Counter
import itertools
from experiments.c2rag_imperfect_forecast_20261027_01.common import *
from experiments.c2rag_imperfect_forecast_20261027_01.verify import decode,groups


def main():
    deadline();banks=read('public/banks.json');streams=read('events.json');ref=module('reference')
    checks=Counter()
    for stream in streams:
        deadline();sid=stream['id'];bank=banks[stream['structure']];case=bank['case'];coalitions=groups(8)
        byid={a['id']:a for q in bank['queries'] for a in q['answers']};cost={a:len(x['reply'].encode('utf8')) for a,x in byid.items()}
        facts={a:decode(bank,stream['structure'],x['reply']) for a,x in byid.items()};ccache={};rcache={}
        def risk(views):
            key=tuple(frozenset(v) for v in views)
            if key in rcache:return rcache[key]
            bad=False
            for members in coalitions:
                known=frozenset().union(*(key[i] for i in members))
                if known not in ccache:ccache[known]=ref.closure(known,case['rules'],case['public'])
                if any(a['target'] in ccache[known] for a in case['assets']):bad=True;break
            rcache[key]=bad;checks['counterfactual_safe_checks']+=1;return bad
        def trial(views,who,aid):
            child=[v.copy() for v in views];child[who].update(facts[aid]);return child,risk(child)
        def greedy(views,who,q):
            for a in bank['queries'][q]['answers']:
                child,bad=trial(views,who,a['id'])
                if not bad:return a['id'],child
            raise AssertionError('safe empty missing')
        def tie(a,score):return (-score,-int(a!='EMPTY'),cost[a],a)
        menus=list(itertools.product(*[[a['id'] for a in q['answers']] for q in bank['queries']]))
        for f in sorted((OUT/'traces').glob(sid+'__*.json')):
            trace=__import__('json').loads(f.read_text(encoding='utf8'));s=trace['summary'];method=s['method'];condition=s['condition']
            if method=='OPT':continue
            packets=read(f'forecasts/{sid}__{condition}.json') if condition in ['prior','none','weak','strong','misleading'] else None
            views=[set() for _ in range(8)]
            for t,step in enumerate(trace['steps']):
                q=step['qid']
                if method=='G-Shared':
                    action,_=greedy(views,t,q);assert action==step['chosen_id']
                else:
                    scenes=[[e['qid'] for e in stream['requests'][t+1:]]]*32 if method=='A2-Oracle' else packets[t]['scenarios']
                    if method.startswith('Simple'):
                        counts=Counter(qt for sc in scenes for qt in sc);options=[]
                        for menu in menus:
                            action=menu[q];child,bad=trial(views,t,action)
                            if bad:continue
                            valid=True
                            for size in range(1,min(3,7-t,len(menu))+1):
                                for kinds in itertools.combinations(range(len(menu)),size):
                                    simulated=[v.copy() for v in child]
                                    for j,qt in enumerate(kinds):simulated[t+1+j].update(facts[menu[qt]])
                                    if risk(simulated):valid=False;break
                                if not valid:break
                            if valid:
                                score=32*int(action!='EMPTY')+sum(n*int(menu[qt]!='EMPTY') for qt,n in counts.items())
                                options.append((tie(action,score)+(menu,),action,menu,score))
                        options.sort();assert options[0][1]==step['chosen_id']
                        logged={(tuple(x['menu']),x['id'],x['score_times32']) for x in step['candidate_trials']}
                        assert logged=={(x[2],x[1],x[3]) for x in options}
                        checks['simple_decisions']+=1
                    else:
                        options=[];logged={x['id']:x for x in step['candidate_trials']}
                        for a in bank['queries'][q]['answers']:
                            aid=a['id'];child,bad=trial(views,t,aid)
                            if bad:assert logged[aid]['unsafe'];continue
                            score=32*int(aid!='EMPTY');expected=[]
                            for scenario,n in Counter(tuple(x) for x in scenes).items():
                                sim=[v.copy() for v in child];utility=0;selected=[]
                                for j,qt in enumerate(scenario):
                                    ac,sim=greedy(sim,t+1+j,qt);utility+=int(ac!='EMPTY');selected.append(ac)
                                score+=n*utility;expected.append((scenario,n,utility,tuple(selected)))
                            assert logged[aid]['score_times32']==score
                            actual=[(tuple(r['scenario']),r['multiplicity'],r['utility'],tuple(r['actions'])) for r in logged[aid]['rollouts']]
                            assert actual==expected
                            options.append((tie(aid,score),aid));checks['rollout_candidate_scores']+=1
                        options.sort();assert options[0][1]==step['chosen_id'];checks['A2_decisions']+=1
                views,_=trial(views,t,step['chosen_id'])
        print('planning verified',sid,flush=True)
    write('independent_planning_verification.json',{'all_scores_and_choices_match':True,'implementation':'independent set reconstruction, no engine/planner imports',**checks})
    print(dict(checks))


if __name__=='__main__':main()
