"""Isolated checkpoint concept. Same-user process separation is SIMULATED trust.

Controller holds immutable checkpoint bytes before handing files to mutation
worker. Disk receipt is evidence only, never the trusted input to validation.
No production persistence or third party services are used.
"""
import sys, json, hashlib, copy, subprocess, importlib.util
from pathlib import Path
from datetime import datetime, timezone
OUT=Path(__file__).resolve().parent
def now():return datetime.now(timezone.utc).isoformat()
def write(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def worker(case,path):
    records=load(path)
    if case in {'tail_delete','unanchored_tail'}: records.pop()
    elif case=='middle_modify':records[1]['value']=999
    elif case=='reorder':records[0],records[1]=records[1],records[0]
    elif case=='rollback':records=records[:1]
    elif case=='empty':records=[]
    elif case=='consistent_rewrite':
        records[0]['value']=999;previous='GENESIS'
        for r in records:
            r['previous_hash']=previous;r.pop('record_hash',None)
            r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();previous=r['record_hash']
    path.write_text(json.dumps(records),encoding='utf-8')
def main():
    result_dir=OUT/'witness_results';result_dir.mkdir(exist_ok=False)
    # Import only original stdlib ledger module, avoid application initialization.
    spec=importlib.util.spec_from_file_location('cg_fixture_ledger',OUT.parents[1]/'cogniguard/governance/audit.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    predicates={'clean':True,'tail_delete':False,'middle_modify':False,'reorder':False,'missing_witness':None,'rollback':False,'empty':False,'consistent_rewrite':False,'unanchored_tail':None,'stale_witness':None,'wrong_run':False}
    write(OUT/'witness_protocol.json',{'frozen_at':now(),'expected_complete':predicates,'commit_cycle':'checkpoint after every 2 fixture events; count=2 must be acknowledged before considered anchored','unanchored_window':'event 3 until next durable acknowledgement; missing events in this window cannot be detected from checkpoint alone','trust':'SIMULATION: controller memory separated from honest mutation worker only; same UID, no durable independent authority','missing_or_stale':'UNKNOWN, never PASS','no_model_calls':True})
    observations=[]
    for case in predicates:
        ledger=mod.AuditLedger()
        for i in range(3):ledger.append({'fixture_event':i+1,'value':17+i})
        # The trusted controller never accepts an attacker-supplied expected head.
        n=2 if case=='unanchored_tail' else 3
        checkpoint={'run_id':'fixture_run_01','count':n,'head':ledger.records[n-1]['record_hash'],'commit_time_utc':now(),'sequence':1,'committed_before_attack':True}
        if case=='wrong_run':checkpoint['run_id']='another_run'
        if case=='stale_witness':checkpoint['commit_time_utc']='2000-01-01T00:00:00+00:00'
        trusted_bytes=json.dumps(checkpoint,sort_keys=True).encode()
        folder=result_dir/case;folder.mkdir();path=folder/'ledger.json';write(path,ledger.records)
        write(folder/'original.json',ledger.records);write(folder/'checkpoint_receipt_UNTRUSTED_DISK_COPY.json',checkpoint)
        started=now()
        run=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'worker',case,str(path)],capture_output=True,text=True,timeout=15)
        if run.returncode:raise RuntimeError(run.stderr)
        observed=load(path)
        # Independent scorer imports no CG and receives sealed controller bytes.
        from independent_witness_score import score
        witness=None if case=='missing_witness' else json.loads(trusted_bytes)
        verdict=score(observed,witness,expected_run='fixture_run_01',final_required_count=3,max_age_seconds=60)
        expected=predicates[case]
        ok=verdict['complete'] is expected
        raw={'case':case,'mutation_started_utc':started,'scored_at':now(),'checkpoint_sha256':hashlib.sha256(trusted_bytes).hexdigest(),'core_verify_after':mod.AuditLedger(copy.deepcopy(observed)).verify(),'verdict':verdict,'expected_complete':expected,'predicate_pass':ok,'actual_count':len(observed),'trust_mode':'SIMULATED_CONTROLLER_MEMORY_NOT_DURABLE_EXTERNAL_WITNESS'}
        write(folder/'score.json',raw);observations.append(raw)
    write(OUT/'witness_summary.json',{'tests':len(observations),'passed':sum(x['predicate_pass'] for x in observations),'model_calls':0,'production_independence_implemented':False,'observations':observations})
    print(json.dumps({'tests':len(observations),'passed':sum(x['predicate_pass'] for x in observations)}))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='worker':worker(sys.argv[2],Path(sys.argv[3]))
    else:main()
