"""Freeze synthetic adaptation cases before any baseline results are inspected."""
import copy
import hashlib
import json
from pathlib import Path
from src.wire import digest

H=Path(__file__).resolve().parent
ROOT=H.parents[1]
V='VIOLATION_PROVEN'; C='COMPLIANT_PROVEN'; U='INDETERMINATE'; I='EVIDENCE_INVALID'

def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists(): raise FileExistsError(p)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf8')

def build(number, topology, paired):
    # Expected labels are hand specified independently of all three engines.
    full={1:C,2:C,3:V,4:C,5:C,6:V,7:V,8:V,9:U,10:U,11:I,12:C}[number]
    limited={1:C,2:C,3:U,4:U,5:C,6:U,7:U,8:U,9:U,10:U,11:I,12:C}[number]
    if paired:
        full={5:V,6:C,7:C,9:C,10:U,11:I,12:V}[number]
        limited={5:U,6:U,7:C,9:U,10:U,11:I,12:U}[number]
    identity=f'{number}/{topology}/{paired}'
    key=hashlib.sha256(identity.encode()).hexdigest()[:16]
    executor='node-C' if topology=='distributed' else 'service'
    obj='derived2' if number==7 else 'raw'
    x={'protocol':'CG-C-FINITE-01','target':{'action_id':'action-'+key,'object_id':obj,
        'executor_id':executor,'session_id':'session-existing-01','operation':'send'},
       'policy':{'rule_id':'R_ACTION','mode':'strict','delta':50,'expiry':10000,'hard_deadline':15000,
                 'preauthorized_session':'session-existing-01','profile_ancestor_restriction':True},
       'objects':{'raw':['profile.f'],'derived1':['raw'],'derived2':['derived1'],'profile.f':[],'profile.g':[]},
       'check':{'query_available':True,'query_used':True,'issued_tick':0,'installed_revoked':False,'rollback_accepted':False},
       'window':{'effect_ticks':[20],'revoke_ticks':[10]},'completeness':{'receiver':True,'authority':True},
       'evidence_assurance':'TRUSTED_SYNTHETIC_FIXTURE; SHA256 detects fixture edits, NOT adversarial authentication',
       'dependency_acquisition':'explicit_fixture_graph','events':[]}
    E=True; R=number not in (1,); t=20; r=10; install=False
    if number==2: r=30
    if number==3: install=True; x['check']['query_used']=False
    if number==4: E=False
    if number==5:
        x['policy']['mode']='bounded'; x['check']['query_available']=False
        x['check']['query_used']=False; t=50 if paired else 49
    if number==6:
        install=True; x['check']['rollback_accepted']=not paired
        x['check']['installed_revoked']=True; E=not paired
    if number==7 and paired: x['objects']['raw']=['profile.g']
    if number==8: t=11; r=10
    if number==9:
        E=False; x['completeness']['receiver']=bool(paired)
    if number==10:
        r=12 if paired else 10; t=11
    if number==12:
        x['policy']['mode']='grace'; x['target']['operation']='submit'; t=12000
        x['objects']['raw']=['profile.f' if paired else 'profile.g']
    x['window']['effect_ticks']=[t]; x['window']['revoke_ticks']=[r]
    seq={}; ids={}
    def event(kind,actor,tick,payload=None,parents=()):
        seq[actor]=seq.get(actor,0)+1
        eid=hashlib.sha256((key+'/'+kind+'/'+actor+'/'+str(seq[actor])).encode()).hexdigest()[:20]
        e={'event_id':eid,'actor_id':actor,'local_seq':seq[actor],'event_type':kind,
           'task_id':'task-'+key,'session_id':x['target']['session_id'],'object_id':obj,
           'dependency_ids':x['objects'].get(obj,[]),'policy_id':'policy-profile','policy_version':1,
           'action_id':x['target']['action_id'],'causal_parent_ids':list(parents),
           'local_time_interval':[tick,tick],'receipt_id':None,'payload':payload or {}}
        if kind in ('revocation_published','policy_install'): e['policy_version']=2
        if kind=='effect_commit': e['receipt_id']='effect-receipt-'+key
        e['fixture_digest']=digest(e)
        x['events'].append(e); ids[kind]=eid
        return eid
    create=event('object_created','node-A' if topology=='distributed' else 'service',-3,{'operation':'explicit_copy'})
    if topology=='distributed':
        hand=event('handoff_received','node-B',-2,parents=[create])
    else:
        hand=create
    event('policy_snapshot','authority',-1,{'allow_f':True})
    if R: event('revocation_published','authority',r,{'revoked_field':'profile.f'})
    if install: event('policy_install',executor,12,{'version':2})
    check=event('authorization_check',executor,15 if t>15 else 8,
                copy.deepcopy(x['check']),parents=[hand])
    event('send_attempt',executor,16 if t>16 else 9,{'effect_not_implied':True},parents=[check])
    if E: event('effect_commit','receiver',t,{'immutable_effect':True},parents=[ids['send_attempt']])
    if number==6 and paired:
        # Accepted duplicate bytes should be idempotent; ignored old version cannot lower installed state.
        x['events'].append(copy.deepcopy(x['events'][0]))
    if number==11:
        if paired:
            x['events'][0]['payload']['operation']='altered_without_digest'
        else:
            event('policy_snapshot','conflicting-authority-channel',-1,{'allow_f':False})
    # Arrival order is intentionally reversed; neither file order nor IDs are a clock.
    x['events'].reverse()
    actual={'effect_present':E if number!=9 or paired else True,'revocation_present':R,
            'effect_tick':t,'revoke_tick':r,
            'actual_action_violation': bool(number in (3,6,7,8,9) and not paired or number in (5,12) and paired or number==10 and not paired)}
    if number==10:
        # Full contracted evidence still has overlapping clocks: two opposite histories, identical bytes.
        for e in x['events']:
            if e['event_type']=='revocation_published': e['local_time_interval']=[10,12]
        x['window']['revoke_ticks']=[10,11,12]
    if number in (3,8):
        actual['node_duty_breaches']=['D_RECHECK'] if number==3 else []
    elif number==6 and not paired:
        actual['node_duty_breaches']=['D_VERSION_MONOTONE']
    else: actual['node_duty_breaches']=[]
    # Restore hashes following intentional interval uncertainty, but not the tamper fixture.
    if not (number==11 and paired):
        for e in x['events']: e['fixture_digest']=digest({k:v for k,v in e.items() if k!='fixture_digest'})
    # Avoid ID leakage in S10 observational twin: common public identifiers are intentional.
    if number==10 and paired:
        base,_,_,_=build(10,topology,False)
        x=base
    restricted=copy.deepcopy(x)
    restricted['events']=[e for e in restricted['events'] if e['event_type']!='effect_commit']
    restricted['completeness']['receiver']=False
    if number==8:
        for e in restricted['events']:
            if e['event_type']=='revocation_published':
                e['local_time_interval']=[10,12]
                e['fixture_digest']=digest({k:v for k,v in e.items() if k!='fixture_digest'})
    return x,restricted,{'full':full,'restricted':limited},actual

