"""Freeze first; run bounded actual primitive exercise; preserve every failure."""
import os,json,hashlib,sys,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def run(args,stem):
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
    for key in list(env):
        if any(v in key.upper() for v in ['API_KEY','API_TOKEN','AUTH_TOKEN','SECRET','PASSWORD']):env.pop(key,None)
    with Path(str(stem)+'.stdout.txt').open('xb') as a,Path(str(stem)+'.stderr.txt').open('xb') as b:
        p=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=a,stderr=b,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
    return p.returncode
def main():
    attempt=HERE/'attempt_01';attempt.mkdir(exist_ok=False)
    paths=list(HERE.glob('*.py'))+[HERE/'protocol.json',HERE/'observer_policy.json']+list((HERE/'runtime_inputs').glob('*.json'))+list((HERE/'evaluator_only').glob('*.json'))
    sources=['experiments/c2rag_v3/fact_release.py','experiments/c2rag_v3/evidence_release.py','experiments/c2rag_v3/core.py','experiments/c2rag_v3/generator.py','core/langgraph_runtime/teachers/chain.py','core/langgraph_runtime/teachers/catalog.py']
    save(attempt/'frozen_manifest.json',{'utc':datetime.now(timezone.utc).isoformat(),'fixture_and_scripts':{p.relative_to(HERE).as_posix():sha(p) for p in paths},'original_sources':{p:sha(ROOT/p) for p in sources},'scorer_reads_hidden_truth_after_runtime':True,'runtime_truth_parameter':False,'rule':'Any repair is a new attempt, no overwrite or truth/core relaxation.'})
    outcomes=[]
    for arch in ['Single-Agent','Multi-Agent','Identity-Split']:
        for defense in ['Per-Agent','Shared-Asset','Shared-Asset+CGC']:
            key=arch+'_'+defense;tick=time.perf_counter()
            code=run([str(HERE/'runtime.py'),arch,defense,str(attempt/key)],attempt/key)
            outcomes.append({'worker':key,'exit_code':code,'elapsed_ms':(time.perf_counter()-tick)*1000})
            print(json.dumps(outcomes[-1]),flush=True)
            if code:
                # Independent groups may continue only after this failed version
                # is recorded and inspected; do not silently consume all cases.
                save(attempt/'execution_outcomes.json',outcomes)
                print('STOPPED_RUNTIME_FAILURE_PRESERVED',flush=True);return
    code=run([str(HERE/'runtime.py'),'TRUTH_PROBE','none',str(attempt/'truth_probe')],attempt/'truth_probe')
    outcomes.append({'worker':'truth_probe','exit_code':code})
    save(attempt/'execution_outcomes.json',outcomes)
    code=run([str(HERE/'scorer.py'),str(attempt)],attempt/'scorer')
    print(json.dumps({'scorer_exit_code':code}),flush=True)
if __name__=='__main__':main()
