"""Exhaustive legal-action audit; no scheduler, predictor, training or generation."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
from core.paths import PROJECT_ROOT, RESULTS_DIR

OUT=RESULTS_DIR/'c2rag_real_source_structure_20261027_01'


def dump(name,value):
    with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def load_module(name):
    spec=importlib.util.spec_from_file_location('r32_'+name,OUT/'snapshot'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def legal_selections(task):
    pools=[[None]+[a for a in task['actions'] if a['request_id']==q['request_id']] for q in task['requests']]
    for choice in itertools.product(*pools):yield [a for a in choice if a is not None]


def views_of(actions,n=4):
    views=[set() for _ in range(n)]
    for a in actions:views[a['recipient']].update(a['reveals'])
    return views


def visible(views,mask):return set().union(*(v for i,v in enumerate(views) if mask&(1<<i)))


def case(task,authorized=False):
    return {k:task[k] for k in ['n','facts','rules','public']}|{'assets':[{'target':'TARGET','authorized':list(range(1,16)) if authorized else []}]}


def main():
    sys.stdout.reconfigure(encoding='utf8')
    frozen=json.loads((OUT/'freeze.json').read_text(encoding='utf8'))
    for p,h in frozen['sha256'].items():assert hashlib.sha256((PROJECT_ROOT/p).read_bytes()).hexdigest()==h,p
    dump('execution_started.json',{'utc':datetime.now(timezone.utc).isoformat(),'freeze_verified':True,'models_called':0})
    tasks=json.loads((OUT/'contracts.json').read_text(encoding='utf8'))
    engines=load_module('engines');ref=load_module('reference')
    queries={}
    for t in tasks:
        sets=set()
        for actions in legal_selections(t):
            v=views_of(actions)
            for c in ref.groups(4):sets.add(tuple(sorted(visible(v,ref.mask(c)))))
        queries[t['task_id']]=[list(x) for x in sorted(sets)]
    dump('math_queries.json',queries)
    worker=PROJECT_ROOT/'experiments/c2rag_real_source_structure_20261027_01/math_reference.py'
    proc=subprocess.run([str(PROJECT_ROOT/'.venv/Scripts/python.exe'),'-B',str(worker),str(OUT/'contracts.json'),
                         str(OUT/'math_queries.json'),str(OUT/'math_certificates.json')],capture_output=True,text=True,encoding='utf8')
    (OUT/'math_execution.log').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf8')
    if proc.returncode:raise RuntimeError('Independent math worker failed; retained math_execution.log')
    math=json.loads((OUT/'math_certificates.json').read_text(encoding='utf8'))['results']
    allrows=[];summaries=[];allwitness=[]
    for t in tasks:
        tid=t['task_id'];c=case(t);compiled=engines.Compiled(c);rows=[];mismatches=[]
        for actions in legal_selections(t):
            v=views_of(actions);state=engines.METHODS['ExactK3'](compiled)
            for a in sorted(actions,key=lambda x:x['round']):state,_,_=state.trial({a['recipient']:a['reveals']})
            reconstructed=ref.reconstruct(c,v);risk=ref.unsafe(c,v)
            expected={str(mask):compiled.bits(facts) for mask,facts in reconstructed.items()}
            assert state.vector()==expected and bool(state.bad)==risk,(tid,actions)
            coal=[]
            for mask,cl in reconstructed.items():
                k='|'.join(sorted(visible(v,mask)));cert=math[tid][k]
                horn='TARGET' in cl
                mismatch=(cert['status']=='UNIQUE' and not horn) or (cert['status']=='NONUNIQUE' and horn)
                if mismatch:mismatches.append({'actions':[a['action_id'] for a in actions],'coalition':mask,'math_key':k,'horn':horn,'math':cert['status']})
                coal.append({'mask':mask,'members':[i for i in range(4) if mask&(1<<i)],'direct_fields':sorted(visible(v,mask)),
                             'horn_target':horn,'math_status':cert['status'],'math_key':k})
            status='UNSAFE' if any(x['math_status']=='UNIQUE' for x in coal) else ('UNKNOWN' if any(x['math_status']=='UNKNOWN' for x in coal) else 'SAFE')
            rows.append({'task_id':tid,'actions':[a['action_id'] for a in actions],'exactk3_unsafe':risk,'reference_unsafe':risk,
                         'math_risk':status,'coalitions':coal,'normal_correct':len(actions),'normal_total':4,
                         'delivered_bytes':sum(a['utf8_bytes'] for a in actions)})
        by_ids={frozenset(row['actions']):row for row in rows}
        minima=[]
        for row in rows:
            ids=frozenset(row['actions'])
            if row['math_risk']!='UNSAFE':continue
            if any(by_ids[ids-{a}]['math_risk']!='SAFE' for a in ids):continue
            witness={'task_id':tid,'actions':row['actions'],'size':len(ids),'coalitions':[]}
            for cl in row['coalitions']:
                if cl['math_status']!='UNIQUE':continue
                subset=[a for a in t['actions'] if a['action_id'] in ids and cl['mask']&(1<<a['recipient'])]
                subsviews=views_of(subset)
                proper=[]
                for size in range(1,len(cl['members'])):
                    for members in itertools.combinations(cl['members'],size):
                        mask=sum(1<<i for i in members);key='|'.join(sorted(visible(subsviews,mask)))
                        proper.append({'members':list(members),'math_key':key,'status':math[tid][key]['status']})
                # Only minimal recipient support, not larger supersets of same witness.
                if any(x['status']=='UNIQUE' for x in proper):continue
                witness['coalitions'].append({'members':cl['members'],'mask':cl['mask'],'math_key':cl['math_key'],
                                             'all_proper_coalitions':proper,'genuine_three_person':len(cl['members'])==3 and all(x['status']=='NONUNIQUE' for x in proper)})
            minima.append(witness)
        # Authorization is explicit coalition authorization, never union of role grants.
        acase=case(t,True);acc=engines.Compiled(acase)
        for actions in legal_selections(t):
            state=engines.METHODS['ExactK3'](acc)
            for a in actions:state,_,_=state.trial({a['recipient']:a['reveals']})
            assert not state.bad and not ref.unsafe(acase,views_of(actions))
        allrows.extend(rows);allwitness.extend(minima)
        counts=Counter(x['math_risk'] for x in rows)
        summary={'task_id':tid,'title':t['title'],'family':t['family'],'candidates':len(t['actions']),
                 'legal_schedules':len(rows),'schedule_status':dict(counts),'minimal_unsafe_count':len(minima),
                 'minimal_unsafe_sizes':dict(Counter(x['size'] for x in minima)),
                 'three_person_witnesses':sum(any(c['genuine_three_person'] for c in x['coalitions']) for x in minima),
                 'engine_reference_disagreements':0,'horn_math_disagreements':mismatches,
                 'authorized_control_false_alerts':0,'all_coalition_checks':len(rows)*14,
                 'safe_nonempty_schedules':sum(x['math_risk']=='SAFE' and bool(x['actions']) for x in rows)}
        summaries.append(summary);print(tid,counts,'minima',len(minima),'math disagreements',len(mismatches),flush=True)
    dump('release_combinations.json',allrows)
    dump('minimal_unsafe_witnesses.json',allwitness)
    dump('summary.json',summaries)
    after={p:hashlib.sha256((PROJECT_ROOT/p).read_bytes()).hexdigest() for p in json.loads((OUT/'source_hashes_before.json').read_text(encoding='utf8'))}
    assert after==json.loads((OUT/'source_hashes_before.json').read_text(encoding='utf8'))
    dump('verification.json',{'source_hashes_after':after,'source_hashes_unchanged':True,'engine_reference_disagreements':0,
                             'authorized_control_false_alerts':0,'models_called':0,'paid_api_calls':0,
                             'completed_utc':datetime.now(timezone.utc).isoformat()})


if __name__=='__main__':main()
