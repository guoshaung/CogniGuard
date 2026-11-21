"""Freeze, execute admission first, then the finite extension. No old matrix rerun."""
import argparse
import collections
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

H=Path(__file__).resolve().parent
sys.path.insert(0,str(H/'src'))
from oracle import solve

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists(): raise FileExistsError(p)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n','utf8')

def freeze():
    paths=[p for p in H.rglob('*') if p.is_file() and (p.suffix in ('.py','.md') or
           p.name=='cases.jsonl' or 'audit_inputs' in p.parts or 'oracle' in p.parts)]
    # Syntax check without creating pycache or running any verdict engine.
    for p in paths:
        if p.suffix=='.py': compile(p.read_text('utf8'),str(p),'exec')
    write(H/'FREEZE_MANIFEST.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),
          'protocol':'CG-C-FINITE-01','files':[{'path':str(p.relative_to(H)),'sha256':sha(p)} for p in sorted(paths)],
          'worker_file_access':'disabled after imports','max_instances':96,'max_nodes':100000,'per_instance_seconds':30,
          'run_seconds':600,'max_repairs':2,'gpu_calls':0,'model_calls':0})

def run(run_id):
    manifest=json.loads((H/'FREEZE_MANIFEST.json').read_text('utf8'))
    changed=[r['path'] for r in manifest['files'] if sha(H/r['path'])!=r['sha256']]
    if changed: raise RuntimeError(('FROZEN_FILES_CHANGED',changed))
    out=H/'runs'/run_id
    out.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(s) for s in (H/'cases.jsonl').read_text('utf8').splitlines()]
    all_results=[]; start=time.perf_counter()
    env=os.environ.copy(); env.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                                      CUDA_VISIBLE_DEVICES='',LANGSMITH_TRACING='false')
    for phase in ['admission','extension']:
        for r in [z for z in rows if z['phase']==phase]:
            if time.perf_counter()-start>600: raise TimeoutError('RUN_BUDGET_EXCEEDED')
            public=json.loads((H/r['path']).read_text('utf8'))
            truth=json.loads((H/'oracle'/f"{r['input_id']}.json").read_text('utf8'))
            reference=solve(public)
            methods={}
            for method in ['B1','B2']:
                try:
                    result=subprocess.run([sys.executable,str(H/'src/worker.py')],
                        input=json.dumps({'method':method,'public':public},ensure_ascii=False).encode('utf8'),
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=35,check=True)
                    methods[method]=json.loads(result.stdout)
                except subprocess.TimeoutExpired:
                    methods[method]={'verdict':'RESOURCE_LIMIT','reason':'subprocess_timeout','breaches':[]}
                except subprocess.CalledProcessError as exc:
                    methods[method]={'verdict':'IMPLEMENTATION_INCOMPLETE','stderr':exc.stderr.decode('utf8',errors='replace'),'breaches':[]}
            expected=truth['expected_verdict']
            checks={'oracle_matches_hand_label':reference['verdict']==expected}
            for method,result in methods.items():
                checks[method+'_verdict_matches']=result['verdict']==reference['verdict']==expected
                got=sorted(b['rule_id'] for b in result.get('breaches',[]))
                checks[method+'_duty_matches']=got==sorted(truth['expected_duties'])
                evidences={e['event_id'] for e in public['events']}
                checks[method+'_references_valid']=all(
                    b['actor_id']==public['target']['executor_id'] and b['action_id']==public['target']['action_id'] and
                    len(b['evidence_ids'])>0 and all(e in evidences for e in b['evidence_ids'])
                    for b in result.get('breaches',[]))
                checks[method+'_two_witnesses_if_unknown']=(result['verdict']!='INDETERMINATE' or len(result.get('witnesses',[]))==2)
            item={**r,'oracle':reference,'expected':expected,'methods':methods,'checks':checks,'passed':all(checks.values())}
            all_results.append(item)
            with (out/'results.jsonl').open('a',encoding='utf8') as f: f.write(json.dumps(item,ensure_ascii=False)+'\n')
        current=[r for r in all_results if r['phase']==phase]
        write(out/f'{phase}_summary.json',{'inputs':len(current),'passed':sum(r['passed'] for r in current),
                 'failures':[{k:r[k] for k in ['input_id','scenario','topology','view','checks']} for r in current if not r['passed']]})
        if not all(r['passed'] for r in current): break
    write(out/'summary.json',{'elapsed_seconds':time.perf_counter()-start,'inputs':len(all_results),
         'passed':sum(r['passed'] for r in all_results),'labels':dict(collections.Counter(r['expected'] for r in all_results)),
         'complete':len(all_results)==len(rows),'failures':[r['input_id'] for r in all_results if not r['passed']],
         'max_worker_rss_bytes':max(v.get('peak_rss_bytes',0) for r in all_results for v in r['methods'].values()),
         'gpu':0,'LLM':0,'API':0,'formal_run':run_id})
    print((out/'summary.json').read_text('utf8'))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['freeze','run']);p.add_argument('--run-id',default='initial')
    a=p.parse_args()
    freeze() if a.action=='freeze' else run(a.run_id)
