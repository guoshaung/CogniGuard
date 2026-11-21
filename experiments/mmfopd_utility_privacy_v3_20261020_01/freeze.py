"""Freeze a single bounded family before any new fit; preserve prior evidence."""
from pathlib import Path
import json,hashlib,subprocess,shutil
P=Path(__file__).parent;ROOT=P.parents[1];V2=ROOT/'experiments/mmfopd_orthogonal_privacy_v2_20261019_01';OLD=ROOT/'experiments/oulad_dynamic_20261019_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
if (P/'protocol.json').exists():raise RuntimeError('No overwrite')
paths=[OLD/x for x in ['dev_data/snapshots_LOCAL.json','design.py','selection_engine.py','dev_results/summary.json','dev_results/cases_LOCAL.json','dev_results/TrainMI_train_only.json','mmfopd_oulad_report.md']]+[V2/x for x in ['privacy_core.py','run_dev.py','protocol.json','summary_results.json','projection_checks.json','phaseC_gate.json','mmfopd_orthogonal_privacy_v2.md']]+[ROOT/'experiments/mmfopd_projection_diagnosis_20261019_01/mmfopd_projection_diagnosis.md']+[ROOT/'protection/student_profile/src/fopd'/x for x in ['profile_selector.py','orthogonal_decoder.py','task_attention.py']]
save('preservation.json',{p.relative_to(ROOT).as_posix():sha(p) for p in paths})
repo=ROOT/'.tmp/research-sync-strong-20261019-01';checks=[]
for folder,name,local in [('2026-10-19-oulad-dynamic-01','mmfopd_oulad_report.md',OLD/'mmfopd_oulad_report.md'),('2026-10-19-mmfopd-projection-diagnosis-01','mmfopd_projection_diagnosis.md',paths[-4]),('2026-10-19-mmfopd-orthogonal-privacy-v2-01','mmfopd_orthogonal_privacy_v2.md',V2/'mmfopd_orthogonal_privacy_v2.md')]:
    rel='CG/experiments/'+folder+'/'+name;b=subprocess.run(['git','show','origin/main:'+rel],cwd=repo,capture_output=True,check=True).stdout
    assert hashlib.sha256(b).hexdigest()==sha(local)
    checks.append({'path':rel,'sha256':sha(local),'remote_matches_local':True})
