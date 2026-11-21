"""Independent small-domain oracle. Does not import either baseline or wire.py."""
import hashlib
import itertools
import json
import time

def solve(x):
    started=time.perf_counter(); count=0; records={}; signatures={}
    for row in x['events']:
        data={k:v for k,v in row.items() if k!='fixture_digest'}
        actual=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        if actual!=row['fixture_digest']: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
        key=row['event_id']
        if key in records and records[key]!=row: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
        if row['event_type']=='policy_snapshot':
            version=(row['policy_id'],row['policy_version'])
            if version in signatures and signatures[version]!=row['payload']: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
            signatures[version]=row['payload']
        records[key]=row
    E=next((v for v in records.values() if v['event_type']=='effect_commit'),None)
    R=next((v for v in records.values() if v['event_type']=='revocation_published'),None)
    pairs=[]
    for v in records.values():
        if v['local_time_interval'][0]>v['local_time_interval'][1]: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
        for a in v['causal_parent_ids']:
            if a not in records: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
            pairs.append((a,v['event_id']))
    for a in records.values():
        for b in records.values():
            if a['event_id']!=b['event_id'] and a['actor_id']==b['actor_id']:
                if a['local_seq']==b['local_seq']: return {'verdict':'EVIDENCE_INVALID','nodes':0,'witnesses':[]}
                if a['local_seq']<b['local_seq']: pairs.append((a['event_id'],b['event_id']))
    # Independent object closure via repeated set expansion, not the baseline DFS.
    deps={x['target']['object_id']}
    while True:
        more=deps | {d for a in deps for d in x['objects'].get(a,[])}
        if more==deps: break
        deps=more
    ed=range(E['local_time_interval'][0],E['local_time_interval'][1]+1) if E else x['window']['effect_ticks']
    rd=range(R['local_time_interval'][0],R['local_time_interval'][1]+1) if R else x['window']['revoke_ticks']
    edp=[True] if E else [False] if x['completeness']['receiver'] else [False,True]
    rdp=[True] if R else [False] if x['completeness']['authority'] else [False,True]
    seen=set(); proof={}
    for tE,tR,hasE,hasR in itertools.product(ed,rd,edp,rdp):
        count+=1
        if count>100000 or time.perf_counter()-started>30: return {'verdict':'RESOURCE_LIMIT','nodes':count,'witnesses':[]}
        mapping={k:v['local_time_interval'][0] for k,v in records.items()}
        if E: mapping[E['event_id']]=tE
        if R: mapping[R['event_id']]=tR
        if not all(mapping[a]<mapping[b] for a,b in pairs): continue
        expired=False
        if 'profile.f' in deps:
            if x['policy']['mode']=='bounded' and x['check']['query_available'] is False:
                expired=x['check']['installed_revoked'] or tE<x['check']['issued_tick'] or tE>=x['check']['issued_tick']+x['policy']['delta']
            else: expired=hasR and tE>=tR
        if x['policy']['mode']=='grace':
            P=x['policy']; A=x['target']
            resource_bad=tE>=P['expiry'] and (tE>=P['hard_deadline'] or A['session_id']!=P['preauthorized_session'] or A['operation'] not in ['submit','receipt'])
            expired=expired or resource_bad
        v=bool(hasE and expired); seen.add(v)
        proof.setdefault(v,{'effect_present':int(hasE),'revocation_present':int(hasR),'effect_tick':tE,'revoke_tick':tR})
    label='EVIDENCE_INVALID' if not seen else 'INDETERMINATE' if len(seen)>1 else 'VIOLATION_PROVEN' if True in seen else 'COMPLIANT_PROVEN'
    return {'verdict':label,'nodes':count,'witnesses':list(proof.values())}
