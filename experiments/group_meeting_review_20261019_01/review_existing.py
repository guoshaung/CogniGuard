"""Read existing artifacts only. No project imports, models, scoring or network."""
from pathlib import Path
import csv, json, hashlib, random, statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
evidence = set()
def read(p):
    p = ROOT / p
    evidence.add(p)
    return p.read_text(encoding='utf-8-sig')
def js(p): return json.loads(read(p))
def csvs(p): return list(csv.DictReader(read(p).splitlines()))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

sources = [
'experiments/mmfopd_v3/runner.py','experiments/mmfopd_v3/baselines.py',
'protection/student_profile/src/fopd/profile_selector.py',
'protection/student_profile/src/fopd/orthogonal_decoder.py',
'protection/student_profile/src/fopd/task_attention.py',
'protection/student_profile/src/fopd/context_card.py',
'experiments/mmfopd_uci/runner.py','experiments/mmfopd_uci/README.md',
'experiments/mmfopd_uci/alignment_probe.py',
'experiments/three_layer_refinement/privacy.py',
'experiments/focused/privacy_attack/runner.py','experiments/focused/privacy_attack/population.py',
'experiments/c2rag_v3/core.py','experiments/c2rag_v3/evaluator.py',
'experiments/c2rag_v3/baselines.py','experiments/c2rag_v3/fact_release.py',
'experiments/c2rag_v3/evidence_release.py','experiments/c2rag_v3/generator.py',
'experiments/three_layer_refinement/rag_model.py','experiments/three_layer_refinement/round_summary.py',
'experiments/three_layer_refinement/watermark.py','experiments/attacks/watermark_attacks.py',
'experiments/text_watermark/DEVELOPMENT_REPORT_V1.md',
'experiments/text_watermark/source_anchor_specificity_audit.py',
'protection/audit_trace/src/watermark_rewriter.py',
'protection/audit_trace/src/watermark_logits_processor.py',
'protection/audit_trace/src/watermark_detector.py',
'experiments/stage1_e_causal_review_20261019_01/sanitized_delivery/causal_review.md',
'experiments/research_handoff_20261019_01/audit_integrity_review.md',
'docs/current_c2rag_audit.md',
]
for p in sources: read(p)
summary = {}
for name in ['uci_math_20261013_01','uci_taskslot_20261016_01','rag_expand120_20261016_01',
             'rag_fact_model_20261016_02','round120_20261016_01','watermark_context_20261016_02',
             'text_watermark_source_anchor_audit_20261013']:
    summary[name] = js(f'experiments/results/{name}/summary.json')
    lock=ROOT/f'experiments/results/{name}/protocol-lock.json'
    if lock.exists(): read(str(lock.relative_to(ROOT)))
for p in ['manifest.json','per_seed.json','summary.json']:
    read('experiments/results/privacy_attack/20261012T105541140694Z/'+p)
mmroot='experiments/results/mmfopd_v3_test_supplement_v2/'
rows=csvs(mmroot+'rows.csv'); read(mmroot+'manifest.json'); read(mmroot+'summary.csv')
mm={m:[r for r in rows if r['method']==m] for m in sorted({r['method'] for r in rows})}
summary['mm_supplement_structure']={'columns':list(rows[0]),'row_count':len(rows),
    'methods':{m:{'rows':len(rs),'distinct_students':len({r.get('student_id') for r in rs}),
                    'distinct_requests':len({r.get('request_id') for r in rs})} for m,rs in mm.items()}}
cr='experiments/c2rag_v3/results/development_matrix_fixed_full_deterministic/'
crows=csvs(cr+'aggregated_metrics.csv')
summary['c2_selected_aggregate']=[r for r in crows if r['method'] in
    ['full_c2rag_v3','c2rag_without_cumulative_budget','c2rag_without_reconstruction_history',
     'advanced_rag_no_defense','semantic_similarity_guard'] and r['metric'] in
    ['reconstruction_success','normal_session_availability','mean_source_attribution_accuracy','generation_calls']]
for p in ['freeze_manifest.json','run_manifest.json','model_manifest.json','evaluator_manifest.json',
          'external_baseline_manifest.json','development_pilot_report.md']:
    read(cr+p)
