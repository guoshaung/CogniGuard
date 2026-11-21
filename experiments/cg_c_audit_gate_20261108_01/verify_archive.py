"""Repeatable read-only verification; no baseline replay or model calls."""
import hashlib
import json
from pathlib import Path
from check_results import verify_witness

H=Path(__file__).resolve().parent; ROOT=H.parents[1]
def main():
    freeze=json.loads((H/'FREEZE_MANIFEST.json').read_text('utf8'))
    mismatches=[r['path'] for r in freeze['files'] if hashlib.sha256((H/r['path']).read_bytes()).hexdigest()!=r['sha256']]
    inv=json.loads((H/'history_inventory.json').read_text('utf8'))
    old=[r['path'] for r in inv['files'] if hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
    rows=[json.loads(s) for s in (H/'runs/initial/results.jsonl').read_text('utf8').splitlines()]
    certs=0
    for r in rows:
        x=json.loads((H/r['path']).read_text('utf8'))
        for name,out in r['methods'].items():
            labels={verify_witness(x,w) for w in out.get('witnesses',[])}
            want={'VIOLATION_PROVEN':{True},'COMPLIANT_PROVEN':{False},'INDETERMINATE':{True,False},'EVIDENCE_INVALID':set()}[out['verdict']]
            assert labels==want,(r['input_id'],name,labels,want)
            certs+=1
    assert not mismatches and not old,(mismatches,old)
    print(json.dumps({'status':'VERIFIED','frozen_files':len(freeze['files']),'historical_files':len(inv['files']),
                      'audit_views':len(rows),'certificate_checks':certs,'new_formal_replays':0,'GPU':0,'API':0}))

if __name__=='__main__':main()
