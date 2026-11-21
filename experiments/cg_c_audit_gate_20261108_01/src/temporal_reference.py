"""B2 REFERENCE_ENUMERATOR: finite event-order monitor, NOT an R3/R4 reproduction."""
import itertools
import time
from wire import unpack, ancestors, event_domains, summary

def audit(x):
    started=time.perf_counter()
    try: events,relation=unpack(x)
    except ValueError as exc: return {'verdict':'EVIDENCE_INVALID','reason':str(exc),'nodes':0,'witnesses':[],'breaches':[]}
    present,revocations,ends,starts,ee,re=event_domains(x,events)
    verdicts=set(); certificates={}; nodes=0
    for e,r in itertools.product(present,revocations):
        for ts in itertools.product(starts,ends):
            nodes+=1
            if nodes>100000 or time.perf_counter()-started>30:
                return {'verdict':'RESOURCE_LIMIT','nodes':nodes,'witnesses':[],'breaches':[]}
            clock={k:v['local_time_interval'][0] for k,v in events.items()}
            if ee: clock[ee['event_id']]=ts[1]
            if re: clock[re['event_id']]=ts[0]
            if any(clock[a]>=clock[b] for a,b in relation): continue
            # For ties the frozen rule makes revocation effective at its boundary.
            stream=[(ts[1],1,'commit')] if e else []
            if r: stream.append((ts[0],0,'revoke'))
            permission=True; violation=False
            for tick,_,kind in sorted(stream):
                if kind=='revoke':
                    permission=False
                    continue
                if 'profile.f' in ancestors(x):
                    if x['policy']['mode']=='bounded' and not x['check']['query_available']:
                        age=tick-x['check']['issued_tick']
                        if x['check']['installed_revoked'] or age<0 or age>=x['policy']['delta']: violation=True
                    elif not permission: violation=True
                if x['policy']['mode']=='grace' and tick>=x['policy']['expiry']:
                    legal_close=(tick<x['policy']['hard_deadline'] and
                                 x['target']['session_id']==x['policy']['preauthorized_session'] and
                                 x['target']['operation'] in {'receipt','submit'})
                    if not legal_close: violation=True
            verdicts.add(violation)
            certificates.setdefault(violation,{'effect_present':e,'revocation_present':r,'effect_tick':ts[1],'revoke_tick':ts[0]})
    findings=[]
    if not x['check']['query_used'] and x['check']['query_available'] and present==[1]:
        findings.append({'actor_id':x['target']['executor_id'],'rule_id':'D_RECHECK','action_id':x['target']['action_id'],
                         'evidence_ids':[k for k,v in events.items() if v['event_type']=='authorization_check']})
    if x['check']['rollback_accepted']:
        findings.append({'actor_id':x['target']['executor_id'],'rule_id':'D_VERSION_MONOTONE','action_id':x['target']['action_id'],
                         'evidence_ids':[k for k,v in events.items() if v['event_type']=='policy_install']})
    return {'verdict':summary(verdicts),'nodes':nodes,'breaches':findings,'witnesses':list(certificates.values()),
            'evidence_ids':list(events),'rule_id':'R_ACTION','action_id':x['target']['action_id']}
