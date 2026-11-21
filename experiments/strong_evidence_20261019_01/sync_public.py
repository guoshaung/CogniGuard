"""Allowlisted research-sync delivery; never stage the CogniGuard working tree."""
from pathlib import Path
import json,hashlib,subprocess,shutil,re
P=Path(__file__).parent;ROOT=P.parents[1]
REPO=ROOT/'.tmp/research-sync-strong-20261019-01'
DEST='CG/experiments/2026-10-19-mmfopd-c2rag-strong-01'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args):
 p=subprocess.run(['git',*args],cwd=REPO,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode('utf8',errors='replace'))
 return p.stdout
if git('remote','get-url','origin').decode().strip()!='https://github.com/guoshaung/research-sync.git':raise RuntimeError('wrong target')
pending=git('status','--porcelain').decode().splitlines()
if any(not row.startswith('?? '+DEST+'/') for row in pending):raise RuntimeError('target checkout has unrelated changes')
git('pull','--ff-only','origin','main');parent=git('rev-parse','HEAD').decode().strip()
manifest=json.loads((P/'evidence_manifest.json').read_text(encoding='utf8'))
files=[]
for x in manifest['files']:
 if x['local_only']:continue
 source=P/x['path']
 if sha(source.read_bytes())!=x['sha256']:raise RuntimeError('local manifest drift: '+x['path'])
 if source.name.endswith('_LOCAL.json') or source.name in ['.env','student-mat.csv','student-por.csv','source.zip']:raise RuntimeError('private file')
 if source.suffix in ['.json','.md','.py','.txt','.csv','.patch']:
  text=source.read_text(encoding='utf-8-sig')
  if re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):raise RuntimeError('credential-like literal in '+x['path'])
 target=REPO/DEST/x['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);files.append(x)
target=REPO/DEST/'evidence_manifest.json';shutil.copyfile(P/'evidence_manifest.json',target);files.append({'path':'evidence_manifest.json','sha256':sha(target.read_bytes()),'bytes':target.stat().st_size})
git('add','--',DEST)
git('add','--renormalize','--',DEST)
changed=git('diff','--cached','--name-only').decode().splitlines()
if not changed or any(not x.startswith(DEST+'/') for x in changed):raise RuntimeError('stage scope mismatch')
git('-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add real offline MM-FOPD and C2-RAG evidence with equal-budget controls')
commit=git('rev-parse','HEAD').decode().strip()
git('push','origin','HEAD:main')
git('fetch','origin','main');tip=git('rev-parse','origin/main').decode().strip()
git('merge-base','--is-ancestor',commit,tip)
verification=[]
for x in files:
 data=git('show','origin/main:'+DEST+'/'+x['path']);digest=sha(data)
 if digest!=x['sha256']:raise RuntimeError('remote byte mismatch '+x['path'])
 verification.append({'path':x['path'],'sha256':digest,'identical':True})
receipt={'status':'SYNCED_VERIFIED','repository':'guoshaung/research-sync','path':DEST,'parent_commit':parent,'commit':commit,'remote_verified_tip':tip,'files':len(files),'local_only_files_excluded':sum(x['local_only'] for x in manifest['files']),'raw_statistics_verified':['mm/summary.json','mm/attacks.json','rag/results.json','rag_controls/results.json','composition_audit/rows.json'],'byte_verification':verification,'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in receipt.items() if k!='byte_verification'},ensure_ascii=False,indent=2))
