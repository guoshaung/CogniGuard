"""Explicitly separate supplementary S00-12; never resumes old fail-fast run."""
import json,sys,os,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
OLD=Path('D:/cg-knowledge-assets-stage0-v2-20261018_01')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def new(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def main():
    manifest=json.loads((OLD/'var/results/frozen_manifest.json').read_bytes())
    mismatches=[p for p,h in manifest['files_sha256'].items() if sha(OLD/p)!=h]
    sources=manifest['source_files_sha256'];root=OUT.parents[1]
    source_mismatch=[p for p,h in sources.items() if not (root/p).is_file() or sha(root/p)!=h]
    # Cross-check every available score, raw digest, frozen config and observer.
    historical=[]
    for line in (OLD/'var/results/independent_scores.jsonl').read_text(encoding='utf-8').splitlines():
        s=json.loads(line);cid=s['case_id'];raw=OLD/'results'/cid/'raw.json'
        historical.append({'case_id':cid,'status':s['status'],'checks':len(s.get('checks',[])),'failure_codes':s.get('failure_codes',[]),'raw_exists':raw.exists(),'raw_hash_matches':sha(raw)==s.get('raw_sha256') if raw.exists() else None})
    new(OUT/'historical_evidence_audit.json',{'v2_frozen_files_checked':len(manifest['files_sha256']),'v2_frozen_mismatches':mismatches,'historic_source_files_checked':len(sources),'historic_source_mismatches':source_mismatch,'scores':historical,'v1_summary':json.loads((Path('D:/cg-knowledge-assets-diagnostic-20261018_01')/'var/results/summary.json').read_bytes()),'v2_selftests':json.loads((OLD/'selftests_v2/summary.json').read_bytes())})
    if mismatches or source_mismatch:raise RuntimeError('Frozen evidence or original sources changed: no new runtime')
    new(OUT/'supplement_protocol.json',{'frozen_utc':datetime.now(timezone.utc).isoformat(),'case':'S00-12','separate_from':'old v2 stopped run, never overwritten','expected_original_acceptance':'FAIL if observed direct sink write absent from native sink_events','interpretation':'unmediated channel scope limitation, not mediated CGC algorithm failure','old_stop_policy_preserved':True,'runtime_sha256':sha(OLD/'runtime_probe.py'),'scorer_sha256':sha(OLD/'independent_scorer.py'),'truth_sha256':sha(OLD/'oracle_truth.json'),'model_calls':0,'phase1':'DISABLED'})
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false',PYTHONHASHSEED='20261018')
    for key in list(env):
        if any(t in key.upper() for t in ['API_KEY','API_TOKEN','AUTH_TOKEN','SECRET','PASSWORD']):env.pop(key,None)
    commands=[('runtime',[sys.executable,'-B',str(OLD/'runtime_probe.py'),'--cases',str(OLD/'runtime_cases.json'),'--case-id','S00-12','--out',str(OUT/'S00-12')]),('scorer',[sys.executable,'-B',str(OLD/'independent_scorer.py'),'--raw',str(OUT/'S00-12/raw.json'),'--truth',str(OLD/'oracle_truth.json'),'--out',str(OUT/'S00-12.score.json')])]
    for label,args in commands:
        with (OUT/(label+'.stdout.txt')).open('xb') as stdout,(OUT/(label+'.stderr.txt')).open('xb') as stderr:
            process=subprocess.run(args,cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW)
        if process.returncode:raise RuntimeError(label+' failed; preserve evidence and stop')
    print(json.dumps(json.loads((OUT/'S00-12.score.json').read_bytes())))
if __name__=='__main__':main()
