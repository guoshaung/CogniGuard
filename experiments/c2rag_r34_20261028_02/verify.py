"""Independent equations, text observer and Cartesian-product optimum.

No import of engines/planner/models in mathematical observer or OPT. The set
reference is only a third cross-check of the original detector's Horn encoding.
"""
from fractions import Fraction as F
import itertools
import json
import math
import time
from experiments.c2rag_r34_20261028_02.common import *

def independent_world(spec,values):
    w=dict(zip(spec['variables'],map(lambda x:F(str(x)),values)));i=spec['id']
    if i=='S01':w['stiffness']=w['force']*w['extension']**-1
    if i=='S02':
        w.update(force=w['applied_work']/w['distance'],friction=w['friction_loss']/w['distance'])
        w.update(net_force=(w['applied_work']-w['friction_loss'])/w['distance'],net_work=(w['force']-w['friction'])*w['distance'])
    if i=='S03':
        w.update(PV=w['volume']*w['pressure'],PT=w['pressure']*w['temperature']**-1,nR=w['pressure']/(w['temperature']/w['volume']))
    if i=='S04':
        w.update(initial_concentration=w['amount']*w['initial_volume']**-1,final_volume=sum([w['initial_volume'],w['added_volume']]))
        w['final_concentration']=w['amount']/(w['initial_volume']+w['added_volume'])
    if i=='S05':
        r,s=w['negative_root'],w['positive_root'];w.update(root_sum=r+s,root_product=r*s,discriminant=r*r-2*r*s+s*s,b=-r-s,c=r*s)
    if i=='S06':
        E,S,I=map(int,[w['enzyme'],w['substrate'],w['inhibitor']])
        w.update(ES=F(E*S),SI=F(S*(1-I)),reaction_on=F(E*S*(1-I)))
    return {k:str(v) for k,v in w.items()}

def tables(truth):
    spec=truth['spec'];ws=[independent_world(spec,v) for v in itertools.product(*spec['variables'].values())]
    assert ws==truth['worlds'];nom=truth['nominal'];obs=list(spec['observations']);result=[]
    for bits in range(1<<len(obs)):
        candidates=[]
        for w in ws:
            if all(not bits&(1<<j) or w[spec['observations'][o]]==nom[spec['observations'][o]] for j,o in enumerate(obs)):candidates.append(w)
        assert candidates
        fields=[f for f in spec['target'] if len({w[f] for w in candidates})==1]
        inputs=[f for f in spec['variables'] if len({w[f] for w in candidates})==1]
        recover=len(fields)==len(spec['target'])
        assert recover==truth['table'][bits]['recover']
        alt=truth['table'][bits]['alternative_world']
        if not recover:assert alt is not None and ws[alt] in candidates and any(ws[alt][f]!=nom[f] for f in spec['target'])
        result.append({'recover':recover,'fields':fields,'inputs':inputs,'remaining_worlds':len(candidates)})
    return result

def parse(reply,bank,truth):
    if not reply:return 0
    obj=json.loads(reply);bits=0
    for k,v in obj.items():
        assert k in bank['observations'] and set(v)=={'unit','value'}
        assert v['unit']==truth['spec']['units'][k]
        assert F(v['value'])==F(truth['nominal'][truth['spec']['observations'][k]])
        bits|=1<<bank['observations'].index(k)
    return bits

def masks(n=4,k=3):return [sum(1<<j for j in c) for size in range(1,k+1) for c in itertools.combinations(range(n),size)]
def union(views,mask):
    b=0
    for i,v in enumerate(views):
        if mask&(1<<i):b|=v
    return b

def independent_opt(bank,truth,table,events):
    t=time.process_time();answers={a['id']:a for q in bank['queries'] for a in q['answers']};answers['EMPTY']={'reply':''}
    bits={i:parse(a['reply'],bank,truth) for i,a in answers.items()};costs={i:len(a['reply'].encode('utf8')) for i,a in answers.items()}
    options=[[a['id'] for a in bank['queries'][e['q']]['answers']]+['EMPTY'] for e in events]
    bad_masks=[m for m in masks() if m not in bank['case']['assets'][0]['authorized']];best=None;total=0;safe=0
    for plan in itertools.product(*options):
        total+=1;views=[0]*4
        for e,a in zip(events,plan):views[e['recipient']]|=bits[a]
        if any(table[union(views,m)]['recover'] for m in bad_masks):continue
        safe+=1;key=(-sum(i!='EMPTY' for i in plan),sum(costs[i] for i in plan),plan)
        if best is None or key<best[0]:best=(key,plan)
    deadline(t,60)
    return {'complete':True,'all_legal_plans':total,'safe_plans':safe,'utility':-best[0][0],'bytes':best[0][1],
        'plan':list(best[1]),'cpu_seconds':time.process_time()-t}

