"""B1: conventional reference-state replay for the frozen finite rule fragment."""
import itertools
import time
from wire import unpack, ancestors, event_domains, summary

def audit(x):
    start=time.perf_counter()
    try: events,reach=unpack(x)
    except ValueError as exc: return {'verdict':'EVIDENCE_INVALID','reason':str(exc),'breaches':[],'witnesses':[],'nodes':0}
    ep,rp,et,rt,effect,revoke=event_domains(x,events)
    affected='profile.f' in ancestors(x)
    out=set(); witness={}; n=0
    for present,revoked,t,r in itertools.product(ep,rp,et,rt):
        n+=1
        if n>100000 or time.perf_counter()-start>30:
            return {'verdict':'RESOURCE_LIMIT','nodes':n,'breaches':[],'witnesses':[]}
        if effect and revoke:
            a,b=effect['event_id'],revoke['event_id']
            if ((a,b) in reach and t>=r) or ((b,a) in reach and r>=t): continue
        fixed={k:v['local_time_interval'][0] for k,v in events.items()}
        if effect: fixed[effect['event_id']]=t
        if revoke: fixed[revoke['event_id']]=r
        if any(fixed[a]>=fixed[b] for a,b in reach): continue
        profile_allowed=True
        if affected:
            if x['policy']['mode']=='bounded' and not x['check']['query_available']:
                # Re-reading a cache never refreshes issued_tick.
                profile_allowed=(not x['check']['installed_revoked'] and 0<=t-x['check']['issued_tick']<x['policy']['delta'])
            else:
                profile_allowed=not (revoked and r<=t)
        resource_allowed=True
        if x['policy']['mode']=='grace':
            if t>=x['policy']['expiry']:
                resource_allowed=(x['target']['session_id']==x['policy']['preauthorized_session'] and
                                  x['target']['operation'] in ('submit','receipt') and t<x['policy']['hard_deadline'])
        violation=bool(present and not (profile_allowed and resource_allowed))
        out.add(violation)
        witness.setdefault(str(violation),{'effect_present':present,'revocation_present':revoked,'effect_tick':t,'revoke_tick':r})
    # Node duty findings are separate from action authorization, and never blame ancestors.
    breaches=[]
    if x['check']['query_available'] and not x['check']['query_used'] and ep==[1]:
        breaches.append({'actor_id':x['target']['executor_id'],'rule_id':'D_RECHECK','action_id':x['target']['action_id'],
                         'evidence_ids':[e['event_id'] for e in events.values() if e['event_type']=='authorization_check']})
    if x['check']['rollback_accepted']:
        breaches.append({'actor_id':x['target']['executor_id'],'rule_id':'D_VERSION_MONOTONE','action_id':x['target']['action_id'],
                         'evidence_ids':[e['event_id'] for e in events.values() if e['event_type']=='policy_install']})
    return {'verdict':summary(out),'nodes':n,'breaches':breaches,'witnesses':list(witness.values()),
            'evidence_ids':list(events),'rule_id':'R_ACTION','action_id':x['target']['action_id']}
