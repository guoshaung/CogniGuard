"""Add post-package verification artifacts without changing any experimental record."""
from pathlib import Path
import json,hashlib,shutil,sys
P=Path(__file__).parent;D=Path(sys.argv[1]).resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((D/'manifest.json').read_text())
for name,row in manifest['files'].items():assert sha(D/name)==row['sha256'],name
for path in P.iterdir():
    if path.is_file() and path.suffix in ['.py','.json','.md','.csv'] and path.name not in ['sync_receipt.json','package_validation.json']:
        shutil.copy2(path,D/path.name)
(D/'.gitignore').write_text('__pycache__/\n*.py[cod]\n',encoding='ascii')
manifest['files']={p.relative_to(D).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(D.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts and p.suffix!='.pyc'}
manifest['portability_verification']={'published_cases':12,'method_budget_recomputations':504,'fixed_pythonhashseed':20261020,'exact_wire_fields_tokens_equal':True,'full_secondary_replay_executed':False,'initial_unset_hashseed_failure_retained':True}
(D/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
validation=json.loads((P/'package_validation.json').read_text());validation.update(published_files=len(manifest['files'])+1,published_bytes=sum(x['bytes'] for x in manifest['files'].values()),portability_computations_equal=504)
(P/'package_validation.json').write_text(json.dumps(validation,indent=2),encoding='utf8');print(validation)
