"""Dispatcher owns real event feed; planners only get one event and permitted packet."""
import itertools
import json
import time
import traceback
from experiments.c2rag_imperfect_forecast_20261027_01.common import *
from experiments.c2rag_imperfect_forecast_20261027_01.planner import Gate,choose


def exact_opt(bank,events,gate):
    start=time.perf_counter();best=None;count=0;safe_count=0
    for plan in itertools.product(*[[a['id'] for a in bank['queries'][e['qid']]['answers']] for e in events]):
        count+=1;state=(0,)*8;safe=True
        for who,aid in enumerate(plan):
            state,bad=gate.trial(state,who,aid)
            if bad:safe=False;break
        if not safe:continue
        safe_count+=1;utility=sum(a!='EMPTY' for a in plan);cost=sum(gate.cost[a] for a in plan)
        key=(-utility,cost,plan)
        if best is None or key<best[0]:best=(key,plan)
    return {'utility':-best[0][0],'bytes':best[0][1],'plan':best[1],
            'enumerated':count,'safe_plans':safe_count,'complete':True,'wall_ms':1000*(time.perf_counter()-start)}


def run_method(stream,bank,engine,method,condition,packets,opt=None):
    gate=Gate(bank,engine);state=(0,)*8;actual=engine.METHODS['ExactK3'](gate.c)
    traces=[];spent=0;elapsed=0.0
    for t,event in enumerate(stream['requests']):
        deadline();qid=event['qid'];start=time.perf_counter();cpu=time.process_time();old_calls=gate.calls;old_hits=gate.hits
        if method=='OPT':
            aid=opt['plan'][t];child,bad=gate.trial(state,t,aid);assert not bad;trials=[];packet_hash=None
        else:
            if method=='A2-Oracle':
                scenarios=[[e['qid'] for e in stream['requests'][t+1:]] for _ in range(32)]
                kind='A2';packet_hash=sha(encoded(scenarios))
            elif method=='G-Shared':scenarios=[];kind='G';packet_hash=None
            else:
                packet=packets[t];assert packet['input']['step']==t
                scenarios=packet['scenarios'];packet_hash=packet['scenario_hash']
                kind='Simple' if method.startswith('Simple') else 'A2'
            aid,child,trials=choose(gate,state,t,qid,kind,scenarios,spent)
        wall=1000*(time.perf_counter()-start);cpu_ms=1000*(time.process_time()-cpu);elapsed+=wall
        answer=gate.answers[aid];real_next,risk,_=actual.trial({t:answer['facts']})
        assert not risk and all(real_next.state[m]==gate.closures[__import__('functools').reduce(int.__or__,(child[i] for i in range(8) if m&(1<<i)),0)] for m in real_next.coals)
        actual=real_next;state=child;spent+=gate.cost[aid];assert spent<=bank['budget_bytes']
        traces.append({'stream_id':stream['id'],'structure':stream['structure'],'family':stream['family'],
              'method':method,'condition':condition,'step':t,'asset_id':stream['id'],'recipient':t,'qid':qid,
              'query':bank['queries'][qid]['query'],'chosen_id':aid,'actual_reply':answer['reply'],
              'normal_utility':int(aid!='EMPTY'),'output_bytes':gate.cost[aid],'cumulative_bytes':spent,
              'persistent_views_encoded':state,'forecast_hash':packet_hash,
              'forecast_visible_input':None if method in ['G-Shared','OPT','A2-Oracle'] else packets[t]['input'],
              'candidate_trials':trials,'decision_wall_ms':wall,'decision_cpu_ms':cpu_ms,
              'safety_trial_calls':gate.calls-old_calls,'safety_cache_hits':gate.hits-old_hits})
    return {'stream_id':stream['id'],'structure':stream['structure'],'family':stream['family'],'method':method,'condition':condition,
            'utility':sum(s['normal_utility'] for s in traces),'refusals':sum(not s['normal_utility'] for s in traces),
            'output_bytes':spent,'decision_wall_ms':elapsed,'trace_steps':8},traces


def main():
    frozen();deadline();banks=read('public/banks.json');streams=read('events.json');engine=module('engines')
    # Future files prepared in an isolated process are hashed before any method runs.
    write('forecast_manifest.json',{p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in sorted((OUT/'forecasts').glob('*.json'))})
    configs=[('G-Shared','baseline'),('Simple-Prior','prior'),('A2-Prior','prior'),('A2-Oracle','oracle'),('OPT','oracle')]
    configs += [(method,condition) for condition in ['none','weak','strong','misleading'] for method in ['Simple-Forecast','A2-Forecast']]
    allrows=[]
    try:
        for stream in streams:
            deadline();sid=stream['id'];bank=banks[stream['structure']]
            optpath=OUT/f'opt/{sid}.json'
            if optpath.exists():opt=read(f'opt/{sid}.json')
            else:opt=exact_opt(bank,stream['requests'],Gate(bank,engine));write(f'opt/{sid}.json',opt)
            for method,condition in configs:
                name=f'{sid}__{method}__{condition}.json';dest=OUT/'traces'/name
                if dest.exists():
                    saved=read('traces/'+name);allrows.append(saved['summary']);continue
                packets=read(f'forecasts/{sid}__{condition}.json') if condition in ['prior','none','weak','strong','misleading'] else None
                summary,trace=run_method(stream,bank,engine,method,condition,packets,opt)
                write('traces/'+name,{'summary':summary,'steps':trace});allrows.append(summary)
            print('completed',sid,'G',allrows[-13]['utility'],'OPT',opt['utility'],flush=True)
        write('execution_summary.json',allrows)
    except Exception:
        # Monotonic-numbered failures, no overwriting completed traces.
        i=1
        while (OUT/f'failures/execution_{i:02d}.json').exists():i+=1
        write(f'failures/execution_{i:02d}.json',{'traceback':traceback.format_exc(),'completed_method_runs':len(allrows),
              'configuration_changed':False,'continue_unstarted_allowed':True})
        raise


if __name__=='__main__':main()
