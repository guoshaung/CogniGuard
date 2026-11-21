"""Fixture integrity and public evidence parsing only; not a verdict engine."""
import hashlib
import json

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf8')

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def unpack(x):
    events = {}
    for e in x['events']:
        row = {k:v for k,v in e.items() if k != 'fixture_digest'}
        if digest(row) != e['fixture_digest']:
            raise ValueError('FIXTURE_DIGEST_MISMATCH')
        eid=e['event_id']
        if eid in events and events[eid] != e:
            raise ValueError('CONFLICTING_EVENT_ID')
        events[eid]=e
    # Different event IDs can still assert incompatible same-version policy values.
    versions={}
    for e in events.values():
        if e['event_type']=='policy_snapshot':
            key=(e['policy_id'],e['policy_version'])
            val=e['payload']['allow_f']
            if key in versions and versions[key]!=val:
                raise ValueError('SAME_VERSION_CONFLICT')
            versions[key]=val
    ids=set(events)
    edges=set()
    for e in events.values():
        for p in e['causal_parent_ids']:
            if p not in ids:
                raise ValueError('DANGLING_CAUSAL_REFERENCE')
            edges.add((p,e['event_id']))
        lo,hi=e['local_time_interval']
        if lo>hi:
            raise ValueError('EMPTY_TIME_INTERVAL')
    actors={e['actor_id'] for e in events.values()}
    for actor in actors:
        ordered=sorted((e for e in events.values() if e['actor_id']==actor), key=lambda e:e['local_seq'])
        if len({e['local_seq'] for e in ordered})!=len(ordered):
            raise ValueError('LOCAL_SEQUENCE_CONFLICT')
        edges.update((a['event_id'],b['event_id']) for a,b in zip(ordered,ordered[1:]))
    reach=set(edges)
    for mid in ids:
        reach |= {(a,b) for a,m in list(reach) for n,b in list(reach) if m==mid==n}
    if any(a==b for a,b in reach):
        raise ValueError('CAUSAL_CYCLE')
    for a,b in reach:
        if events[a]['local_time_interval'][0]>=events[b]['local_time_interval'][1]:
            raise ValueError('TIME_CAUSAL_CONTRADICTION')
    return events, reach

def ancestors(x):
    graph=x['objects']; todo=[x['target']['object_id']]; seen=set()
    while todo:
        item=todo.pop()
        if item in seen: continue
        seen.add(item)
        todo.extend(graph.get(item,[]))
    return seen

def event_domains(x, events):
    effect=next((e for e in events.values() if e['event_type']=='effect_commit'),None)
    revoke=next((e for e in events.values() if e['event_type']=='revocation_published'),None)
    ep=[1] if effect else [0] if x['completeness']['receiver'] else [0,1]
    rp=[1] if revoke else [0] if x['completeness']['authority'] else [0,1]
    et=list(range(effect['local_time_interval'][0],effect['local_time_interval'][1]+1)) if effect else x['window']['effect_ticks']
    rt=list(range(revoke['local_time_interval'][0],revoke['local_time_interval'][1]+1)) if revoke else x['window']['revoke_ticks']
    return ep,rp,et,rt,effect,revoke

def summary(values):
    if not values: return 'EVIDENCE_INVALID'
    if values=={True}: return 'VIOLATION_PROVEN'
    if values=={False}: return 'COMPLIANT_PROVEN'
    return 'INDETERMINATE'
