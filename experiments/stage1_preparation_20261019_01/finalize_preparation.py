"""Local evidence preservation and exactly-five-report publication staging."""
from pathlib import Path
import json,hashlib,re
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPORTS=['stage1_asset_inventory.md','stage1_annotation_guideline.md','stage1_frozen_protocol.md','stage1_readiness_report.md','research_decision.md']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def append(p,t):
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write(t)
def main():
    previous=json.loads((HERE/'preservation_before.json').read_bytes())
    changed=[name for name,h in previous.items() if not Path(name).is_file() or sha(Path(name))!=h]
    preservation={'checked_utc':datetime.now(timezone.utc).isoformat(),'files_verified':len(previous),'unchanged':not changed,'changed_or_missing':changed}
    save(HERE/'preservation_after.json',preservation)
    if changed:raise RuntimeError('Existing source/history changed; do not publish')
    paths=['experiments/c2rag_v3/core.py','experiments/c2rag_v3/fact_release.py','core/langgraph_runtime/teachers/chain.py','core/langgraph_runtime/teachers/store.py','cogniguard/governance/audit.py','protection/teacher_resource/src/c2rag/exposure_budget.py']
    hashes={p:sha(ROOT/p) for p in paths};save(HERE/'source_hashes.json',hashes)
    frozen=json.loads((HERE/'dry_run/frozen_script_manifest.json').read_bytes())
    freeze_check={name:sha(HERE/name)==h for name,h in frozen['files'].items()}
    protocol_unchanged=sha(HERE/'protocol_candidate.json')==frozen['protocol_sha256']
    if not all(freeze_check[n] for n in ['dryrun_worker.py','independent_contract_verifier.py','run_dryrun.py']) or not protocol_unchanged:raise RuntimeError('Runtime/verifier/protocol changed since rehearsal')
    save(HERE/'development_freeze_integrity.json',{'files':freeze_check,'protocol_unchanged':protocol_unchanged,'prepare_materials_change_reason':'Post-rehearsal inventory schema correction license -> license_id; original inventory preserved; no runtime, source asset or policy changes.'})
    asset_manifest=json.loads((HERE/'asset_manifest.json').read_bytes())
    table='\n\n## 本轮合成资产版本哈希（只摘要，不上传内容）\n\n| 资产 | source SHA256 |\n|---|---|\n'+''.join(f"| {x['asset_id']} v1 SYNTHETIC | `{x['source_sha256']}` |\n" for x in asset_manifest['assets'])
    table+=f"\n本地 asset_manifest.json SHA256：`{sha(HERE/'asset_manifest.json')}`。本地 corrected inventory SHA256：`{sha(HERE/'existing_asset_candidates_v2.json')}`。上述文件不在本轮上传范围。\n"
    append(HERE/'stage1_asset_inventory.md',table)
    coretable='\n\n## 文件保全与关键源码证据\n\n'+f"既有文件 **{len(previous)}份**运行前后SHA256一致；0个缺失/变化。\n\n| 原路径 | SHA256 |\n|---|---|\n"+''.join(f'| {p} | `{h}` |\n' for p,h in hashes.items())
    coretable+=f"\n本地 dryrun_summary.json SHA256：`{sha(HERE/'dryrun_summary.json')}`。protocol_candidate.json SHA256：`{sha(HERE/'protocol_candidate.json')}`。排练时runtime/verifier/runner和协议hash至今一致；prepare_materials仅元数据字段纠正，已单独记录。\n"
    append(HERE/'stage1_readiness_report.md',coretable)
    append(HERE/'stage1_frozen_protocol.md',f"\n\n候选协议SHA256：`{sha(HERE/'protocol_candidate.json')}`；排练前冻结manifest SHA256：`{sha(HERE/'dry_run/frozen_script_manifest.json')}`。这两个文件只本地保留，不将开发冻结误称正式冻结。\n")
    append(HERE/'stage1_annotation_guideline.md',f"\n\n本地资产manifest SHA256：`{sha(HERE/'asset_manifest.json')}`。两位标注者收到的source应逐份核对此manifest，任何改动需新版本。BLANK_adjudication当前仍PENDING，无人工gold hash。\n")
    delivery=HERE/'sanitized_delivery';delivery.mkdir(exist_ok=False)
    findings=[]
    patterns=[r'C:[/\\]Users[/\\](?!WINDOWS_USER_HOME)',r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)',r'-----BEGIN .*PRIVATE KEY-----',r'(?i)(?:api_key|password|secret)\s*[=:]\s*[\"\x27][^\"\x27]{8,}']
    for name in REPORTS:
        blob=(HERE/name).read_bytes();t=blob.decode('utf-8')
        for pattern in patterns:
            if re.search(pattern,t):findings.append(name)
        # Exact bytes; no newline normalization between reviewed package and GitHub.
        with (delivery/name).open('xb') as f:f.write(blob)
    if findings:raise RuntimeError('Sensitive pattern found; no upload')
    save(HERE/'publication_allowlist.json',{'reports':REPORTS,'file_count':len(REPORTS),'sha256':{name:sha(delivery/name) for name in REPORTS},'git_blob_sha':{name:hashlib.sha1(b'blob '+str(len((delivery/name).read_bytes())).encode()+b'\0'+(delivery/name).read_bytes()).hexdigest() for name in REPORTS},'sensitive_pattern_findings':findings,'content_review':'Five descriptive reports only. No synthetic source text, AI answers, annotation files, scripts, detailed logs, full private source, credentials, student records or paid teaching materials. Policy examples are structural summaries only.','repo_checked':{'full_name':'guoshaung/research-sync','visibility':'private','pull':True,'push':True,'read_base':'289f91e69e3788a77292191d65266bb00887ca29'},'remote_directory':'CG/reviews/2026-10-19-stage1-preparation-01/','upload_rule':'If review rejects any upload, stop it immediately; do not retry or change route.'})
    print(json.dumps({'preserved_files':len(previous),'unchanged':True,'reports':REPORTS,'dryrun_runtime_unchanged':True,'sensitive_pattern_findings':findings}))
if __name__=='__main__':main()
