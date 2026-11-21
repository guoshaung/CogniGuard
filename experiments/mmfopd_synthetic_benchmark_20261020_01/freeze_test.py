from pathlib import Path
import json,hashlib
P=Path(__file__).parent;ROOT=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if (P/'final_freeze.json').exists():raise RuntimeError('No overwrite')
completion=json.loads((P/'var/results/dev/execution.json').read_text());assert completion['status']=='COMPLETED' and completion['tasks']==1000 and completion['all_candidate_program_correct']==1000
assert completion['dev_full_equivalent_to_snapshot_after_same_budget']==3000
assert json.loads((P/'attacks_dev/execution.json').read_text())['status']=='COMPLETED'
assert not (P/'data/test').exists() and not (P/'data/train').exists()
files=[p for p in P.glob('*.py') if not p.name.startswith('retained_')]+list((P/'frozen').glob('*.py'))+[P/'development_protocol.json',P/'fopd_config.json']
import yaml
assert json.loads((P/'fopd_config.json').read_text())=={'fopd':yaml.safe_load((ROOT/'protection/student_profile/configs/default.yaml').read_text(encoding='utf8'))['fopd']}
lock={'status':'FROZEN_AFTER1000_DEV_BEFORE_TRAIN_TEST_GENERATION','sources':{p.relative_to(P).as_posix():sha(p) for p in files},'development_input_sha256':{p.relative_to(P).as_posix():sha(p) for p in (P/'data/dev').glob('*')},'external_dependencies':{n:sha(ROOT/n) for n in ['protection/common/text_utils.py','protection/common/schemas.py','protection/student_profile/src/fopd/multimodal_profile.py']},'test_count':10000,'no_parameter_changes_from_development_protocol':True,'budget_K':[2,3,5],'token_cap':96,'synthetic_benchmark_only':True}
(P/'final_freeze.json').write_text(json.dumps(lock,indent=2),encoding='utf8');print('FROZEN; no train/test data exists yet')
