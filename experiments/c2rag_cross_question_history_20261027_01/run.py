"""One replay run plus bounded exhaustive offline references; no new controller."""
from collections import Counter
import csv
from datetime import datetime,timezone
from fractions import Fraction
import itertools
import json
import time
import traceback
from experiments.c2rag_cross_question_history_20261027_01.common import OUT,read,write,module,verify_freeze,sha
from experiments.c2rag_cross_question_history_20261027_01.observer import decode


def coalitions():
    return [(sum(1<<i for i in group),group) for size in [1,2,3] for group in itertools.combinations(range(4),size)]


def case_of(data):return {k:data[k] for k in ['n','facts','rules','public','assets']}


def target_state(case,views,ref,cache):
    groups=[]
    for mask,members in coalitions():
        known=frozenset().union(*(set(views[i]) for i in members))
        if known not in cache:cache[known]=ref.closure(known,case['rules'],case['public'])
        cl=cache[known]
        groups.append({'mask':mask,'members':list(members),'size':len(members),'known':sorted(known),
                       'closure':sorted(cl),'targets':[a['target'] for a in case['assets'] if a['target'] in cl],
                       'partial_T06_fields':[f for f in ['F_push','f','d_push'] if f in cl]})
    targets={}
    for a in case['assets']:
        matches=[g for g in groups if a['target'] in g['targets']]
        targets[a['target']]={'k_min':min((g['size'] for g in matches),default=None),
                              'counts_exact_k':{str(k):sum(g['size']==k for g in matches) for k in [1,2,3]}}
    return {'targets':targets,'coalitions':groups,'unsafe':any(g['targets'] for g in groups)}


def replay(data,eng,ref):
    case=case_of(data);compiled=eng.Compiled(case);traces=[];summary=[]
    for method in ['NoGate','Reset','Shared']:
        state=eng.METHODS['ExactK3'](compiled);controller_views=[set() for _ in range(4)]
        observer_views=[{} for _ in range(4)];cache={};seen=set();first={a['target']:None for a in data['assets']}
        steps=[]
        for q in data['requests']:
            if method=='Reset' and (q['step']-1)%4==0:
                state=eng.METHODS['ExactK3'](compiled);controller_views=[set() for _ in range(4)]
            a=q['candidates'][0];who=q['recipient']
            trial,risk,_=state.trial({who:a['reveals']})
            cv=[s.copy() for s in controller_views];cv[who].update(a['reveals'])
            recons=ref.reconstruct(case,cv)
            assert trial.vector()=={str(k):compiled.bits(v) for k,v in recons.items()}
            assert risk==ref.unsafe(case,cv)
            allowed=method=='NoGate' or not risk
            reply=a['reply'] if allowed else ''
            if allowed:state=trial;controller_views=cv
            parsed=decode(reply,q['task_id'])
            if allowed:assert set(parsed)==set(a['reveals'])
            for k,v in parsed.items():
                assert v==Fraction(data['field_values_evaluator_only'][k])
                assert k not in observer_views[who] or observer_views[who][k]==v
                observer_views[who][k]=v
            obs=target_state(case,observer_views,ref,cache)
            new={a['target'] for a in case['assets'] if obs['targets'][a['target']]['k_min'] is not None}-seen
            for target in new:first[target]=q['step']
            seen.update(new)
            steps.append({'method':method,'step':q['step'],'task_id':q['task_id'],'asset_id':q['asset_id'],
                          'recipient':who,'request_id':q['request_id'],'query':q['query'],
                          'candidate_action':a['action_id'],'candidate_reply':a['reply'],
                          'actual_reply':reply,'controller_decision':'ALLOW' if allowed else 'REFUSE',
                          'controller_candidate_unsafe':risk,'normal_correct':int(allowed),
                          'actual_bytes':len(reply.encode('utf8')),
                          'observer_parsed_values':{k:str(v) for k,v in parsed.items()},
                          'observer_persistent_views':[{k:str(v) for k,v in s.items()} for s in observer_views],
                          'observer':obs,'new_targets':sorted(new),
                          'allowed_but_observer_unsafe':allowed and obs['unsafe'],
                          'false_safe_allow':allowed and not risk and obs['unsafe'],
                          'global_case_sha256':sha(json.dumps(case,sort_keys=True).encode())})
        summary.append({'method':method,'correct':sum(s['normal_correct'] for s in steps),'total':16,
                        'refusals':sum(not s['normal_correct'] for s in steps),
                        'output_bytes':sum(s['actual_bytes'] for s in steps),
                        'first_recovery_steps':first,'final_targets_recovered':len(seen),
                        'allowed_but_observer_unsafe_steps':[s['step'] for s in steps if s['allowed_but_observer_unsafe']],
                        'false_safe_allow_steps':[s['step'] for s in steps if s['false_safe_allow']],
                        'new_target_delivery_steps':[s['step'] for s in steps if s['normal_correct'] and s['new_targets']],
                        'final_recovery_by_exact_k':{str(k):sorted({t for g in steps[-1]['observer']['coalitions'] if g['size']==k for t in g['targets']}) for k in [1,2,3]}})
        traces.extend(steps)
        print(method,summary[-1]['correct'],summary[-1]['output_bytes'],first,flush=True)
    return traces,summary


