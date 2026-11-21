from pathlib import Path
import json,hashlib,shutil
P=Path(__file__).parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
if (P/'development_protocol.json').exists():raise RuntimeError('No overwrite')
old=ROOT/'experiments/datasets/mmfopd_v3_suite/mixed_math_suite/student_profile/data_expanded'
files=[ROOT/'experiments/mmfopd_v3'/x for x in ['expand_profiles.py','baselines.py','runner.py','graph.py']]+[ROOT/'experiments/dataset_builders/build_math_datasets.py']+[old/x for x in ['profiles.jsonl','student_questions.jsonl','learning_events.jsonl']]+[ROOT/'protection/student_profile/src/fopd'/x for x in ['profile_selector.py','orthogonal_decoder.py','task_attention.py','fopd_metrics.py']]+[ROOT/'experiments/results/mmfopd_v3_test_supplement_v2'/x for x in ['manifest.json','summary.csv','rows.csv']]+[ROOT/'experiments/results/ablation_expanded_test_v2/fopd_component_ablation_summary.csv']
save('preservation.json',{p.relative_to(ROOT).as_posix():sha(p) for p in files})
frozen=P/'frozen';frozen.mkdir()
for name in ['profile_selector.py','orthogonal_decoder.py','task_attention.py']:
    source=(ROOT/'protection/student_profile/src/fopd'/name).read_text(encoding='utf8')
    source=source.replace('protection.student_profile.src.fopd.orthogonal_decoder','_synfrozen.orthogonal_decoder').replace('protection.student_profile.src.fopd.task_attention','_synfrozen.task_attention')
    (frozen/('original_'+name)).write_text(source,encoding='utf8')
    if name=='profile_selector.py':
        source=source.replace('self.use_bottleneck = bool(components.get("use_bottleneck", True))','self.use_bottleneck = bool(components.get("use_bottleneck", True))\n        self.use_taskslot = bool(components.get("use_taskslot", True))')
        source=source.replace('(not self.use_orthogonal or records[idx].sensitivity <= self.sensitivity_threshold)','(records[idx].sensitivity <= self.sensitivity_threshold)')
        source=source.replace('(not self.use_orthogonal or item.record.sensitivity <= self.sensitivity_threshold)','(item.record.sensitivity <= self.sensitivity_threshold)')
        source=source.replace('        selected_ids = {item.record.record_id for item in result}\n        baseline_relevant', '        if not self.use_taskslot:\n            return sorted(result, key=lambda x: x.score, reverse=True)[: self.top_k]\n        selected_ids = {item.record.record_id for item in result}\n        baseline_relevant',1)
        source=source.replace('        if self.use_bottleneck:\n            distinct_types', '        if self.use_taskslot:\n            distinct_types',1)
    (frozen/name).write_text(source,encoding='utf8')
b=(ROOT/'experiments/mmfopd_v3/baselines.py').read_text(encoding='utf8').replace('protection.student_profile.src.fopd.profile_selector','_synfrozen.profile_selector')
(frozen/'baselines.py').write_text(b,encoding='utf8')
save('development_protocol.json',{'status':'DEVELOPMENT_BEFORE_TEST','seed_roster':2026102011,'seed_tasks':{'dev':2026102012,'train':2026102013,'test':2026102014},'students':{'train':2500,'dev':500,'test':2000},'tasks':{'train':5000,'dev':1000,'test':10000},'types':8,'structural_families_per_type':4,'difficulties':['explicit','ambiguous','missing','dependency','sensitive_proxy'],'budgets':[2,3,5],'token_cap':96,'main_budget':3,'synthetic_only':True,'common_candidate_pool':True,'FullProfile':'budgeted original-order truncation; separate unbounded feasibility oracle','method_styles':'original extractive/proxy adapters, not official LaMP/GPG/PAPILLON/PrivacyFunnel or actual LLM calls','DP_limit':'exponential-style stochastic selection epsilon1, raw-value release has no DP guarantee','MM_version':'frozen original field selector, not numerical privacy v2/v3; experiment-only strict independent component flags and common MM gate.7','truth':'32 executable teaching decision programs with instrumented dynamic input trace, independent of selector score; executable synthetic task completion, not human/LLM teaching efficacy','attackers':'LR C1 balanced liblinear maxiter2000; RF64 depth6 minleaf5 balanced_subsample; seed20261020; actual parsed wire + public task features only; public-only calibration; student-disjoint train/test','bootstrap':'500 student clusters,500 structural-family clusters,500 two-way student xfamily pigeonhole draws; no iid task interval','freeze_after_dev':'No test generation/evaluation before frozen final hashes. No difficulty resampling based on results. Synthetic benchmark exploratory, structural families shared across splits.'})
print('Snapshot and development protocol created')
