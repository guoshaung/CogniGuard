"""Independent post-run certificate/accounting checks; six bounded interface repeats."""
import collections
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from src.wire import digest

H=Path(__file__).resolve().parent
def write(p,x):
    if p.exists(): raise FileExistsError(p)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf8')

def verify_witness(x,w):
    # Independent certificate checker: provenance matrix + explicit deadline conditions.
    records={e['event_id']:e for e in x['events']}
    E=next((e for e in records.values() if e['event_type']=='effect_commit'),None)
    R=next((e for e in records.values() if e['event_type']=='revocation_published'),None)
    e,r,t,u=(w[k] for k in ['effect_present','revocation_present','effect_tick','revoke_tick'])
    if E and (not e or not E['local_time_interval'][0]<=t<=E['local_time_interval'][1]): return None
    if R and (not r or not R['local_time_interval'][0]<=u<=R['local_time_interval'][1]): return None
    if not E and (t not in x['window']['effect_ticks'] or x['completeness']['receiver'] and e): return None
    if not R and (u not in x['window']['revoke_ticks'] or x['completeness']['authority'] and r): return None
    times={k:v['local_time_interval'][0] for k,v in records.items()}
    if E: times[E['event_id']]=t
    if R: times[R['event_id']]=u
    for b in records.values():
        if any(times[a]>=times[b['event_id']] for a in b['causal_parent_ids']): return None
    for a in records.values():
        for b in records.values():
            if a['actor_id']==b['actor_id'] and a['local_seq']<b['local_seq'] and times[a['event_id']]>=times[b['event_id']]: return None
    graph=x['objects']; closure={k:set(v) for k,v in graph.items()}
    for _ in graph:
        closure={k:v|{p for n in v for p in closure.get(n,set())} for k,v in closure.items()}
    affect='profile.f' in closure.get(x['target']['object_id'],set())
    bad=False
    if affect:
        if x['policy']['mode']=='bounded' and not x['check']['query_available']:
            bad=x['check']['installed_revoked'] or not(x['check']['issued_tick']<=t<x['check']['issued_tick']+50)
        else: bad=bool(r and u<=t)
    if x['policy']['mode']=='grace' and t>=10000:
        bad=bad or not(t<15000 and x['target']['session_id']=='session-existing-01' and x['target']['operation'] in ('submit','receipt'))
    return bool(e and bad)