save('prior_remote_readback.json',checks)
shutil.copytree(V2/'vendor',P/'vendor',ignore=shutil.ignore_patterns('__pycache__'))
save('reference_sources.json',{'source':'existing v2 vendored official MIT LEACE; no new download','files':{x.relative_to(P).as_posix():sha(x) for x in (P/'vendor').rglob('*') if x.is_file()},'papers':['https://arxiv.org/abs/2004.07667','https://arxiv.org/abs/2306.03819','https://arxiv.org/abs/1402.1774']})
save('protocol.json',{
 'status':'FROZEN_BEFORE_ANY_NEW_FIT','classification':'EXPLORATORY_TRAIN_DEVELOPMENT_ONLY','seed':20261020,
 'cohort':'unchanged2013J train484 students/1337 snapshots; dev166/473; no2014J raw data reads',
 'contexts':'same3 tasks x explicit/ambiguous; all share next-TMA target, not independent teaching interventions',
 'interface':'fixed6 numeric components:3 standardized train-median-imputed value codes h0..h2 +3 explicit missing flags m0..m2; public f=field-index triplet in actual wire, all methods same schema. Mixed codes are not original facts.',
 'source_budget':3,'token_cap':64,'wire_precision':3,'hard_gate':'same13 safe fields, threshold.7; no IDs, sensitive labels or attack predictions in payload',
 'mask_rule':'missing flags never projected, identical handling across methods; missingness is an explicitly retained privacy side channel',
 'B0':'Identity on task-only TFIDF Top3 source fields; B5 task-only selection is exactly this same method, alias not fake independent baseline',
 'B1':'historical role-reward selector, re-encoded through identical6D interface; explicitly historical, no sensitive projection',
 'B2':'v2-style unconstrained covariance orthogonal projector refitted on SAME3 value coordinates, not old26D/3-output result and not retroactive v2 improvement',
 'B3':'INLP intersection-nullspaces, up to3 fixed LinearSVC C1 balanced rounds on4 joint classes, stop only on algebraic rank exhaustion; masks kept',
 'B4':'existing official LEACE float64 affine, no shrinkage/trace constraint, tol1e-10; same3-value input, masks kept',
 'B6_single_candidate':'train-only Ridge teacher defines value coefficient w; residual sensitive crosscov C_res=(I-tt.T)Cov(v,S), t=w/||w||. P_r=I-U_rU_r.T from top left singular directions of C_res, r in{0,1,2}. Exact orthogonal, P_r w=w. No new optimizer/novelty claim.',
 'inner_split':'outer TRAIN students only: sha256(mmfopd-v3-inner:+student_id) mod4==0 for inner validation; all other train students inner fit. Fit encoder, teacher, projection, attackers on inner fit only. Choose rank without outer dev labels; refit chosen rank once on all outer train.',
 'privacy_objective':'inner actual-wire+public RF risk=max across2 attributes of max(0,AUC_release_RF-AUC_public_RF); identical RF budget for each candidate. Minimize subject to constraints, tie1e-12 -> smaller distortion then smaller rank, including Identity r0.',
 'epsilon_MAE_points':1.0,'delta_value_relative_squared_distortion':0.20,
 'constraints':'inner MAE <= same-interfaceIdentity MAE+epsilon AND distortion<=delta AND wire<=64; feasibility is an actual eligibility gate, not a penalty. Final outer-dev constraints rechecked, not assumed from preserving teacher.',
 'PhaseB_gate':'Identity MAE <= cached raw SafeTaskTopK MAE+1.0 in EVERY6 frozen context; exact flags retained, no field-ID ambiguity, same public/release attack visibility. If false stop before PhaseC.',
 'PhaseC_ablations':['V3-rank1','V3-rank2','V3-no-loss-gate (only remove explicit epsilon eligibility; retain teacher-null directions)','V3-no-teacher-protection (only set t-space empty, retain epsilon/delta/rank-selection gates)','NoAtt-Identity (fixed trainMI Top3)','NoAtt-V3 (same candidate, fixed trainMI Top3)','V3-no-projection alias Identity','nonorth-half (I-.5UU.T on selected rank/directions, otherwise same; optional simple reference)'],
 'unconstrained_ablation_note':'B2 removes both teacher protection and explicit feasibility constraints; not a single-factor ablation. no-loss-gate and no-teacher-protection separate those effects.',
 'rank_bound':'only r0/1/2, no adaptive candidates, lambda or epsilon/delta search; no choosing final rank using outer dev.',
 'predictor':'same Ridge alpha10 lsqr, DictVectorizer, StandardScaler(with_mean=False), clip[0,100], refit for every actual representation; teacher is same protocol',
 'attackers':'LR C1 balanced liblinear maxiter2000 and RF64 depth6 minleaf5 balanced_subsample, seed20261020; same train budgets, public-only and actual wire+public; no private internal extras',
 'public':'same course module, cutoff, days_to_due public schedule; field identity triplet also in actual wire; no raw sensitive labels in public',
 'bootstrap':'500 student-cluster resamples, paired MAE/AUC/BA differences conditional on frozen fitted models; not independent snapshots, no multiplicity-adjusted confirmation',
 'PhaseD_gate':'no new test this turn. At least one preregistered context must have nonzero chosen rank, meet epsilon/delta/B and improve RF nonnegative excess>=.02 for>=1 attribute with paired AUC95 upper<0, no other RF AUC or LR AUC worsening>.01; also no simple/INLP/LEACE method satisfies same utility bound with no-greater worst-attribute excess. Otherwise PIVOT; do not tune.',
 'privacy_floor':'If Identity has no positive RF excess, cannot claim incremental improvement from below-public fitted attacks; rational receiver can ignore output.',
 'test_access':False,'paid_calls':0,'data_or_model_downloads':False,'core_or_history_edits':False})
print('FROZEN_V3_BEFORE_FITS; prior reports matched',len(checks))
