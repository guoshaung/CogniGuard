"""Independent actual-text scoring and exhaustive set OPT; no planner/engine import."""
import ast
import csv
from fractions import Fraction as F
import itertools
import math
import re
import time
from experiments.c2rag_imperfect_forecast_20261027_01.common import *
from experiments.c2rag_cross_question_history_20261027_02.observer import decode as package_decode


def decode(bank,structure,text):
    if not text:return set()
    if structure=='kinetic':
        m=re.fullmatch(r'([mv]) = (\d+(?:/\d+)?) \[(kg|m/s)\]\.',text)
        if not m:raise ValueError('UNKNOWN kinetic reply')
        field,value,unit=m.groups();assert (field,unit) in [('m','kg'),('v','m/s')]
        return {f'kinetic::binding::{field}={F(value)}[{unit}]'}
    aliases={'F_net':'net_force','d_push':'distance','W_net':'net_work','W_push':'applied_work','loss_push':'friction_loss'}
    quantities=package_decode(text,'T06')
    return {aliases[x] for x in quantities}


def groups(n):return [tuple(c) for size in [1,2,3] for c in itertools.combinations(range(n),size)]


def main():
    frozen();deadline();banks=read('public/banks.json');streams=read('events.json');reference=module('reference')
    resultrows=[];checks=0;unknown=0;violations=0;opt_checks=[];scenario_checks=0
    # Source-level access boundary: decision module contains no file IO or gold imports.
    tree=ast.parse((SOURCE/'planner.py').read_text(encoding='utf8'))
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ['open','read','eval','exec','__import__'] for n in ast.walk(tree))
    assert 'source_gold' not in (SOURCE/'planner.py').read_text(encoding='utf8')
    for stream in streams:
        deadline();sid=stream['id'];bank=banks[stream['structure']];case=bank['case'];coalitions=groups(8);cache={}
        def closed(known):
            key=frozenset(known)
            if key not in cache:cache[key]=reference.closure(key,case['rules'],case['public'])
            return cache[key]
        def unsafe(views):
            for members in coalitions:
                cl=closed(set().union(*(views[i] for i in members)))
                if any(a['target'] in cl for a in case['assets']):return True
            return False
        target=case['assets'][0]['target']
        byid={a['id']:a for q in bank['queries'] for a in q['answers']}
        parsed={aid:decode(bank,stream['structure'],a['reply']) for aid,a in byid.items()}
        assert all(parsed[aid]==set(a['facts']) for aid,a in byid.items())
        start=time.perf_counter();best=None;safe_count=0;enum=0
        for plan in itertools.product(*[[a['id'] for a in bank['queries'][e['qid']]['answers']] for e in stream['requests']]):
            enum+=1;views=[parsed[aid] for aid in plan]
            if unsafe(views):continue
            safe_count+=1;key=(-sum(a!='EMPTY' for a in plan),sum(len(byid[a]['reply'].encode('utf8')) for a in plan),plan)
            if best is None or key<best:best=key
        primary=read(f'opt/{sid}.json');assert primary['complete'] and primary['enumerated']==enum and primary['safe_plans']==safe_count
        assert (-best[0],best[1],list(best[2]))==(primary['utility'],primary['bytes'],primary['plan'])
        opt_checks.append({'stream_id':sid,'enumerated':enum,'utility':-best[0],'safe_plans':safe_count,'complete':True,'wall_ms':1000*(time.perf_counter()-start)})
        traces=sorted((OUT/'traces').glob(sid+'__*.json'))
        assert len(traces)==13
        for path in traces:
            trace=json.loads(path.read_text(encoding='utf8'));steps=trace['steps'];summary=trace['summary'];views=[set() for _ in range(8)]
            score=0;cost=0;method_violations=0
            for i,s in enumerate(steps):
                assert s['recipient']==i and s['qid']==stream['requests'][i]['qid'] and s['asset_id']==sid
                valid={a['id']:a for a in bank['queries'][s['qid']]['answers']}
                assert s['chosen_id'] in valid and s['actual_reply']==valid[s['chosen_id']]['reply']
                views[i].update(decode(bank,stream['structure'],s['actual_reply']))
                if unsafe(views):violations+=1;method_violations+=1
                cost+=len(s['actual_reply'].encode('utf8'));score+=int(bool(s['actual_reply']));checks+=len(coalitions)
                assert cost==s['cumulative_bytes'] and cost<=bank['budget_bytes']
                assert all(len(views[j])==0 for j in range(i+1,8))
                if s['method'] not in ['G-Shared','OPT','A2-Oracle']:
                    packet=read(f'forecasts/{sid}__{s["condition"]}.json')[i]
                    assert s['forecast_hash']==packet['scenario_hash']==sha(encoded(packet['scenarios']))
                    assert s['forecast_visible_input']==packet['input']
                    if s['condition']=='prior':assert packet['input']['prefix']==[] and packet['input']['hint'] is None
                    else:assert packet['input']['prefix']==[e['qid'] for e in stream['requests'][:i+1]]
                    scenario_checks+=1
                elif s['method']=='A2-Oracle':
                    assert s['forecast_hash']==sha(encoded([[e['qid'] for e in stream['requests'][i+1:]]]*32))
            assert score==summary['utility'] and cost==summary['output_bytes']
            resultrows.append(summary|{'violations':method_violations,'unknown':0,'OPT':primary['utility'],'gap_OPT':primary['utility']-score})
        print('verified',sid,'plans',enum,flush=True)
    # No condition differences or hidden learning in the known uniform generator.
    uniform_same=True
    for s in streams:
        if s['family']!='uniform':continue
        packets=[read(f'forecasts/{s["id"]}__{c}.json') for c in ['prior','none','weak','strong','misleading']]
        assert all([x['scenarios'] for x in p]==[x['scenarios'] for x in packets[0]] for p in packets[1:])
    # Historical regression only: reconstruct actual existing Shared/Reset deliveries,
    # not a newly invented production vulnerability or a gain workload.
    hi=read('regression/instance.json');hr=read('regression/replay.json');regression={}
    for method in ['Shared','Reset']:
        views=[set() for _ in range(4)];badsteps=[]
        for s in [x for x in hr if x['method']==method]:
            views[s['recipient']].update(package_decode(s['actual_reply'],s['task_id']))
            if reference.unsafe(hi,views):badsteps.append(s['step'])
        regression[method]=badsteps
    assert regression=={'Shared':[],'Reset':[13,14,15,16]}
    write('verified_rows.json',resultrows);write('independent_opt.json',opt_checks)
    write('independent_verification.json',{'completed_streams':len(streams),'method_runs':len(resultrows),
       'coalition_prefix_checks':checks,'violating_steps':violations,'unknown':unknown,
       'scenario_hash_and_visibility_checks':scenario_checks,'uniform_forecast_conditions_identical':uniform_same,
       'exact_OPT_all_certified':True,'historical_scope_regression':regression,'planner_no_file_or_gold_access':True,
       'scorer_imports_engine_or_planner':False})
    assert violations==0


if __name__=='__main__':main()
