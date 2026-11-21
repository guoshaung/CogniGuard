"""Sanitized new subtree only; no individual records; verify remote Git object bytes."""
from pathlib import Path
import json,hashlib,subprocess,shutil,re,csv
P=Path(__file__).parent;ROOT=P.parents[1]
REPO=ROOT/'.tmp/research-sync-strong-20261019-01'
DEST='CG/experiments/2026-10-19-mmfopd-orthogonal-privacy-v2-01'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):
    q=subprocess.run(['git',*args],cwd=REPO,capture_output=True)
    if q.returncode:raise RuntimeError(q.stderr.decode('utf8',errors='replace'))
    return q.stdout
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    assert json.loads((P/'validation.json').read_text())['status']=='PASSED'
    assert json.loads((P/'completion.json').read_text())['status']=='COMPLETED_DEV_ONLY'
    assert git('remote','get-url','origin').decode().strip()=='https://github.com/guoshaung/research-sync.git'
    if git('status','--porcelain'):raise RuntimeError('sync checkout is not clean')
    git('pull','--ff-only','origin','main')
    if (REPO/DEST).exists():raise RuntimeError('Refuse overwrite of historical subtree')
    (P/'.gitattributes').write_text('* -text\n',encoding='utf8')
    files=[]
    for source in sorted(P.rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts or source.name in ['evidence_manifest.json','sync_receipt.json']:continue
        rel=source.relative_to(P).as_posix();private='_LOCAL' in source.name
        if not private and source.suffix in ['.json','.md','.py','.txt','.csv']:
            text=source.read_text(encoding='utf-8-sig')
            if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):raise RuntimeError('literal credential in '+rel)
            if source.suffix=='.json':
                obj=json.loads(text)
                def inspect(value):
                    if isinstance(value,dict):
                        if 'student' in value or 'payload' in value or 'wire' in value:raise RuntimeError('individual-record JSON in '+rel)
                        for z in value.values():inspect(z)
                    elif isinstance(value,list):
                        for z in value:inspect(z)
                inspect(obj)
        files.append({'path':rel,'sha256':sha(source.read_bytes()),'bytes':source.stat().st_size,'local_only':private})
    for name,expected in [('mmfopd_v2_ablation.csv',66),('mmfopd_v2_privacy_utility.csv',300)]:
        with (P/name).open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==expected
    save('evidence_manifest.json',{'classification':'EXPLORATORY_TRAIN_DEV_ONLY','decision':'PIVOT','files':files,
        'individual_records_local_only':True,'raw_dataset_synced':False,'core_or_history_edits':False,
        'scope':'new experimental source, frozen settings, aggregate metrics, train-derived transform parameters, public metadata, figures, reference license',
        'gate':'0/12 passed; no independent test; no posthoc parameter changes'})
    manifest=json.loads((P/'evidence_manifest.json').read_text(encoding='utf8'));public=[]
    for x in manifest['files']:
        if x['local_only']:continue
        source=P/x['path'];assert sha(source.read_bytes())==x['sha256']
        target=REPO/DEST/x['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);public.append(x)
    target=REPO/DEST/'evidence_manifest.json';shutil.copyfile(P/'evidence_manifest.json',target)
    public.append({'path':'evidence_manifest.json','sha256':sha(target.read_bytes())})
    parent=git('rev-parse','HEAD').decode().strip()
    git('add','--',DEST);git('add','--renormalize','--',DEST)
    changed=git('diff','--cached','--name-only').decode().splitlines()
    assert changed and all(x.startswith(DEST+'/') for x in changed)
    git('-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add frozen MM-FOPD privacy projection development ablation and negative results')
    commit=git('rev-parse','HEAD').decode().strip();git('push','origin','HEAD:main');git('fetch','origin','main')
    tip=git('rev-parse','origin/main').decode().strip();git('merge-base','--is-ancestor',commit,tip)
    verified=[]
    for x in public:
        digest=sha(git('show','origin/main:'+DEST+'/'+x['path']))
        if digest!=x['sha256']:raise RuntimeError('remote byte mismatch: '+x['path'])
        if digest!=sha((P/x['path']).read_bytes()):raise RuntimeError('local drift: '+x['path'])
        verified.append({'path':x['path'],'sha256':digest,'identical':True})
    remote_head=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    assert remote_head==tip
    receipt={'status':'SYNCED_VERIFIED','repository':'guoshaung/research-sync','path':DEST,'parent_commit':parent,
        'commit':commit,'remote_verified_tip':tip,'server_head_verified':True,'files_verified':len(verified),
        'local_only_excluded':sum(x['local_only'] for x in files),'verification':verified,
        'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
    save('sync_receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='verification'},indent=2))

if __name__=='__main__':main()
