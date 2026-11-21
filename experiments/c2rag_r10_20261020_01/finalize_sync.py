"""Resume publication after retained CRLF assertion failure; no experiments rerun."""
from pathlib import Path
import subprocess,json,hashlib,re,sys
sys.stdout.reconfigure(encoding='utf8');P=Path(__file__).resolve().parent;ROOT=P.parents[1]
R=ROOT/'.tmp/c2rag-review-sync-20261019';B=ROOT/'.tmp/c2rag-remote-readback-20261019-01';D='CG/experiments/2026-10-20-c2rag-r10-multiasset-01'
def git(r,*args):return subprocess.run(['git',*args],cwd=r,capture_output=True,check=True).stdout
def sha(x):return hashlib.sha256(x).hexdigest()
names=[n for n in git(R,'diff','--cached','--name-only','-z').decode().split('\0') if n]
assert names and all(n.startswith(D+'/') or n=='CG/decision_log.md' for n in names)
assert git(R,'show',':CG/decision_log.md').startswith(git(R,'show','HEAD:CG/decision_log.md'))
for n,h in json.loads((P/'protocol.json').read_text(encoding='utf8'))['hashes'].items():assert sha((P/n).read_bytes())==h,n
for n,h in json.loads((P/'preservation_before.json').read_text(encoding='utf8')).items():assert sha((ROOT/n).read_bytes())==h,n
old=json.loads((P/'manifest.json').read_text(encoding='utf8'));files=[]
for f in sorted(P.rglob('*')):
 if not f.is_file() or '__pycache__' in f.parts or 'local_sources' in f.parts:continue
 if f.name.endswith('_private.json') or f.name in ['manifest.json','sync_receipt.json']:continue
 rel=f.relative_to(P).as_posix();blob=f.read_bytes()
 if f.suffix in ['.py','.json','.md','.csv','.svg','.html']:assert not re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',blob.decode('utf-8-sig')),rel
 dest=R/D/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob);files.append({'path':rel,'bytes':len(blob),'sha256':sha(blob)})
old['files']=files;old['publication_failure_retained']='publication_failure.json';blob=(json.dumps(old,ensure_ascii=False,indent=2)+'\n').encode('utf8')
(P/'manifest.json').write_bytes(blob);(R/D/'manifest.json').write_bytes(blob)
git(R,'add','--',D,'CG/decision_log.md')
for f in files:assert sha(git(R,'show',':'+D+'/'+f['path']))==f['sha256'],f['path']
git(R,'-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m','Add exploratory C2-RAG R10 multiasset constraint baseline evidence and exclusions')
commit=git(R,'rev-parse','HEAD').decode().strip();git(R,'push','origin','HEAD:main')
assert not git(B,'status','--porcelain');git(B,'pull','--ff-only','--quiet','origin','main');git(B,'merge-base','--is-ancestor',commit,'HEAD')
for f in files:assert sha((B/D/f['path']).read_bytes())==f['sha256'],f['path']
assert sha((B/D/'manifest.json').read_bytes())==sha(blob)
remote=git(R,'ls-remote','origin','refs/heads/main').decode().split()[0]
receipt={'status':'REMOTE_AUTHENTICATED_SEPARATE_CHECKOUT_ALL_HASHES_PASS','commit':commit,'remote_head_at_check':remote,'payload_files_verified':len(files),'manifest_sha256':sha(blob),'only_new_subtree_and_append_only_log':True,'anonymous_public_readability':'not asserted','url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+D}
(P/'sync_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt,ensure_ascii=False,indent=2))
