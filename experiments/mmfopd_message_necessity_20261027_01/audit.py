"""Read-only source/cohort inventory; all new outputs stay in this experiment."""
from pathlib import Path
import sys,json,hashlib,subprocess,datetime,collections,platform
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(ROOT))
from core.paths import PROJECT_ROOT,MODELS_DIR
assert ROOT==PROJECT_ROOT
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    out=P/'audit.json'
    if out.exists():raise RuntimeError('No overwrite')
    cfg=json.loads((P/'config.json').read_text())
    source=ROOT/cfg['cache'];rows=json.loads(source.read_text());tr=[r for r in rows if r['split']=='train'];dv=[r for r in rows if r['split']=='dev']
    assert len(tr)==1337 and len(dv)==473
    assert {r['student'] for r in tr}.isdisjoint({r['student'] for r in dv})
    assert {r['presentation'] for r in rows}=={'2013J'}
    files=['AGENTS.md','CONTRIBUTING.md','core/paths.py','experiments/README.md','protection/student_profile/README.md',cfg['cache'],cfg['tokenizer'],
      'experiments/oulad_dynamic_20261019_01/design.py','experiments/oulad_dynamic_20261019_01/build_data.py','experiments/oulad_dynamic_20261019_01/acquisition.json','experiments/oulad_dynamic_20261019_01/author_metadata.json',
      'experiments/oulad_dynamic_20261019_01/dev_data/availability.json','experiments/oulad_dynamic_20261019_01/README.md',
      'experiments/mmfopd_orthogonal_privacy_v2_20261019_01/protocol.json','experiments/mmfopd_orthogonal_privacy_v2_20261019_01/mmfopd_v2_failure_cases.md',
      'experiments/mmfopd_utility_privacy_v3_20261020_01/protocol.json','experiments/mmfopd_utility_privacy_v3_20261020_01/mmfopd_v3_interface_audit.md','experiments/mmfopd_utility_privacy_v3_20261020_01/group_meeting_mmfopd_v3.md',
      'protection/student_profile/src/fopd/profile_selector.py','protection/student_profile/src/fopd/orthogonal_decoder.py','protection/student_profile/src/fopd/task_attention.py']
    import numpy,sklearn,tokenizers,scipy
    status=subprocess.run(['git','status','--porcelain','-uno'],cwd=ROOT,check=True,capture_output=True).stdout
    cohort={sp:{'students':len({r['student'] for r in rr}),'snapshots':len(rr),'attributes':{a:{'positive_students':sum(next(x[a] for x in rr if x['student']==sid) for sid in {r['student'] for r in rr}),'negative_students':sum(1-next(x[a] for x in rr if x['student']==sid) for sid in {r['student'] for r in rr}),'positive_snapshots':sum(r[a] for r in rr),'negative_snapshots':sum(1-r[a] for r in rr)} for a in ['gender_F','disability_Y']}} for sp,rr in [('train',tr),('dev',dv)]}
    obj={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_tracked_dirty_lines':len(status.splitlines()),'git_status_sha256':hashlib.sha256(status).hexdigest(),
      'classification':'EXPLORATORY_USED_DEVELOPMENT','schema':{'safe_values':list(tr[0]['values']),'additional_charged_context':['module','cutoff','days_to_due'],'Public_personal_information':[]},'cohort':cohort,
      'sources_sha256':{n:sha(ROOT/n) for n in files},'input_cache_bytes':source.stat().st_size,'model_weight_reads':0,'old_test_cache_reads':0,'R31':{'status':'BLOCKED_MISSING_SOURCE','search':'local filenames/content, cached Git tree, GitHub R31 and R31 MM-FOPD searches returned no report'},
      'runtime':{'python':platform.python_version(),'executable_LOCAL':sys.executable,'numpy':numpy.__version__,'sklearn':sklearn.__version__,'scipy':scipy.__version__,'tokenizers':tokenizers.__version__,'virtualenv_tokenizers':'MISSING; existing system environment used, no install'},'deployment_Public_or_RBAC_confirmed':False}
    out.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
    freeze={'phase':'PROTOCOL_FROZEN_BEFORE_ANY_NEW_FIT','timestamp_utc':obj['timestamp_utc'],'sha256':{n:sha(P/n) for n in ['PROTOCOL.md','config.json','README.md','audit.py']},'sources_sha256':obj['sources_sha256'],'dev_metrics_inspected':False}
    (P/'protocol_freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf8')
    print(json.dumps({'status':'AUDIT_AND_PROTOCOL_FREEZE_COMPLETE','cohort':cohort,'git_commit':obj['git_commit'],'R31':'BLOCKED_MISSING_SOURCE'}))
if __name__=='__main__':main()