def enumerate_plans(data,eng,ref,all_candidates,implementation,seconds):
    started=time.process_time();case=case_of(data);coals=coalitions();cache={}
    compiled=eng.Compiled(case)
    actions=[q['candidates'][0] for q in data['requests']]
    alt=data['requests'][4]['candidates'][1]
    widths=98304 if all_candidates else 65536
    safe_codes=[];best=[];best_value=-1;decisions=bytearray();checked=0
    atoms=compiled.index;target_bits=sum(1<<atoms[a['target']] for a in case['assets'])
    encoded={a['action_id']:compiled.bits(a['reveals']) for a in actions+[alt]}
    for code in range(widths):
        if time.process_time()-started>=seconds:
            return {'completed':False,'checked':checked,'planned':widths,'cpu_seconds':time.process_time()-started,
                    'budget_seconds':seconds,'implementation':implementation,'best_so_far_NOT_OPT':best_value,
                    'safe_codes':safe_codes,'status_digest':sha(bytes(decisions))}
        if all_candidates:
            other,choice=divmod(code,3);selected=[];j=0
            for i,a in enumerate(actions):
                if i==4:
                    if choice:selected.append(a if choice==1 else alt)
                else:
                    if other&(1<<j):selected.append(a)
                    j+=1
        else:selected=[a for i,a in enumerate(actions) if code&(1<<i)]
        unsafe=False
        if implementation=='ExactK3_final_semantics':
            views=[0]*4
            for a in selected:views[a['recipient']]|=encoded[a['action_id']]
            for mask,members in coals:
                bits=0
                for member in members:bits|=views[member]
                if bits not in cache:cache[bits]=compiled.expand(bits)
                if cache[bits]&target_bits:unsafe=True;break
        else:
            views=[set() for _ in range(4)]
            for a in selected:views[a['recipient']].update(decode(a['reply'],a['task_id']))
            for mask,members in coals:
                known=frozenset().union(*(views[i] for i in members))
                if known not in cache:cache[known]=ref.closure(known,case['rules'])
                if any(a['target'] in cache[known] for a in case['assets']):unsafe=True;break
        checked+=1;decisions.append(int(not unsafe))
        if unsafe:continue
        safe_codes.append(code);value=len(selected)
        plan={'code':code,'correct':value,'output_bytes':sum(len(a['reply'].encode('utf8')) for a in selected),
              'actions':[a['action_id'] for a in selected]}
        if value>best_value:best_value=value;best=[plan]
        elif value==best_value:best.append(plan)
    best.sort(key=lambda p:(p['output_bytes'],p['code']))
    return {'completed':True,'checked':checked,'planned':widths,'cpu_seconds':time.process_time()-started,
            'budget_seconds':seconds,'implementation':implementation,'opt_correct':best_value,
            'optimal_plans':best,'safe_codes':safe_codes,'status_digest':sha(bytes(decisions))}


def minimum_witnesses(data,traces,ref):
    """Enumerate actual-delivery subsets, retain target-specific minimal supports."""
    case=case_of(data);byid={a['action_id']:a for q in data['requests'] for a in q['candidates']}
    cache={}
    def closure(actions):
        known=frozenset(f for a in actions for f in decode(a['reply'],a['task_id']))
        if known not in cache:cache[known]=ref.closure(known,case['rules'])
        return cache[known]
    witnesses=[]
    for method in ['NoGate','Reset','Shared']:
        actual=[byid[s['candidate_action']] for s in traces if s['method']==method and s['normal_correct']]
        for target in [a['target'] for a in data['assets']]:
            minima=[]
            # Supports cannot use >3 recipients. Repeated equivalent deliveries remain explicit.
            for size in range(1,len(actual)+1):
                for combo in itertools.combinations(actual,size):
                    ids=frozenset(a['action_id'] for a in combo)
                    if any(x<=ids for x in minima):continue
                    members=sorted({a['recipient'] for a in combo})
                    if len(members)>3 or target not in closure(combo):continue
                    deletion=[{'removed':a['action_id'],'recovers':target in closure([x for x in combo if x is not a])} for a in combo]
                    assert not any(x['recovers'] for x in deletion)
                    minima.append(ids)
                    tasks=sorted({a['task_id'] for a in combo})
                    separate={tid:target in closure([a for a in combo if a['task_id']==tid]) for tid in tasks}
                    kind='direct' if size==1 else ('single_question_combination' if len(tasks)==1 else 'cross_question_accumulation')
                    if kind=='cross_question_accumulation':assert not any(separate.values())
                    witnesses.append({'method':method,'target':target,'kind':kind,'actions':sorted(ids),
                       'members':members,'k_min_for_support':len(members),'tasks':tasks,
                       'last_step':max(a['step'] for a in combo),'separate_question_recovers':separate,
                       'deletion_checks':deletion,
                       'known_values':{k:str(v) for a in combo for k,v in decode(a['reply'],a['task_id']).items()},
                       'actual_deliveries':[{'step':a['step'],'task_id':a['task_id'],'recipient':a['recipient'],
                                            'action_id':a['action_id'],'reply':a['reply']} for a in combo]})
    return witnesses


