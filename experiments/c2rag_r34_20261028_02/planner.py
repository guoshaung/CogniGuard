"""Existing G, fixed-menu Simple and one-step greedy-rollout A2, not new algorithms."""
import itertools
from collections import Counter

class Gate:
    def __init__(self, bank, engine):
        self.bank=bank;self.c=engine.Compiled(bank['case']);self.calls=0;self.cache={}
        self.answers={a['id']:a for q in bank['queries'] for a in q['answers']}
        self.answers['EMPTY']={'id':'EMPTY','facts':[],'reply':'','correct':False}
        self.bits={k:self.c.bits(a['facts']) for k,a in self.answers.items()}
        self.cost={k:len(a['reply'].encode('utf8')) for k,a in self.answers.items()}
        self.menus=list(itertools.product(*[[a['id'] for a in q['answers']]+['EMPTY'] for q in bank['queries']]))
        self.closures={}
        self.members={m:tuple(i for i in range(4) if m&(1<<i)) for m in self.c.coals}
        self.fixed=self.fixed_menu()
    def close(self,b):
        if b not in self.closures:self.closures[b]=self.c.expand(b|self.c.public)
        return self.closures[b]
    def risk(self,state):
        for m, members in self.members.items():
            b=0
            for i in members:b|=state[i]
            if self.close(b)&self.c.risk_masks[m]:return True
        return False
    def trial(self,state,who,aid):
        self.calls+=1;key=(state,who,aid)
        if key not in self.cache:
            child=state[:who]+(state[who]|self.bits[aid],)+state[who+1:]
            self.cache[key]=(child,self.risk(child))
        return self.cache[key]
    def greedy(self,state,who,q):
        for a in [a['id'] for a in self.bank['queries'][q]['answers']]+['EMPTY']:
            child,bad=self.trial(state,who,a)
            if not bad:return a,child
        raise AssertionError('No feasible EMPTY: public contract initially unsafe')
    def menu_safe(self,state,menu,future_recipients):
        # Exact universal compatibility of a global type menu under this remaining
        # recipient schedule. Each future slot may have ANY query type. Coalition
        # authorization depends on its mask; no fresh/symmetric-person assumption.
        opts=sorted(set(self.bits[a] for a in menu)-{0})
        unions={0:0}
        for size in range(1,len(opts)+1):
            for subset in itertools.combinations(opts,size):
                b=0
                for x in subset:b|=x
                unions[b]=min(unions.get(b,99),size)
        counts=Counter(future_recipients)
        for mask, members in self.members.items():
            if not self.c.risk_masks[mask]:continue
            capacity=sum(counts[i] for i in members);known=0
            for i in members:known|=state[i]
            for b,need in unions.items():
                if need<=capacity and self.close(known|b)&self.c.risk_masks[mask]:return False
        return True
    def fixed_menu(self):
        good=[m for m in self.menus if self.menu_safe((0,0,0,0),m,[0,1,2]*len(self.bank['queries']))]
        return min(good,key=lambda m:(-sum(a!='EMPTY' for a in m),sum(self.cost[a] for a in m),m))

def tie(gate,aid,score):return (-score,-int(aid!='EMPTY'),gate.cost[aid],aid)

def choose(gate,state,who,q,kind,scenarios,future_recipients):
    trusted=gate.bank['trusted_recipient']
    if kind=='NoGate':
        a=gate.bank['queries'][q]['answers'][0]['id'];child,_=gate.trial(state,who,a)
        return a,child,{'kind':kind}
    if kind=='G' or who==trusted:
        a,child=gate.greedy(state,who,q);return a,child,{'kind':kind,'trusted_free':who==trusted}
    if kind=='Fixed':
        a=gate.fixed[q];child,bad=gate.trial(state,who,a)
        if bad:a='EMPTY';child=state
        return a,child,{'menu':gate.fixed}
    scores=[];options=[]
    if kind=='Simple':
        for menu in gate.menus:
            a=menu[q];child,bad=gate.trial(state,who,a)
            if bad or not gate.menu_safe(child,menu,future_recipients):continue
            value=len(scenarios)*int(a!='EMPTY')+sum(
                int(rec==trusted or menu[qt]!='EMPTY')
                for seq in scenarios for rec,qt in zip(future_recipients,seq))
            key=tie(gate,a,value)+(menu,)
            options.append((key,a,child));scores.append({'aid':a,'menu':menu,'score':value})
    elif kind=='A2':
        for a in [x['id'] for x in gate.bank['queries'][q]['answers']]+['EMPTY']:
            child,bad=gate.trial(state,who,a)
            if bad:continue
            value=len(scenarios)*int(a!='EMPTY');roll=[]
            for seq,count in Counter(tuple(x) for x in scenarios).items():
                sim=child;u=0;actions=[]
                for rec,qt in zip(future_recipients,seq):
                    action,sim=gate.greedy(sim,rec,qt);u+=int(action!='EMPTY');actions.append(action)
                value+=count*u;roll.append({'sequence':seq,'count':count,'utility':u,'actions':actions})
            options.append((tie(gate,a,value),a,child));scores.append({'aid':a,'score':value,'rollouts':roll})
    else:raise ValueError(kind)
    assert options
    _,a,child=min(options,key=lambda x:x[0])
    return a,child,{'kind':kind,'options':scores}

def optimize(gate,events):
    # Primary complete prefix DFS: prune only prefixes already unsafe. Safety is
    # monotone in delivered information under frozen monotone group entitlement.
    best=None;visited=0;leaves=0
    def dfs(t,state,plan,u,cost):
        nonlocal best,visited,leaves
        visited+=1
        if t==len(events):
            leaves+=1;key=(-u,cost,tuple(plan))
            if best is None or key<best[0]:best=(key,plan.copy())
            return
        event=events[t]
        for a in [x['id'] for x in gate.bank['queries'][event['q']]['answers']]+['EMPTY']:
            child,bad=gate.trial(state,event['recipient'],a)
            if not bad:dfs(t+1,child,plan+[a],u+int(a!='EMPTY'),cost+gate.cost[a])
    dfs(0,(0,0,0,0),[],0,0)
    return {'utility':-best[0][0],'bytes':best[0][1],'plan':best[1],'visited_nodes':visited,'safe_leaves':leaves,'complete':True}

def best_static_menu(gate,events):
    best=None
    for menu in gate.menus:
        state=(0,0,0,0);plan=[];valid=True
        for event in events:
            if event['recipient']==gate.bank['trusted_recipient']:a,child=gate.greedy(state,event['recipient'],event['q'])
            else:a=menu[event['q']];child,bad=gate.trial(state,event['recipient'],a);valid=valid and not bad
            state=child;plan.append(a)
            if not valid:break
        if valid:
            key=(-sum(a!='EMPTY' for a in plan),sum(gate.cost[a] for a in plan),tuple(plan))
            if best is None or key<best[0]:best=(key,menu,plan)
    return {'utility':-best[0][0],'bytes':best[0][1],'menu':best[1],'plan':best[2]}
