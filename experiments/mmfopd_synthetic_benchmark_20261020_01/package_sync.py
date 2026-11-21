"""Allowlisted publication of wholly SYNTHETIC benchmark evidence. No Git mutation."""
from pathlib import Path
import hashlib,json,gzip,shutil,sys,re,collections
P=Path(__file__).parent;ROOT=P.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    dest=Path(sys.argv[1]).resolve()
    if dest.exists():raise RuntimeError('No overwrite: publication destination exists')
    lock=json.loads((P/'final_freeze.json').read_text());old=json.loads((P/'preservation.json').read_text())
    for name,h in lock['sources'].items():assert sha(P/name)==h,name
    for name,h in lock['external_dependencies'].items():assert sha(ROOT/name)==h,name
    for name,h in old.items():assert sha(ROOT/name)==h,name
    dest.mkdir(parents=True);compressed={};failed=[]
    for path in sorted(P.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or 'LOCAL' in path.name:continue
        rel=path.relative_to(P)
        if rel.parts[0].startswith('retained_development'):
            failed.append({'path':rel.as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,'publication':'retained locally; superseded development artifact'});continue
        if path.name in ['sync_receipt.json','package_validation.json','development_failures.json']:continue
        target=dest/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if rel.parts[0]=='data' and path.suffix=='.jsonl':
            target=target.with_suffix('.jsonl.gz')
            with path.open('rb') as source,target.open('wb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as out:shutil.copyfileobj(source,out)
            with gzip.open(target,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==sha(path)
            compressed[target.relative_to(dest).as_posix()]={'uncompressed_sha256':sha(path),'uncompressed_bytes':path.stat().st_size}
        else:shutil.copy2(path,target)
    for name in lock['external_dependencies']:
        target=dest/'dependencies'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    # JSON is a YAML subset; this contains ONLY the frozen FOPD parameters.
    target=dest/'dependencies/protection/student_profile/configs/default.yaml';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/'fopd_config.json',target)
    model='assets/models/qwen2.5-0.5b-instruct-7ae55760'
    for name in ['config.json','tokenizer_config.json','tokenizer.json','vocab.json','merges.txt','LICENSE','README.md']:
        target=dest/'dependencies'/model/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/model/name,target)
    save(dest/'development_failures.json',{'phase':'development only, no test resampling','retained_artifacts':failed,'engine_import_attempt':'retained_engine_import_attempt_01.py included','changes':'see historical_audit.md and pretest_amendment.json','all_final_primary_and_historical_hashes_verified':True})
    (dest/'.gitattributes').write_text('* -text\n',encoding='ascii')
    (dest/'.gitignore').write_text('__pycache__/\n*.py[cod]\n',encoding='ascii')
    # No real student/OULAD files or old mathematical question text are copied.
    personal=re.compile(r'[A-Za-z]:[\\/]'+''.join(['Us','ers'])+r'[\\/]|/ho'+'me/|/Us'+'ers/')
    secret=re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----')
    checked=0
    for path in dest.rglob('*'):
        if not path.is_file() or 'models' in path.parts or path.suffix in ['.png','.npz']:continue
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf8') as f:content=f.read()
        else:content=path.read_text(encoding='utf-8-sig')
        assert not personal.search(content),str(path.relative_to(dest));assert not secret.search(content),str(path.relative_to(dest));checked+=1
    manifest={'classification':'WHOLLY_SYNTHETIC_EXPLORATORY','primary_test_episodes':10000,'synthetic_students_total':5000,'structural_families':32,'data_compression':compressed,'files':{p.relative_to(dest).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(dest.rglob('*')) if p.is_file()},'exclusions':['computed features_LOCAL caches','superseded large development attempts (hashes retained)','old mathematical problem texts','all real-student caches','model weights'],'no_production_or_historical_file_changes':True,'privacy_scan_files_checked':checked}
    save(dest/'manifest.json',manifest)
    save(P/'package_validation.json',{'status':'PACKAGED_AND_HASH_VERIFIED','published_files':len(manifest['files'])+1,'published_bytes':sum(x['bytes'] for x in manifest['files'].values()),'historical_files_verified':len(old),'frozen_primary_files_verified':len(lock['sources']),'compressed_data_files':len(compressed),'privacy_scan_files_checked':checked,'real_student_records_published':0,'model_weights_published':False})
    print(json.dumps(json.loads((P/'package_validation.json').read_text()),indent=2))
if __name__=='__main__':main()
