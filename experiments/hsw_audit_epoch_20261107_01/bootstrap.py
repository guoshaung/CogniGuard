"""Isolated admission. Does not infer, mutate shared assets, or copy environments."""
from pathlib import Path
import datetime, hashlib, json, os, platform, shutil, subprocess, sys

W = Path(__file__).resolve().parents[2]
E = Path(__file__).resolve().parent
R = W/'var/results/hsw-st/audit_epoch_20261107_01/run01'
OLD = Path('D:/pycharm/CogniGuard')
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p, data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        f.write(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def git(*args):
    return subprocess.check_output(['git','-C',str(W),*args],text=True,encoding='utf-8').strip()

if __name__=='__main__':
    assert W==Path('D:/pycharm/CogniGuard-worktrees/hsw-st')
    assert git('branch','--show-current')=='codex/hsw-st'
    assert not R.exists(), 'first-write-only bootstrap'
    R.mkdir(parents=True)
    for name in ['cache','tmp','logs','raw','inputs','reviews','analysis','literature','private']:
        (R/name).mkdir()
    inherited=[
      'var/results/hsw_r38_auth_transfer_20261103/RESULT.md',
      'var/results/hsw_r39_two_signals_20261103/RESULT.md',
      'var/results/hsw_copyright_transfer01_20261106/FINAL_SHA256_MANIFEST.json',
      'var/results/hsw_copyright_transfer01_status_correction_20261107/STATUS_CORRECTION.md',
      'var/results/hsw_copyright_transfer_rq1_rq3_20261107/EVIDENCE_SHA256.json',
      'var/results/hsw_copyright_transfer_rq1_rq3_20261107/delivery/FINAL_DECISION.md',
      'var/results/hsw_repro02_continuation_20261106/EXECUTION_STATE.md',
      'CONTRIBUTING.md','protection/audit_trace/README.md']
    rows=[{'path':str(OLD/p),'exists':(OLD/p).is_file(),'sha256':digest(OLD/p) if (OLD/p).is_file() else None} for p in inherited]
    rec={'task':'HSW-AUDIT-EPOCH-01','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'actual_root':git('rev-parse','--show-toplevel'),'branch':git('branch','--show-current'),
      'HEAD':git('rev-parse','HEAD'),'pre_write_status':git('status','--short'),
      'worktrees':git('worktree','list','--porcelain'),
      'origin_before':git('remote','get-url','origin'),
      'isolation_difference':'Expected HSW tree/branch absent; created new sparse worktree at expected path from current registered baseline. Shared uncommitted source changes NOT migrated; no backup, no model/venv copies.',
      'precedent_read_only':'D:/pycharm/CogniGuard-worktrees/c2rag/tools/isolation/README.md',
      'precedent_migration_sha256':digest('D:/pycharm/CogniGuard-worktrees/c2rag/var/isolation/migration.json'),
      'first_failed_git_command':'git worktree add from non-repository parent failed before mutation; then used existing registered tree',
      'formal_admin_signature':'NOT_LOCATED; actual filesystem/git isolation verified',
      'result_root':str(R),'shared_assets':'read only absolute paths; bytecode disabled',
      'disk_free':shutil.disk_usage(W).free,'python':sys.executable,'platform':platform.platform(),
      'original_worktree_research_files_written':False,'GPU_calls':0,'paid_API_calls':0}
    save(R/'WORKTREE_CHECK.json',rec);save(R/'HISTORY_INPUTS.json',rows)
    save(R/'STATE.json',{'stage':'S0_ACTIVE','model_attempts':0,'API_calls':0,'GPU_seconds':0,'RQ2':'FROZEN','total_attempt_ceiling':256,'output_budget_bytes':3*2**30})
    save(R/'RUN_MANIFEST.jsonl','')
    save(E/'README.md','''# HSW-AUDIT-EPOCH-01

独立教学材料离平台发行版本关联和历史周期审计。输出位于本工作树var/results/hsw-st/audit_epoch_20261107_01/run01。
本轮固定原文→独立交付改写，不研究连续覆盖必要性，不将关联命中当成许可有效或法律归责。
模型/venv/旧归档只读共享；所有新缓存、临时、原始结果和密钥只写入本工作树。私密材料不发布。
默认零付费、无下载模型、无新云资源；生成/失败/攻击合计上限256，磁盘3GiB。每阶段另冻结更小上限，不要求用满。
''')
    save(E/'ISOLATION.md',json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    save(E/'NEXT_ACTION.md','S0: acquire and pin allowed author material, public MPAC source and methods; S1 lifecycle fixtures; no generation before protocol/input/license freeze.\n')
    print(json.dumps({'status':'ISOLATED_READY','root':str(W),'output':str(R),'old_files_written':False},ensure_ascii=False))
