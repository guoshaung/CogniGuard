"""Independent stdlib-only observer; does not call CG verify or import runtime."""
import json,hashlib
from datetime import datetime,timezone
def score(records,witness,*,expected_run,final_required_count,max_age_seconds):
    previous='GENESIS';valid=True
    for r in records:
        body={k:v for k,v in r.items() if k!='record_hash'}
        h=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if body.get('previous_hash')!=previous or h!=r.get('record_hash'):valid=False;break
        previous=h
    def result(complete,reason):return {'chain_consistent':valid,'complete':complete,'reason':reason}
    if not valid:return result(False,'chain_inconsistent')
    if witness is None:return result(None,'missing_witness')
    if witness['run_id']!=expected_run:return result(False,'run_mismatch')
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(witness['commit_time_utc'])).total_seconds()
    if age<0 or age>max_age_seconds:return result(None,'stale_or_future_witness')
    count=witness['count']
    if len(records)<count:return result(False,'committed_tail_missing')
    anchored=records[count-1]['record_hash'] if count else 'GENESIS'
    if anchored!=witness['head']:return result(False,'committed_head_mismatch')
    if count!=final_required_count or len(records)!=count:return result(None,'unanchored_window_or_missing_final_commit')
    return result(True,'matches_trusted_checkpoint_under_simulated_assumptions')
