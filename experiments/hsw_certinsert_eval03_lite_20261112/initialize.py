"""Metadata only: no scoring, selection tests, model loads or network."""
from pathlib import Path
import json,hashlib,datetime,subprocess
E=Path(__file__).resolve().parent;W=E.parents[1]
O=W/'var/results/hsw-st/certinsert_eval03_lite_20261112/run01'
E1=W/'var/results/hsw-st/certinsert_eval_20261111_01/run01'
E2=W/'var/results/hsw-st/certinsert_eval_20261111_02/run01'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf8') as f:json.dump(x,f,indent=2,ensure_ascii=False)
def main():
 O.mkdir(parents=True,exist_ok=False)
 task=Path('C:/Users/guoshuang/Downloads/TASK_EVAL03_LITE.md');(E/'TASK_AUTHORITY.md').write_bytes(task.read_bytes())
 baseline=read(E1/'EVAL_FREEZE.json');files={'method':E2/'FROZEN_METHOD.json','parser':W/'experiments/hsw_certinsert_eval_20261111_02/structure_adapter.py','domain_null':E2/'DOMAIN_FREQUENCIES.json','original_generation_freeze':E1/'EVAL_FREEZE.json'}
 freeze=dict(task='HSW-CERTINSERT-EVAL-03-LITE',phase='BEFORE_DATA_INVENTORY_AND_GENERATION',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),seed=2026111203,task_sha256=sha(task),frozen_files={k:dict(path=str(v),sha256=sha(v)) for k,v in files.items()},targets=dict(T4=400,T5=200,in_domain=1000,general_reused=300,costly_T4=100),generation=baseline['generation'],prompts={k:baseline[k] for k in ['T3_prompt','rewrite_prompt','attacks']},KGW=baseline['KGW'],model7b=baseline['model7b'],model7b_parts=baseline['model7b_parts'],retry=0,paid_API=0,max_GPU_seconds=172800,stop_target_p=.001,detector_p=.01,random_key_stress=1000,stress_alpha=[.001,.01,.05],source_rng='SHA256(seed|purpose|id)',RC='global-only key k4; random permitted token-safe positions; structure mask off; same remaining constraints',bootstrap_seed=2026111204,bootstrap_replicates=2000,calibration_status_inherited=read(E2/'CALIBRATION_RESULT.json')['status'],domain_null_adoption='Explicit EVAL03 task revision, not retroactive EVAL02 modification',paper_plot_script='AWAITING_ACTUAL_PATH',sample_freeze='REQUIRED before scoring/generation')
 put(E/'EVAL_FREEZE.json',freeze);put(O/'STATE.json',dict(stage='PROTOCOL_FROZEN_NEEDS_COMMIT',generated=0,GPU_seconds=0,next='Commit protocol and inventory script; inventory actual disjoint licensed sources.'))
 put(O/'WORKTREE.json',dict(root=str(W),branch=subprocess.check_output(['git','-C',str(W),'branch','--show-current'],text=True).strip(),HEAD=subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip(),historical_results_read_only=True))
 print('metadata frozen',O)
if __name__=='__main__':main()
