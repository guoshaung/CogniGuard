from pathlib import Path
import json,hashlib,re
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((OUT/'evidence_manifest.json').read_text(encoding='utf-8'))
changed=[r['path'] for r in manifest if sha(ROOT/r['path'])!=r['sha256']]
if changed:raise RuntimeError('Evidence drift: '+str(changed))
report=OUT/'group_meeting_evidence_review.md'
text=report.read_text(encoding='utf-8')
key_paths=[
'protection/student_profile/src/fopd/profile_selector.py',
'protection/student_profile/src/fopd/orthogonal_decoder.py',
'experiments/mmfopd_v3/runner.py','experiments/mmfopd_v3/baselines.py',
'experiments/results/mmfopd_v3_test_supplement_v2/rows.csv',
'experiments/results/mmfopd_v3_test_supplement_v2/manifest.json',
'experiments/results/privacy_attack/20261012T105541140694Z/summary.json',
'experiments/results/uci_math_20261013_01/protocol-lock.json',
'experiments/results/uci_math_20261013_01/summary.json',
'experiments/results/uci_taskslot_20261016_01/summary.json',
'experiments/c2rag_v3/core.py','experiments/c2rag_v3/evaluator.py','experiments/c2rag_v3/fact_release.py',
'experiments/c2rag_v3/results/development_matrix_fixed_full_deterministic/freeze_manifest.json',
'experiments/c2rag_v3/results/development_matrix_fixed_full_deterministic/raw_results.jsonl',
'experiments/c2rag_v3/results/development_matrix_fixed_full_deterministic/session_metrics.jsonl',
'experiments/c2rag_v3/results/development_matrix_fixed_full_deterministic/linked_group_metrics.jsonl',
'experiments/results/rag_expand120_20261016_01/summary.json',
'experiments/results/rag_fact_model_20261016_02/summary.json',
'experiments/results/round120_20261016_01/summary.json',
'experiments/results/watermark_context_20261016_02/protocol-lock.json',
'experiments/results/watermark_context_20261016_02/summary.json',
'experiments/results/text_watermark_source_anchor_audit_20261013/summary.json',
'protection/audit_trace/src/watermark_rewriter.py',
'protection/audit_trace/src/watermark_logits_processor.py',
'experiments/stage1_e_causal_review_20261019_01/sanitized_delivery/causal_review.md',
]
by={r['path']:r for r in manifest}
table='| 相对证据路径 | SHA256 |\n|---|---|\n'+'\n'.join('| `'+p+'` | `'+by[p]['sha256']+'` |' for p in key_paths)
text=text.replace('<!-- EVIDENCE_HASH_TABLE -->',table)
report.write_text(text,encoding='utf-8')
dest=OUT/'sanitized_delivery'
dest.mkdir(exist_ok=True)
# Report was authored without raw records, hostnames, key values or source passages.
sanitized=text.replace('全量本地清单另见 `evidence_manifest.json`','全量清单保留在本地 `evidence_manifest.json`')
patterns={
'credential_material':r'(?i)(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|postgres(?:ql)?://|mysql://)',
'windows_absolute_path':r'[A-Z]:[\\/]',
'email':r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
'secret_assignment':r'(?i)(?:password|api_key|secret_key)\s*[=:]\s*[\x22\x27][^\x22\x27]{8,}',
}
hits={name:len(re.findall(pattern,sanitized)) for name,pattern in patterns.items()}
if any(hits.values()):raise RuntimeError('Sanitization failed: '+str(hits))
target=dest/'group_meeting_evidence_review.md'
target.write_text(sanitized,encoding='utf-8')
receipt={'status':'LOCAL_COMPLETE_UPLOAD_NOT_ATTEMPTED','preserved_evidence_files':len(manifest),
 'changed_evidence_files':changed,'report_sha256':sha(report),'sanitized_sha256':sha(target),
 'sanitized_bytes':target.stat().st_size,'sensitive_scan_hits':hits,
 'manual_scope':'Aggregate metrics, designs, relative evidence paths and hashes only; no raw student rows, source code, source passages or key values.',
 'model_calls':0,'new_defense_experiments':0,
 'destination_repository':'guoshaung/research-sync','destination_path':'CG/reviews/2026-10-19-group-meeting-evidence-01/group_meeting_evidence_review.md'}
(OUT/'local_delivery_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2))
