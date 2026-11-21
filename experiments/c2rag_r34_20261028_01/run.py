import json
import subprocess
import sys
import time
from experiments.c2rag_r34_20261028_01.common import *
from experiments.c2rag_r34_20261028_01.planner import Gate, choose, optimize, best_static_menu

def forecasts(stream,bank,condition):
    proc=subprocess.Popen([sys.executable,'-m','experiments.c2rag_r34_20261028_01.forecast_worker'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',cwd=PROJECT_ROOT)
    packets=[]
    for t in range(8):
        item={'stream_id':stream['id'],'condition':condition,'types':len(bank['queries']),
            'family':stream['family'],'hint':stream['hints'].get(condition),
            'prefix':[e['q'] for e in stream['events'][:t+1]],'step':t,'seed':seed(stream['id'],'scenarios',t)}
        proc.stdin.write(json.dumps(item)+'\n');proc.stdin.flush()
        line=proc.stdout.readline();assert line,proc.stderr.read()
        packet=json.loads(line);assert packet['input']==item;packets.append(packet)
    proc.stdin.close();stderr=proc.stderr.read();assert proc.wait(timeout=30)==0,stderr
    write(f'forecasts/{stream["id"]}__{condition}.json',packets)
    return packets

def execute(bank,stream,name,kind,packets,engine,opt=None):
    gate=Gate(bank,engine);state=(0,0,0,0);exact=engine.METHODS['ExactK3'](gate.c);steps=[]
    started=time.process_time()
    for t,event in enumerate(stream['events']):
        if opt is not None:
            aid=opt['plan'][t];child,bad=gate.trial(state,event['recipient'],aid);detail={'offline_opt':True}
        else:
            scenarios=packets[t]['scenarios'] if packets is not None else [[e['q'] for e in stream['events'][t+1:]]]*32
            before=time.process_time()
            aid,child,detail=choose(gate,state,event['recipient'],event['q'],kind,scenarios,
                [e['recipient'] for e in stream['events'][t+1:]])
            detail['decision_cpu_ms']=(time.process_time()-before)*1000
        candidate=gate.answers[aid]
        next_exact,bad,_=exact.trial({event['recipient']:candidate['facts']})
        assert bad==gate.risk(child)
        # Original ExactK3 vector versus cached per-recipient adaptation.
        for m,mem in gate.members.items():
            known=0
            for i in mem:known|=child[i]
            assert next_exact.vector()[str(m)]==gate.close(known)
        if kind!='NoGate':assert not bad
        exact=next_exact;state=child
        steps.append({**event,'query':bank['queries'][event['q']]['request'],'answer_id':aid,'reply':candidate['reply'],
            'bytes':gate.cost[aid],'correct':int(aid!='EMPTY'),'decision':'REFUSE' if aid=='EMPTY' else 'ALLOW',
            'controller_unsafe_after':bad,'detail':detail})
    return {'stream':stream['id'],'asset':bank['id'],'method':name,'split':bank['split'],'family':stream['family'],
        'utility':sum(x['correct'] for x in steps),'refusals':sum(not x['correct'] for x in steps),
        'bytes':sum(x['bytes'] for x in steps),'cpu_ms':(time.process_time()-started)*1000,'steps':steps}

def main():
    frozen();write('execution_started.json',{'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'main_runs':1})
    started=time.process_time();engine=module('engines');banks={b['id']:b for b in read('public/banks.json')};index=[]
    try:
        for stream in read('events.json'):
            first=time.process_time();bank=banks[stream['asset']]
            packets={c:forecasts(stream,bank,c) for c in ['prior','none','strong','misleading']}
            gate=Gate(bank,engine);t=time.process_time();opt=optimize(gate,stream['events']);opt['cpu_ms']=(time.process_time()-t)*1000
            static=best_static_menu(gate,stream['events']);write(f'opt/{stream["id"]}.json',{'opt':opt,'static_menu_oracle':static})
            specs=[('M0-NoGate','NoGate',None),('M1-G-Shared','G',None),('M2-Fixed-Rules','Fixed',None),
                ('M3-Simple-Prior','Simple',packets['prior'])]
            for c in ['none','strong','misleading']:
                specs.extend([(f'M4-Simple-Forecast-{c}','Simple',packets[c]),(f'M5-A2-Forecast-{c}','A2',packets[c])])
            specs.extend([('M6-Simple-Oracle','Simple',None),('M7-A2-Oracle','A2',None),('M8-OPT','OPT',None)])
            for name,kind,ps in specs:
                trace=execute(bank,stream,name,kind,ps,engine,opt if kind=='OPT' else None)
                path=f'traces/{stream["id"]}__{name}.json';write(path,trace)
                index.append({k:v for k,v in trace.items() if k!='steps'}|{'trace':path,'opt_utility':opt['utility'],
                    'static_menu_oracle_utility':static['utility']})
            deadline(first,60);deadline(started,1800)
            print(stream['id'],'complete',flush=True)
        write('run_index.json',index);write('execution_completed.json',{'complete':True,'runs':len(index),'cpu_seconds':time.process_time()-started,
            'model_calls':0,'paid_calls':0,'gpu_calls':0,'forecast_information_boundary':'prefix-only stdin, independent process, forbidden evidence-file selftest'})
    except Exception as error:
        write('execution_failure.json',{'error':repr(error),'retained_partial_runs':len(index),'cpu_seconds':time.process_time()-started});raise

if __name__=='__main__':main()