# Inspect existing raw artifacts without exposing passages or individual students.
for p in ['raw_results.jsonl','session_metrics.jsonl','failure_cases.jsonl','linked_group_metrics.jsonl']:
    rr=[json.loads(x) for x in read(cr+p).splitlines() if x.strip()]
    summary['c2_'+p]={'rows':len(rr),'columns':list(rr[0]) if rr else []}
    if p=='session_metrics.jsonl':
        summary['c2_session_unique']={k:len({str(r.get(k)) for r in rr}) for k in
            ['case_id','session_id','link_group']}
    if p=='raw_results.jsonl':
        from collections import Counter
        summary['c2_raw_metadata']={'unique_target_resource_ids':len({r['target_resource_id'] for r in rr}),
            'rounds_per_method_session_histogram':dict(Counter(Counter((r['method'],r['session_id']) for r in rr).values())),
            'model_calls':sum(r['generation_calls'] for r in rr),
            'hidden_label_access_true':sum(bool(r['hidden_label_access']) for r in rr)}
    if p=='linked_group_metrics.jsonl':
        summary['c2_linked_unique_nonempty_groups']=len({str(r['link_group']) for r in rr if r['link_group']})
raw_normal={}
for folder in ['rag_expand_real_20261016_01','rag_expand_real_20261016_02']:
    for p in sorted((ROOT/'experiments/results'/folder).glob('normal-*.json')):
        row=js(str(p.relative_to(ROOT)))['metrics']
        raw_normal[(row['case_id'],row['arm'])]=row
summary['rag_raw_counts']={'question_count':len({k[0] for k in raw_normal}),
    'unique_rows':len(raw_normal)}
delta=[]
for q in sorted({k[0] for k in raw_normal}):
    a=raw_normal.get((q,'Raw-RAG'));b=raw_normal.get((q,'FactRelease-C2RAG'))
    if a and b: delta.append(b['answer_token_f1']-a['answer_token_f1'])
summary['rag_raw_paired_f1']={'n':len(delta),'mean':statistics.mean(delta)}
wm='experiments/results/watermark_context_20261016_02/'
arms={}
for p in sorted((ROOT/wm).glob('??-context?.json')):
    r=js(str(p.relative_to(ROOT)))['metrics']
    if r['split']=='test': arms.setdefault(r['arm'],[]).append(r)
rng=random.Random(20261019)
def boot(vals):
    bs=sorted(statistics.mean(rng.choices(vals,k=len(vals))) for _ in range(10000))
    return [bs[249],bs[9749]]
summary['watermark_source_resampling']={}
for arm,rs in arms.items():
    vals=[statistics.mean(a['detected'] for a in r['attacks']) for r in rs]
    summary['watermark_source_resampling'][arm]={'source_n':len(rs),'attacks_per_source':5,
        'adr':statistics.mean(vals),'source_cluster_percentile_95':boot(vals),
        'note':'Exploratory corpus-conditional resampling; no population robustness guarantee.'}
for p in ['dev-selection-lock.json','clean-calibration-lock.json']:read(wm+p)
summary['source_hash_checks']={}
for folder in ['watermark_context_20261016_02','rag_expand_real_20261016_01','rag_expand_real_20261016_02','uci_math_20261013_01']:
    lock=js(f'experiments/results/{folder}/protocol-lock.json')
    hashes=lock.get('source_code_sha256',{})
    summary['source_hash_checks'][folder]={k:sha(ROOT/k)==v for k,v in hashes.items() if (ROOT/k).is_file()}
for folder in ['text_watermark_selective12','text_watermark_qwen05b_long12','text_watermark_sweet12']:
    for p in (ROOT/'experiments/results'/folder).glob('*/metrics_summary.csv'):read(str(p.relative_to(ROOT)))
for p in (ROOT/'experiments/results/text_watermark_selective12').glob('*/attack_results.csv'):read(str(p.relative_to(ROOT)))
# Hash all inspected raw model records, never export their content.
for folder in ['rag_expand_real_20261016_01','rag_expand_real_20261016_02']:
    for p in (ROOT/'experiments/results'/folder).glob('attack-*.json'): evidence.add(p)
manifest=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)}
          for p in sorted(evidence)]
(OUT/'evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'derived_review_statistics.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:summary[k] for k in ['mm_supplement_structure','c2_session_unique','rag_raw_counts',
    'rag_raw_paired_f1','watermark_source_resampling','c2_selected_aggregate']},ensure_ascii=False,indent=2))
print('manifest_files',len(manifest))
