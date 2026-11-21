"""Recompute published frozen inputs in a NEW isolated workspace; no downloads."""
from pathlib import Path
import argparse,shutil,subprocess,sys,json,gzip,hashlib,os
P=Path(__file__).parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',required=True);ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
    root=Path(args.workspace).resolve()
    if root.exists():raise RuntimeError('Refuse overwrite: choose a new workspace')
    deps=P/'dependencies'
    if not deps.exists():raise RuntimeError('Use the published package with dependency snapshots')
    root.mkdir(parents=True);bench=root/'experiments/synthetic_replay';bench.mkdir(parents=True)
    for path in P.glob('*.py'):shutil.copy2(path,bench/path.name)
    for name in ['frozen','data']:
        shutil.copytree(P/name,bench/name)
    for name in ['final_freeze.json','fopd_config.json','development_protocol.json','strict_attention_supplement_lock.json']:
        shutil.copy2(P/name,bench/name)
    for path in deps.rglob('*'):
        if path.is_file():
            target=root/path.relative_to(deps);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    lock=json.loads((bench/'final_freeze.json').read_text())
    for name,h in lock['sources'].items():assert hashlib.sha256((bench/name).read_bytes()).hexdigest()==h,name
    for name,h in lock['external_dependencies'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
    if args.prepare_only:
        print('PREPARED_FROZEN_REPLAY_WORKSPACE');return
    replay_env=os.environ.copy();replay_env['PYTHONHASHSEED']='20261020'
    for script,phase in [('evaluate.py','train'),('evaluate.py','test'),('attacks.py','test'),('strict_attention_audit.py','train'),('strict_attention_audit.py','test')]:
        subprocess.run([sys.executable,str(bench/script),phase],cwd=root,env=replay_env,check=True)
    compared={}
    for phase in ['train','test']:
        def content(path):
            with gzip.open(path,'rb') as f:return hashlib.sha256(f.read()).hexdigest()
        a=content(P/f'var/results/{phase}/raw_rows.jsonl.gz');b=content(bench/f'var/results/{phase}/raw_rows.jsonl.gz');assert a==b,phase;compared[phase]=a
    old=json.loads((P/'attacks_test/metrics.json').read_text());new=json.loads((bench/'attacks_test/metrics.json').read_text());assert len(old)==len(new)
    drift=max(abs(a[k]-b[k]) for a,b in zip(old,new) for k in ['AUC','BA','Accuracy'])
    (bench/'public_replay_verification.json').write_text(json.dumps({'wire_and_metrics_raw_equal':True,'uncompressed_result_sha256':compared,'attack_max_metric_drift':drift,'interpretation':'published-input replay, not a new independent test'},indent=2))
    print('PUBLIC_REPLAY_COMPLETED',drift)

if __name__=='__main__':main()
