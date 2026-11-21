"""Decision functions receive current event/history/forecast only, never stream gold."""
from collections import Counter
import itertools
import time


class Gate:
    """Cached same exact <=3-coalition semantics, not a new risk function."""
    def __init__(self,bank,engine):
        self.bank=bank;self.case=bank['case'];self.c=engine.Compiled(self.case)
        self.answers={a['id']:a for q in bank['queries'] for a in q['answers']}
        self.bits={i:self.c.bits(a['facts']) for i,a in self.answers.items()}
        self.cost={i:len(a['reply'].encode('utf8')) for i,a in self.answers.items()}
        self.closures=[self.c.expand(b|self.c.public) for b in range(1<<len(self.c.atoms))]
        self.target_bits=sum(1<<self.c.index[a['target']] for a in self.case['assets'])
        assert all(not a['authorized'] for a in self.case['assets'])
        self.affected={i:[tuple(j for j in range(self.c.n) if m&(1<<j)) for m in self.c.affected[i]] for i in range(self.c.n)}
        self.cache={};self.calls=0;self.hits=0
        self.menus=list(itertools.product(*[[a['id'] for a in q['answers']] for q in bank['queries']]))
    def trial(self,state,who,aid):
        self.calls+=1;key=(state,who,aid)
        if key in self.cache:self.hits+=1;return self.cache[key]
        bits=self.bits[aid]
        child=state[:who]+(state[who]|bits,)+state[who+1:]
        unsafe=False
        for members in self.affected[who]:
            known=0
            for i in members:known|=child[i]
            if self.closures[known]&self.target_bits:unsafe=True;break
        result=(child,unsafe)
        if len(self.cache)<100000:self.cache[key]=result
        return result
    def greedy(self,state,who,q):
        for a in self.bank['queries'][q]['answers']:
            child,risk=self.trial(state,who,a['id'])
            if not risk:return a['id'],child
        raise AssertionError('EMPTY must always be feasible from safe state')


def tie(gate,aid,score):return (-score,-int(aid!='EMPTY'),gate.cost[aid],aid)


def choose(gate,state,who,q,kind,scenarios,used_bytes=0):
    before=state;trials=[]
    if kind=='G':
        aid,child=gate.greedy(state,who,q)
        return aid,child,[{'id':aid,'score_times32':32*int(aid!='EMPTY')}]
    remaining=7-who
    if kind=='Simple':
        counts=Counter(x for scenario in scenarios for x in scenario)
        options=[]
        for menu in gate.menus:
            aid=menu[q];child,risk=gate.trial(state,who,aid)
            if risk:continue
            safe=True
            # Any unsafe coalition uses <=3 fresh recipients; duplicate identical
            # views can be omitted. All distinct-type subsets up to horizon suffice.
            for size in range(1,min(3,remaining,len(menu))+1):
                for types in itertools.combinations(range(len(menu)),size):
                    sim=child
                    for offset,qt in enumerate(types):
                        sim,bad=gate.trial(sim,who+1+offset,menu[qt])
                        if bad:safe=False;break
                    if not safe:break
                if not safe:break
            if not safe:continue
            score=32*int(aid!='EMPTY')+sum(n*int(menu[qt]!='EMPTY') for qt,n in counts.items())
            options.append((tie(gate,aid,score)+(menu,),aid,child,menu,score))
        assert options
        options.sort(key=lambda x:x[0]);_,aid,child,menu,score=options[0]
        trials=[{'id':x[1],'menu':x[3],'score_times32':x[4]} for x in options]
    else:
        # Only base greedy rollout, never offline optimization per predicted world.
        multiplicities=Counter(tuple(s) for s in scenarios);options=[]
        for a in gate.bank['queries'][q]['answers']:
            aid=a['id'];child,risk=gate.trial(state,who,aid)
            if risk:trials.append({'id':aid,'unsafe':True});continue
            total=32*int(aid!='EMPTY');rollouts=[]
            for scenario,count in multiplicities.items():
                sim=child;value=0;selected=[];spent=used_bytes+gate.cost[aid]
                for offset,qt in enumerate(scenario):
                    action,sim=gate.greedy(sim,who+1+offset,qt)
                    value+=int(action!='EMPTY');selected.append(action)
                    spent+=gate.cost[action]
                    assert spent<=gate.bank['budget_bytes']
                total+=count*value
                rollouts.append({'scenario':list(scenario),'multiplicity':count,'utility':value,'actions':selected,'projected_total_bytes':spent})
            options.append((tie(gate,aid,total),aid,child,total))
            trials.append({'id':aid,'score_times32':total,'rollouts':rollouts})
        options.sort(key=lambda x:x[0]);_,aid,child,score=options[0]
    assert state==before
    return aid,child,trials
