"""Explicit allowlist export; never exports private source or raw stack/logs."""
import json,hashlib,re,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    preservation=json.loads((OUT/'preservation_after.json').read_bytes())
    if not preservation['unchanged']:raise RuntimeError('Existing work changed; do not sync')
    h=json.loads((OUT/'historical_evidence_audit.json').read_bytes())
    w=json.loads((OUT/'witness_summary.json').read_bytes())
    s=json.loads((OUT/'S00-12.score.json').read_bytes())
    raw=json.loads((OUT/'S00-12/raw.json').read_bytes())
    summary={'version':'research_handoff_20261019_01','created_utc':datetime.now(timezone.utc).isoformat(),'research_sync_read_base':'4ca4c00ffbdfc26a5bd355c6ce16469d28c52437','local_head':'d01953234add03996cb9200af3ff02c9592697e7','decision':'ANALYZE','stage1':'NOT_EXECUTED','stage1_n':0,'stage1_value':None,'real_model_calls':0,'local_model_inference':0,'new_risk_algorithms':0,'production_changes':0,'preserved_files':preservation['files_verified'],'preservation_unchanged':True,'v2_frozen_files_verified':h['v2_frozen_files_checked'],'historic_source_files_verified':h['historic_source_files_checked'],'old_scores':h['scores'],'witness':w,'supplement_S00_12':{'separate_run':True,'old_status':'NOT_EXECUTED','new_status':s['status'],'checks':len(s['checks']),'checks_passed':sum(c['pass'] for c in s['checks']),'failure_codes':s['failure_codes'],'observed_sink_writes':len(raw['observed_sink_writes']),'native_sink_events':len(raw['native_report'].get('sink_events',[])),'script_backend_requests':len(raw['backend_requests']),'new_model_calls':0,'observer_verification':s['observer_verification'],'raw_sha256':sha(OUT/'S00-12/raw.json'),'score_sha256':sha(OUT/'S00-12.score.json'),'truth_sha256':s['truth_sha256'],'sqlite_sha256':sha(OUT/'S00-12/native_audit.sqlite3'),'interpretation':'unmediated channel scope limitation; not mediated algorithm failure'},'remaining':'Independent durable witness, sink scope/mediation, asset authorization, independent two-person truth and freeze. No Stage1 authorization.'}
    save(OUT/'experiment_summary.json',summary)
    delivery=OUT/'sanitized_delivery';delivery.mkdir(exist_ok=False)
    allow=['research_handoff.md','environment_audit.md','audit_integrity_review.md','stage1_readiness.md','research_decision.md','experiment_summary.json','witness_protocol.json','supplement_protocol.json']
    for name in allow:shutil.copyfile(OUT/name,delivery/name)
    suspicious=[]
    patterns=[r'C:[/\\]Users[/\\](?!WINDOWS_USER_HOME)',r'(?i)\bsk-[A-Za-z0-9_-]{12,}',r'(?i)github_pat_[A-Za-z0-9_]+',r'(?i)ghp_[A-Za-z0-9]+',r'-----BEGIN .*PRIVATE KEY-----',r'(?i)(?:api_key|password|secret)\s*[=:]\s*[\"\x27][^\"\x27]{8,}']
    for p in delivery.iterdir():
        text=p.read_text(encoding='utf-8')
        for pattern in patterns:
            if re.search(pattern,text):suspicious.append({'file':p.name,'pattern':pattern})
    if suspicious:raise RuntimeError('Sensitive pattern found; review locally')
    receipt={'allowlist':allow,'pattern_scan_findings':suspicious,'content_review':'Reports and self-authored mechanical fixture summaries only; no CG core source, raw process stacks, full preservation/git inventory, model text, teaching assets, student records, credentials or databases. Agent content review before commit; no independent human review claimed.','source_hashes':{p.name:sha(p) for p in delivery.iterdir()},'preservation':{'verified_files':preservation['files_verified'],'unchanged':True},'limits':'Pattern scan complements explicit allowlist/content review; not a universal DLP guarantee.'}
    save(delivery/'redaction_receipt.json',receipt)
    save(delivery/'package_manifest.json',{'files_sha256':{p.name:sha(p) for p in sorted(delivery.iterdir())},'delivery_scope':'Only reports and experiment summaries, original raw evidence stays local','new_remote_directory':'CG/reviews/2026-10-19-windows-handoff-01/','old_records_modified':False})
    print(json.dumps({'files':len(list(delivery.iterdir())),'sensitive_pattern_findings':0,'summary_status':s['status'],'witness_predicates':str(w['passed'])+'/'+str(w['tests'])}))
if __name__=='__main__':main()