def minimal_witnesses(trace,bank,truth,table):
    delivered=[s for s in trace['steps'] if s['reply']];ws=[]
    for k in [1,2,3]:
        for people in itertools.combinations(range(4),k):
            mask=sum(1<<i for i in people)
            if mask in bank['case']['assets'][0]['authorized']:continue
            relevant=[s for s in delivered if s['recipient'] in people]
            for size in range(1,len(relevant)+1):
                for items in itertools.combinations(relevant,size):
                    ids=[x['step'] for x in items]
                    if any(set(w['steps'])<=set(ids) for w in ws):continue
                    b=0
                    for x in items:b|=parse(x['reply'],bank,truth)
                    if not table[b]['recover']:continue
                    persons=sorted(set(x['recipient'] for x in items))
                    by_q={}
                    for x in items:by_q[x['q']]=by_q.get(x['q'],0)|parse(x['reply'],bank,truth)
                    cross=len(by_q)>1 and all(not table[bq]['recover'] for bq in by_q.values())
                    deletion=[]
                    for omit in items:
                        other=0
                        for x in items:
                            if x is not omit:other|=parse(x['reply'],bank,truth)
                        assert not table[other]['recover'];deletion.append({'removed_step':omit['step'],'remaining_bits':other,
                            'counterworld':truth['table'][other]['alternative_world']})
                    ws.append({'steps':ids,'recipients':persons,'k_min_for_this_support':len(persons),
                        'question_types':sorted(by_q),'cross_question':cross,'source':'direct' if size==1 else ('cross_question' if cross else 'same_question_combination'),
                        'observations':[o for j,o in enumerate(bank['observations']) if b&(1<<j)],'deletion_certificates':deletion,
                        'per_question_not_recovered':{str(q):not table[bq]['recover'] for q,bq in by_q.items()}})
    return ws

def main():
    frozen();start=time.process_time();write('verification_started.json',{'cpu_budget':1800})
    banks={b['id']:b for b in read('public/banks.json')};truths={t['id']:t for t in read('private/truth.json')}
    all_tables={i:tables(t) for i,t in truths.items()};reference=module('reference');rows=[];observer_count=0;witnesses={};opts=[]
    write('independent_mathematical_tables.json',all_tables)
    for row in read('run_index.json'):
        bank=banks[row['asset']];truth=truths[row['asset']];table=all_tables[row['asset']];trace=read(row['trace']);views=[0]*4;prefix=[]
        target_k={k:False for k in [1,2,3]};unauthed_k={k:False for k in [1,2,3]};first=None;direct=0;all_fields=set();all_inputs=set()
        for step in trace['steps']:
            bits=parse(step['reply'],bank,truth);views[step['recipient']]|=bits
            current_bad=False;details=[]
            sets=[{o for j,o in enumerate(bank['observations']) if v&(1<<j)} for v in views]
            for mask in masks():
                u=union(views,mask);value=table[u];k=mask.bit_count();target_k[k]|=value['recover']
                allowed=mask in bank['case']['assets'][0]['authorized'];bad=value['recover'] and not allowed
                unauthed_k[k]|=bad;current_bad|=bad
                if not allowed:all_fields.update(value['fields']);all_inputs.update(value['inputs'])
                closed=reference.closure(sets[0] if mask==1 else set().union(*(sets[i] for i in range(4) if mask&(1<<i))),bank['case']['rules'],bank['case']['public'])
                assert ('TARGET' in closed)==value['recover']
                observer_count+=1;details.append({'coalition':mask,'authorized':allowed,**value})
            if current_bad and first is None:first=step['step']
            if bits and table[bits]['recover'] and (1<<step['recipient']) not in bank['case']['assets'][0]['authorized']:direct+=1
            assert current_bad==step['controller_unsafe_after']
            prefix.append({'step':step['step'],'coalitions':details,'observer_unsafe':current_bad})
        if row['method']!='M0-NoGate':assert first is None
        assert sum(x['bytes'] for x in trace['steps'])==row['bytes']<=bank['budget_bytes']
        assert sum(x['correct'] for x in trace['steps'])==row['utility']
        write(f'observer/{row["stream"]}__{row["method"]}.json',prefix)
        rows.append({**row,'complete_unauthorized_target':int(first is not None),'first_recovery_step':first,
            'target_fields_recovered':len(all_fields),'target_field_denominator':len(truth['target_fields']),
            'input_fields_recovered':len(all_inputs),'input_field_denominator':len(truth['spec']['variables']),
            'direct_unauthorized_deliveries':direct,'unknown':0,
            **{f'unauthorized_exact_k{k}':int(v) for k,v in unauthed_k.items()},
            **{f'all_recovery_exact_k{k}':int(v) for k,v in target_k.items()}})
        if row['method']=='M0-NoGate':
            witnesses[row['stream']]=minimal_witnesses(trace,bank,truth,table)
        deadline(start,1800)
    for stream in read('events.json'):
        bank=banks[stream['asset']];ind=independent_opt(bank,truths[bank['id']],all_tables[bank['id']],stream['events']);primary=read(f'opt/{stream["id"]}.json')['opt']
        assert (ind['utility'],ind['bytes'],ind['plan'])==(primary['utility'],primary['bytes'],primary['plan'])
        opts.append({'stream':stream['id'],**ind});deadline(start,1800)
    # Controls check entitlement and public-source visibility, not new assets.
    controls=[]
    for bank in banks.values():
        for public in [False,True]:
            case=json.loads(json.dumps(bank['case']));case['assets'][0]['authorized']=masks()
            if public:case['public']=['TARGET']
            sets=[set(bank['observations']) for _ in range(4)]
            assert not reference.unsafe(case,sets)
            controls.append({'asset':bank['id'],'control':'source_instance_public_and_authorized' if public else 'fully_authorized',
                'false_alarm':False,'target_public_from_start':public})
    write('evaluated_rows.json',rows);write('minimal_witnesses.json',witnesses);write('opt_independent.json',opts);write('controls.json',controls)
    write('independent_verification.json',{'complete':True,'runs':len(rows),'coalition_prefix_checks':observer_count,
        'mathematical_subsets':sum(len(t) for t in all_tables.values()),'independent_OPTs':len(opts),'unknown':0,
        'non_NoGate_violations':0,'cpu_seconds':time.process_time()-start,
        'annotation':'single author + programmatically independent math/observer; not independent human ground truth'})
    print('Independently verified',len(rows),'runs;',len(opts),'OPT certificates')

if __name__=='__main__':main()
