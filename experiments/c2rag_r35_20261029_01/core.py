"""Adapters for old baselines and standard MILP/DP, never new risk mechanisms."""
from collections import Counter
from fractions import Fraction as F
from functools import lru_cache
import itertools
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from experiments.c2rag_r35_20261029_01.common import H, RECIPIENTS

class Backend:
    def __init__(self,bank,engine,old):
        self.bank=bank;self.g=old.Gate(bank,engine);self.old=old;self.certificates=[]
        self.obs=bank['observations'];self.supports=[self.g.c.bits(b) for b,h in bank['case']['rules'] if h=='TARGET']
        self.stats=Counter();self.wall_milp=0.
    def joint(self,state):return state[0]|state[1]|state[2]
    def safe_joint(self,b):return not self.g.close(b)&(1<<self.g.c.index['TARGET'])
    def ids(self,q):return [a['id'] for a in self.bank['queries'][q]['answers']]+['EMPTY']
    @lru_cache(None)
    def exact(self,known,sequence):
        """Standard binary MILP, complete future only inside hypothetical scenario."""
        if not sequence:return 0
        start=time.perf_counter();opts=[(t,a) for t,q in enumerate(sequence) for a in self.ids(q) if a!='EMPTY']
        nx=len(opts);nf=len(self.obs);size=nx+nf;c=np.zeros(size);c[:nx]=-1
        lower=np.zeros(size);upper=np.ones(size);rows=[];ub=[]
        for t in range(len(sequence)):
            row=np.zeros(size)
            for j,(step,a) in enumerate(opts):
                if step==t:row[j]=1
            rows.append(row);ub.append(1)
        for f,atom in enumerate(self.obs):
            mask=1<<self.g.c.index[atom]
            if known&mask:lower[nx+f]=1
            for j,(t,a) in enumerate(opts):
                if self.g.bits[a]&mask:
                    row=np.zeros(size);row[j]=1;row[nx+f]=-1;rows.append(row);ub.append(0)
        for support in self.supports:
            row=np.zeros(size)
            for f,atom in enumerate(self.obs):
                if support&(1<<self.g.c.index[atom]):row[nx+f]=1
            rows.append(row);ub.append(support.bit_count()-1)
        result=milp(c,integrality=np.ones(size),bounds=Bounds(lower,upper),
            constraints=LinearConstraint(np.asarray(rows),np.full(len(rows),-np.inf),np.asarray(ub)),
            options={'time_limit':2.,'mip_rel_gap':0.})
        self.wall_milp+=time.perf_counter()-start;self.stats['MILP_calls']+=1
        assert result.status==0 and result.success and result.x is not None,result.message
        assert np.max(np.abs(result.x-np.rint(result.x)))<1e-6
        plan=['EMPTY']*len(sequence)
        for j,(t,a) in enumerate(opts):
            if result.x[j]>.5:assert plan[t]=='EMPTY';plan[t]=a
        final=known
        for a in plan:final|=self.g.bits[a]
        value=sum(a!='EMPTY' for a in plan)
        assert self.safe_joint(final) and abs(value+result.fun)<1e-6
        self.certificates.append({'known_engine_bits':known,'sequence':sequence,'plan':plan,'value':value,
            'solver_status':int(result.status),'mip_gap':float(getattr(result,'mip_gap',0.)),'safe':True})
        return value
    @lru_cache(None)
    def menu(self,known,sequence):
        best=0
        for menu in self.g.menus:
            final=known;value=0
            for q in sequence:
                a=menu[q];final|=self.g.bits[a];value+=int(a!='EMPTY')
            if self.safe_joint(final):best=max(best,value)
        self.stats['menu_value_calls']+=1
        return best
    @lru_cache(None)
    def dp(self,known,remaining,probability):
        if not remaining:return F(0)
        total=F(0)
        for q,p in enumerate(probability):
            choices=[]
            for a in self.ids(q):
                after=known|self.g.bits[a]
                if self.safe_joint(after):choices.append(F(a!='EMPTY')+self.dp(after,remaining-1,probability))
            total+=p*max(choices)
        return total
    def choose(self,state,prefix,kind,packet):
        q=prefix[-1];t=len(prefix)-1;who=RECIPIENTS[t];future_recipients=RECIPIENTS[t+1:]
        scenarios=packet['scenarios'] if packet else [];known=self.joint(state);r=H-t-1
        if kind in ['NoGate','Budget']:
            a=self.ids(q)[0];child,_=self.g.trial(state,who,a);return a,child,{'counter_cap':H,'budget_binding':False}
        if kind in ['G','Simple','A2']:
            return self.old.choose(self.g,state,who,q,kind,scenarios,future_recipients)
        options=[];scores=[];probs=tuple(F(p) for p in packet['probability'])
        for a in self.ids(q):
            child,bad=self.g.trial(state,who,a)
            if bad:continue
            after=self.joint(child);u=int(a!='EMPTY')
            if kind=='A1':
                loss=0
                for seq in scenarios:
                    for qt in seq:
                        before=any(self.safe_joint(known|self.g.bits[b]) for b in self.ids(qt) if b!='EMPTY')
                        later=any(self.safe_joint(after|self.g.bits[b]) for b in self.ids(qt) if b!='EMPTY')
                        loss+=int(before and not later)
                score=F(32*u-loss,32)
            elif kind in ['B','MenuRecourse']:
                fn=self.exact if kind=='B' else self.menu
                score=F(u)+sum((F(count)*fn(after,seq) for seq,count in Counter(tuple(s) for s in scenarios).items()),F(0))/32
            elif kind=='DP':score=F(u)+self.dp(after,r,probs)
            elif kind=='BDistribution':
                score=F(u)
                for seq in itertools.product(range(len(probs)),repeat=r):
                    p=F(1)
                    for qt in seq:p*=probs[qt]
                    score+=p*self.exact(after,seq)
            else:raise ValueError(kind)
            key=(-score,-u,self.g.cost[a],a);options.append((key,a,child))
            scores.append({'id':a,'score_fraction':str(score)})
        _,a,child=min(options,key=lambda x:x[0])
        return a,child,{'kind':kind,'scores':scores}
