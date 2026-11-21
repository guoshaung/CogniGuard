"""Publish only new aggregate evidence; no students, personal paths or label rows."""
from pathlib import Path
import json,hashlib,subprocess,shutil,re,csv
P=Path(__file__).parent;ROOT=P.parents[1];REPO=ROOT/'.tmp/research-sync-strong-20261019-01'
DEST='CG/experiments/2026-10-20-mmfopd-utility-privacy-v3-01'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):
    q=subprocess.run(['git',*args],cwd=REPO,capture_output=True)
    if q.returncode:raise RuntimeError(q.stderr.decode('utf8',errors='replace'))
    return q.stdout
def save(n,obj):(P/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    validation=json.loads((P/'validation.json').read_text());assert validation['status']=='PASSED'
    for lock in ['phaseB_lock.json','phaseC_lock.json']:
        assert all(sha((P/n).read_bytes())==h for n,h in json.loads((P/lock).read_text())['sources'].items())
    assert git('remote','get-url','origin').decode().strip()=='https://github.com/guoshaung/research-sync.git'
    if git('status','--porcelain'):raise RuntimeError('sync checkout must be clean')
    git('pull','--ff-only','origin','main')
    if (REPO/DEST).exists():raise RuntimeError('Do not overwrite historical evidence')
    (P/'.gitattributes').write_text('* -text\n',encoding='utf8');files=[]
    for p in sorted(P.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name in ['evidence_manifest.json','sync_receipt.json']:continue
        private='_LOCAL' in p.name;rel=p.relative_to(P).as_posix()
        if not private and p.suffix in ['.md','.json','.csv','.py','.txt']:
            s=p.read_text(encoding='utf-8-sig')
            if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',s):raise RuntimeError('literal credential in '+rel)
            absolute_pattern=r'(?i)[A-Z]:[\\/](?:Users|pycharm|aaaaa)[\\/]|/'+r'(?:Users|home/[^/\s]+)'+r'/'
            if re.search(absolute_pattern,s):raise RuntimeError('personal absolute path in '+rel)
            if p.suffix=='.json':
                obj=json.loads(s)
                def audit(v):
                    if isinstance(v,dict):
                        if any(k in v for k in ['student','student_id','payload','wire','target_score','gender_F_truth','disability_Y_truth']):raise RuntimeError('individual record in '+rel)
                        for x in v.values():audit(x)
                    elif isinstance(v,list):
                        for x in v:audit(x)
                audit(obj)
            if p.suffix=='.csv':
                with p.open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f)
                    assert not ({'student','student_id','target_score','gender_F_truth','disability_Y_truth'}&set(reader.fieldnames))
        files.append({'path':rel,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size,'local_only':private})
    for n,expected in [('mmfopd_v3_ablation.csv',90),('mmfopd_v3_privacy_utility.csv',364)]:
        with (P/n).open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==expected
    save('evidence_manifest.json',{'classification':'EXPLORATORY_TRAIN_DEV_ONLY','decision':'PIVOT','files':files,
        'privacy':'No individual student rows, targets, attribute truths, probabilities or replies; no personal absolute paths or keys. Aggregate attribute metrics and train-derived model parameters only.',
        'raw_data_synced':False,'production_or_history_edits':False,'independent_test_run':False,
        'method_aliases_not_independent_samples':True,'predeclared_constraints':{'epsilon':1.,'delta':.20,'token_cap':64}})
    public=[]
    for x in files:
        if x['local_only']:continue
        p=P/x['path'];assert sha(p.read_bytes())==x['sha256'];dest=REPO/DEST/x['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);public.append(x)
    dest=REPO/DEST/'evidence_manifest.json';shutil.copyfile(P/'evidence_manifest.json',dest);public.append({'path':'evidence_manifest.json','sha256':sha(dest.read_bytes())})
    parent=git('rev-parse','HEAD').decode().strip();git('add','--',DEST);git('add','--renormalize','--',DEST)
    staged=git('diff','--cached','--name-only').decode().splitlines();assert staged and all(x.startswith(DEST+'/') for x in staged)
    git('-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add frozen MM-FOPD v3 interface repair and constrained projection negative results')
    commit=git('rev-parse','HEAD').decode().strip();git('push','origin','HEAD:main');git('fetch','origin','main');tip=git('rev-parse','origin/main').decode().strip();git('merge-base','--is-ancestor',commit,tip)
    verified=[]
    for x in public:
        digest=sha(git('show','origin/main:'+DEST+'/'+x['path']));assert digest==x['sha256']==sha((P/x['path']).read_bytes())
        verified.append({'path':x['path'],'sha256':digest,'identical':True})
    assert git('ls-remote','origin','refs/heads/main').decode().split()[0]==tip
    receipt={'status':'SYNCED_VERIFIED','repository':'guoshaung/research-sync','path':DEST,'parent_commit':parent,'commit':commit,'remote_verified_tip':tip,
        'files_verified':len(verified),'local_only_excluded':sum(x['local_only'] for x in files),'server_head_verified':True,'verification':verified,
        'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
    save('sync_receipt.json',receipt);print(json.dumps({k:v for k,v in receipt.items() if k!='verification'},indent=2))

if __name__=='__main__':main()
