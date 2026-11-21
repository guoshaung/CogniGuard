from fractions import Fraction as F
import itertools
import time
from experiments.c2rag_r35_20261029_01.common import *
from experiments.c2rag_r35_20261029_01.core import Backend

BASE_METHODS=[('NoGate','NoGate'),('Counter4','Budget'),('G-Shared','G')]
PRED_METHODS=[('A1','A1'),('A2','A2'),('Simple','Simple'),('B-SAA','B'),('MenuRecourse','MenuRecourse'),('B-Expectation','BDistribution'),('Causal-DP','DP')]

def main():
    frozen();start=time.perf_counter();write('execution_started.json',{'complete_runs_requested':1,'wall_budget_seconds':600})
    engine=module('engines');old=module('old_planner');packets={(p['asset'],p['law'],p['error'],tuple(p['prefix'])):p for p in read('forecast_packets.json')}
    policies=[];backends={};information=[]
    try:
        # Only generic prefixes and estimated distributions enter this phase.
        # Actual leaf evaluation and Offline-Oracle are constructed afterwards.
        for bank in read('banks.json'):
            public_bank={k:v for k,v in bank.items() if k!='evaluation_true_probabilities'}
            backend=Backend(public_bank,engine,old);backends[bank['id']]=backend;K=len(bank['queries'])
            for law in ['uniform','biased']:
                configs=[(m,k,'NA') for m,k in BASE_METHODS]+[(m,k,e) for e in ['0','1/2','1'] for m,k in PRED_METHODS]
                for method,kind,error in configs:
                    tree=[]
                    def walk(prefix,state):
                        packet=packets[bank['id'],law,error,prefix] if error!='NA' else None
                        began=time.perf_counter_ns();a,child,details=backend.choose(state,prefix,kind,packet)
                        ns=time.perf_counter_ns()-began
                        tree.append({'prefix':prefix,'recipient':RECIPIENTS[len(prefix)-1],'known_before':state,'answer_id':a,
                            'known_after':child,'reply':backend.g.answers[a]['reply'],'bytes':backend.g.cost[a],
                            'cpu_wall_ns':ns,'detail':details})
                        if len(prefix)<H:
                            for q in range(K):walk(prefix+(q,),child)
                    for q in range(K):walk((q,),(0,0,0,0))
                    path=f'policies/{bank["id"]}__{law}__{error.replace("/","_")}__{method}.json'
                    write(path,tree);policies.append({'asset':bank['id'],'law':law,'error':error,'method':method,'path':path})
                    deadline(start)
            print(bank['id'],'causal policies frozen before evaluation',flush=True)
        write('policy_index.json',policies)
        # True law used only below for evaluation/reference values.
        replays=[];oracles=[];leaves=read('test_leaves.json');banks={b['id']:b for b in read('banks.json')}
        for bank in banks.values():
            backend=backends[bank['id']];own=[s for s in leaves if s['asset']==bank['id']]
            for leaf in own:
                events=[{'q':q,'recipient':RECIPIENTS[t]} for t,q in enumerate(leaf['sequence'])]
                opt=old.optimize(backend.g,events);oracles.append({'leaf':leaf['id'],'asset':bank['id'],**opt})
            for law,ptext in bank['evaluation_true_probabilities'].items():
                p=tuple(F(x) for x in ptext);D=backend.dp(0,H,p);R=F(0)
                for q,pq in enumerate(p):
                    scores=[]
                    for a in backend.ids(q):
                        after=backend.g.bits[a]
                        if not backend.safe_joint(after):continue
                        score=F(a!='EMPTY')
                        for suffix in itertools.product(range(len(p)),repeat=H-1):
                            w=F(1)
                            for qt in suffix:w*=p[qt]
                            score+=w*backend.exact(after,suffix)
                        scores.append(score)
                    R+=pq*max(scores)
                information.append({'asset':bank['id'],'law':law,'B_exact_root_information_relaxation':str(R),
                    'optimal_causal_value':str(D),'information_relaxation_gap':str(R-D)})
            deadline(start)
        write('oracles.json',oracles);write('information_bounds.json',information)
        for config in policies:
            bank=banks[config['asset']];backend=backends[bank['id']];tree={tuple(x['prefix']):x for x in read(config['path'])}
            for leaf in leaves:
                if leaf['asset']!=bank['id']:continue
                weight=F(1);p=list(map(F,bank['evaluation_true_probabilities'][config['law']]))
                for q in leaf['sequence']:weight*=p[q]
                steps=[]
                for t,q in enumerate(leaf['sequence']):
                    row=tree[tuple(leaf['sequence'][:t+1])]
                    steps.append({'step':t,'query_id':q,'query':bank['queries'][q]['request'],'recipient':RECIPIENTS[t],
                        'asset_id':bank['id'],'answer_id':row['answer_id'],'reply':row['reply'],'bytes':row['bytes'],
                        'decision':'REFUSE' if row['answer_id']=='EMPTY' else 'ALLOW'})
                replays.append({k:config[k] for k in ['asset','law','error','method']}|{'leaf':leaf['id'],
                    'probability':str(weight),'correct':sum(s['answer_id']!='EMPTY' for s in steps),
                    'bytes':sum(s['bytes'] for s in steps),'steps':steps})
        write('replays.json',replays)
        for ident,b in backends.items():
            write(f'MILP/{ident}.json',{'stats':dict(b.stats),'solver_wall_seconds':b.wall_milp,'certificates':b.certificates,
                'cache_shared_across_methods':True,'timing_interpretation':'first users pay cold cache; no method speed ranking'})
        write('execution_completed.json',{'complete':True,'policy_configs':len(policies),'actual_replay_rows':len(replays),
            'unique_leaf_sequences':len(leaves),'wall_seconds':time.perf_counter()-start,
            'generation_model_calls':0,'paid_API_calls':0,'training':False,'stage3_integration':False})
        print('Complete',len(policies),'policies;',len(replays),'weighted replay rows',flush=True)
    except Exception as error:
        write('execution_failure.json',{'error':repr(error),'wall_seconds':time.perf_counter()-start,'partial_evidence_retained':True});raise

if __name__=='__main__':main()