def main():
    allrows=[json.loads(s) for s in (H/'runs/initial/results.jsonl').read_text('utf8').splitlines()]
    if len(allrows)!=76 or not all(r['passed'] for r in allrows): raise AssertionError('INITIAL_NOT_ACCEPTED')
    checks=[]
    for r in allrows:
        x=json.loads((H/r['path']).read_text('utf8'))
        for name,out in r['methods'].items():
            values=[verify_witness(x,w) for w in out.get('witnesses',[])]
            expected={'VIOLATION_PROVEN':{True},'COMPLIANT_PROVEN':{False},'INDETERMINATE':{False,True},'EVIDENCE_INVALID':set()}[out['verdict']]
            checks.append({'input_id':r['input_id'],'method':name,'witness_count':len(values),'passed':set(values)==expected})
    write(H/'runs/certificate_checks.json',checks)
    # Freeze telemetry-only helper before exactly six additional method calls.
    write(H/'runs/telemetry_fix_freeze.json',{'files':{str(p.relative_to(H)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in [H/'src/worker_metered.py',Path(__file__)]},'method_changes':False,'new_independent_inputs':0,'max_worker_calls':6})
    selected=[next(r for r in allrows if r['scenario']==s and r['topology']=='centralized' and r['view']=='full' and r['paired']==p)
              for s,p in [('S8',False),('S10',False),('S6',True)]]
    repeats=[]
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    for idx,r in enumerate(selected):
        public=json.loads((H/r['path']).read_text('utf8'))
        if idx==1: public['events'].reverse()
        for name in ['B1','B2']:
            proc=subprocess.run([sys.executable,str(H/'src/worker_metered.py')],input=json.dumps({'method':name,'public':public}).encode(),
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=35,env=env)
            out=json.loads(proc.stdout)
            repeats.append({'input_id':r['input_id'],'method':name,'event_order_permuted':idx==1,'result':out,
                            'matches_original_verdict':out['verdict']==r['methods'][name]['verdict']})
    write(H/'runs/interface_rechecks.json',repeats)
    # S10 indistinguishability is checked on exact public bytes for both actual histories.
    twin=[]
    for topology in ['centralized','distributed']:
        pair=[r for r in allrows if r['scenario']=='S10' and r['topology']==topology and r['view']=='full']
        a,b=pair
        oa=json.loads((H/'oracle'/f"{a['input_id']}.json").read_text('utf8'))
        ob=json.loads((H/'oracle'/f"{b['input_id']}.json").read_text('utf8'))
        twin.append({'topology':topology,'input_a':a['path'],'input_b':b['path'],
                     'identical_public_bytes':(H/a['path']).read_bytes()==(H/b['path']).read_bytes(),
                     'opposite_actual_labels':oa['actual_history']['actual_action_violation']!=ob['actual_history']['actual_action_violation'],
                     'two_witnesses':a['oracle']['witnesses']})
    write(H/'counterexamples/indistinguishable_twins.json',twin)
    groups={}
    for r in allrows:
        x=json.loads((H/r['path']).read_text('utf8'))
        key='/'.join([x['policy']['mode'],r['topology'],r['view']])
        groups.setdefault(key,[]).append(r)
    metrics={'inputs':len(allrows),'execution_traces':len({r['trace_id'] for r in allrows}),
             'unique_public_bytes':len({hashlib.sha256((H/r['path']).read_bytes()).hexdigest() for r in allrows}),
             'by_group':{},'methods':{},'certificate_checks':{'passed':sum(c['passed'] for c in checks),'total':len(checks)},
             'interface_rechecks':{'passed':sum(r['matches_original_verdict'] and r['result']['oracle_access_probe_denied'] for r in repeats),'total':len(repeats)},
             'initial_rss':'UNAVAILABLE_API_SIGNATURE_DEFECT; zero is not observed zero memory',
             'metered_recheck_peak_rss_bytes':max(r['result']['peak_rss_bytes'] for r in repeats),
             'not_run':['B0_STATIC_ACL_OPTIONAL','FULL_PAPER_IMPLEMENTATIONS','NEW_PRODUCTION_INTERFACE_REPLAY'],
             'repair_rounds':1,'algorithm_verdict_repairs':0}
    for key,rows in groups.items():
        metrics['by_group'][key]={'n':len(rows),'labels':dict(collections.Counter(r['expected'] for r in rows)),
                                 'all_methods_correct':sum(r['passed'] for r in rows)}
    for name in ['B1','B2']:
        determinate=[r for r in allrows if r['expected'] in ('COMPLIANT_PROVEN','VIOLATION_PROVEN')]
        unknown=[r for r in allrows if r['expected']=='INDETERMINATE']
        invalid=[r for r in allrows if r['expected']=='EVIDENCE_INVALID']
        metrics['methods'][name]={'determinate_coverage':{'numerator':sum(r['methods'][name]['verdict']==r['expected'] for r in determinate),'denominator':len(determinate)},
             'necessary_refusal':{'numerator':sum(r['methods'][name]['verdict']=='INDETERMINATE' for r in unknown),'denominator':len(unknown)},
             'invalid_evidence':{'numerator':sum(r['methods'][name]['verdict']=='EVIDENCE_INVALID' for r in invalid),'denominator':len(invalid)},
             'false_violation':sum(r['methods'][name]['verdict']=='VIOLATION_PROVEN' and r['expected']!='VIOLATION_PROVEN' for r in allrows),
             'false_compliance':sum(r['methods'][name]['verdict']=='COMPLIANT_PROVEN' and r['expected']!='COMPLIANT_PROVEN' for r in allrows),
             'unnecessary_refusal':sum(r['methods'][name]['verdict']=='INDETERMINATE' and r['expected'] not in ('INDETERMINATE','EVIDENCE_INVALID') for r in allrows),
             'duty_exact_match':{'numerator':sum(r['checks'][name+'_duty_matches'] for r in allrows),'denominator':len(allrows)},
             'evidence_reference_valid':{'numerator':sum(r['checks'][name+'_references_valid'] for r in allrows),'denominator':len(allrows)},
             'max_solver_seconds':max(r['methods'][name].get('elapsed_seconds',0) for r in allrows),
             'max_nodes':max(r['methods'][name].get('nodes',0) for r in allrows)}
    write(H/'metrics.json',metrics)
    print(json.dumps({'certificates':metrics['certificate_checks'],'rechecks':metrics['interface_rechecks'],
                      'peak_rss_bytes':metrics['metered_recheck_peak_rss_bytes'],'unique_inputs':metrics['unique_public_bytes'],
                      'twins':twin},ensure_ascii=False))

if __name__=='__main__': main()