def verify_plans(data,plans,eng,ref):
    case=case_of(data);compiled=eng.Compiled(case);byid={a['action_id']:a for q in data['requests'] for a in q['candidates']}
    results=[]
    for plan in plans:
        state=eng.METHODS['ExactK3'](compiled);views=[set() for _ in range(4)];steps=[]
        for a in sorted((byid[i] for i in plan['actions']),key=lambda a:a['step']):
            state,risk,_=state.trial({a['recipient']:a['reveals']});views[a['recipient']].update(decode(a['reply'],a['task_id']))
            assert not risk and not ref.unsafe(case,views)
            steps.append(a['step'])
        results.append({'code':plan['code'],'actions':plan['actions'],'prefix_safe':True,'prefix_steps':steps})
    return results


def main():
    verify_freeze();write('execution_started.json',{'utc':datetime.now(timezone.utc).isoformat(),'freeze_verified':True})
    try:
        data=read('instance.json');eng=module('engines');ref=module('reference')
        traces,summary=replay(data,eng,ref);write('replay.json',traces);write('method_summary.json',summary)
        with (OUT/'method_summary.csv').open('x',encoding='utf-8-sig',newline='') as f:
            fields=['method','correct','total','refusals','output_bytes','final_targets_recovered']
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:s[k] for k in fields} for s in summary)
        references={};plan_checks={}
        for mode,allc in [('fixed',False),('all',True)]:
            if mode=='all' and not references['fixed'].get('independent_agreement',False):
                references['all']={'completed':False,'reason':'fixed exhaustive verification incomplete'};break
            p=enumerate_plans(data,eng,ref,allc,'ExactK3_final_semantics',data['cpu_budgets_seconds'][mode+'_primary'])
            write(f'opt_{mode}_primary.json',p)
            if not p['completed']:
                references[mode]={'completed':False,'primary':p};continue
            r=enumerate_plans(data,eng,ref,allc,'independent_sets_actual_text',data['cpu_budgets_seconds'][mode+'_independent'])
            write(f'opt_{mode}_independent.json',r)
            agreement=r['completed'] and p['safe_codes']==r['safe_codes'] and p['optimal_plans']==r['optimal_plans']
            if r['completed']:assert agreement
            references[mode]={'completed':p['completed'] and r['completed'],'independent_agreement':agreement,
                              'opt_correct':p['opt_correct'] if agreement else None,
                              'representative_plan':p['optimal_plans'][0] if agreement else None}
            if agreement:plan_checks[mode]=verify_plans(data,p['optimal_plans'],eng,ref)
            print(mode,'opt',references[mode].get('opt_correct'),'cpu',p['cpu_seconds'],r['cpu_seconds'],flush=True)
        write('offline_references.json',references);write('optimal_plan_prefix_checks.json',plan_checks)
        witnesses=minimum_witnesses(data,traces,ref);write('minimal_witnesses.json',witnesses)
        # Freeze exact mathematical queries from actual histories, deletion/single-question
        # counterfactuals and every certified optimal plan, with no engine verdict supplied.
        queries=set()
        for s in traces:
            for g in s['observer']['coalitions']:queries.add(tuple(g['known']))
        for w in witnesses:
            acts=w['actual_deliveries']
            queries.add(tuple(sorted(w['known_values'])))
            for a in acts:queries.add(tuple(sorted({k for x in acts if x!=a for k in decode(x['reply'],x['task_id'])})))
            for tid in w['tasks']:queries.add(tuple(sorted({k for x in acts if x['task_id']==tid for k in decode(x['reply'],x['task_id'])})))
        byid={a['action_id']:a for q in data['requests'] for a in q['candidates']}
        for mode,plans in plan_checks.items():
            for p in plans:
                views=[set() for _ in range(4)]
                for aid in p['actions']:views[byid[aid]['recipient']].update(decode(byid[aid]['reply'],byid[aid]['task_id']))
                for mask,members in coalitions():queries.add(tuple(sorted(set().union(*(views[i] for i in members)))))
        write('math_queries.json',[list(q) for q in sorted(queries)])
        write('execution_completed.json',{'utc':datetime.now(timezone.utc).isoformat(),'replay_steps':len(traces),
                                          'minimal_witnesses':len(witnesses),'math_queries':len(queries),'model_calls':0})
    except Exception:
        write('FAILURE.json',{'traceback':traceback.format_exc(),'stop_no_overwrite':True,'contract_not_changed':True})
        raise


if __name__=='__main__':main()
