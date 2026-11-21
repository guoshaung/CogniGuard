"""Synchronize only the sanitized new evidence subtree and verify remote bytes."""
from pathlib import Path
import json,hashlib,subprocess,shutil,re
P=Path(__file__).parent;ROOT=P.parents[1];REPO=ROOT/'.tmp/research-sync-strong-20261019-01';DEST='CG/experiments/2026-10-19-aligned-content-01'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):
 p=subprocess.run(['git',*args],cwd=REPO,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode('utf8',errors='replace'))
 return p.stdout
if git('remote','get-url','origin').decode().strip()!='https://github.com/guoshaung/research-sync.git':raise RuntimeError('wrong remote')
if git('status','--porcelain'):raise RuntimeError('checkout not clean')
git('pull','--ff-only','origin','main');parent=git('rev-parse','HEAD').decode().strip()
if (REPO/DEST).exists():raise RuntimeError('fresh remote subtree required')
manifest=json.loads((P/'evidence_manifest.json').read_text(encoding='utf8'));files=[]
for x in manifest['files']:
 if x['local_only']:continue
 source=P/x['path'];blob=source.read_bytes()
 if sha(blob)!=x['sha256']:raise RuntimeError('manifest drift '+x['path'])
 if source.name.endswith('_LOCAL.json') or source.name=='trace_public.json':raise RuntimeError('per-record private trace')
 if source.suffix in ['.json','.md','.py','.txt','.csv']:
  t=source.read_text(encoding='utf-8-sig')
  if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',t):raise RuntimeError('credential literal in '+x['path'])
 target=REPO/DEST/x['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);files.append(x)
target=REPO/DEST/'evidence_manifest.json';shutil.copyfile(P/'evidence_manifest.json',target);files.append({'path':'evidence_manifest.json','sha256':sha(target.read_bytes())})
git('add','--',DEST);git('add','--renormalize','--',DEST)
changed=git('diff','--cached','--name-only').decode().splitlines()
if not changed or any(not n.startswith(DEST+'/') for n in changed):raise RuntimeError('stage scope')
git('-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add aligned MM repair ablations and visible-content risk failure audit')
commit=git('rev-parse','HEAD').decode().strip();git('push','origin','HEAD:main');git('fetch','origin','main');tip=git('rev-parse','origin/main').decode().strip();git('merge-base','--is-ancestor',commit,tip)
verified=[]
for x in files:
 blob=git('show','origin/main:'+DEST+'/'+x['path']);digest=sha(blob)
 if digest!=x['sha256']:raise RuntimeError('remote byte mismatch '+x['path'])
 verified.append({'path':x['path'],'sha256':digest,'identical':True})
receipt={'status':'SYNCED_VERIFIED','repository':'guoshaung/research-sync','path':DEST,'parent_commit':parent,'commit':commit,'remote_verified_tip':tip,'files_verified':len(files),'local_only_excluded':sum(x['local_only'] for x in manifest['files']),'verification':verified,'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='verification'},indent=2))