def main():
    if (H/'cases.jsonl').exists(): raise FileExistsError('already prepared')
    rows=[]; index=0
    paired={5,6,7,9,10,11,12}
    for number in range(1,13):
        for topology in ['centralized','distributed']:
            for pair in ([False,True] if number in paired else [False]):
                index+=1; public,limited,expected,actual=build(number,topology,pair)
                trace_id=f'T{index:03}'
                phase='admission' if number in (1,2,3,4,8,10) and not pair else 'extension'
                for view,x in [('full',public),('restricted',limited)]:
                    aid=hashlib.sha256(f'{trace_id}/{view}'.encode()).hexdigest()[:24]
                    save(H/'audit_inputs'/f'{aid}.json',x)
                    save(H/'oracle'/f'{aid}.json',{'actual_history':actual,'expected_verdict':expected[view],
                         'expected_duties':actual['node_duty_breaches'] if view=='full' else (['D_VERSION_MONOTONE'] if number==6 and not pair else []),
                         'scenario':f'S{number}','topology':topology,'trace_id':trace_id,'view':view,'phase':phase})
                    rows.append({'input_id':aid,'path':f'audit_inputs/{aid}.json','trace_id':trace_id,
                                 'scenario':f'S{number}','topology':topology,'paired':pair,'view':view,'phase':phase,
                                 'historical_anchor':{'S1':'P1','S2':'P4','S3':'P2','S4':'V4','S8':'P3','S10':'P3'}.get(f'S{number}')})
    (H/'cases.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),'utf8')
    save(H/'STATE.json',{'stage':'PREPARED_NOT_RUN','traces':index,'audit_inputs':len(rows),'GPU':0,'LLM':0,
         'paid_API':0,'formal_runs':0,'repairs':0})
    print(json.dumps({'traces':index,'audit_inputs':len(rows),'admission_inputs':sum(r['phase']=='admission' for r in rows)}))

if __name__=='__main__': main()
