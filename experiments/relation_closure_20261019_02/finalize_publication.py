"""Append publication-access diagnostics; verify final files via fresh Git clone."""
from pathlib import Path
import hashlib,json,re,subprocess

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
REPO=ROOT/'.tmp/c2rag-review-sync-20261019'
READBACK=ROOT/'.tmp/c2rag-remote-readback-20261019-01'
DEST='CG/experiments/2026-10-19-c2rag-relation-closure-01'
def git(repo,*args):return subprocess.run(['git',*args],cwd=repo,capture_output=True,check=True).stdout
def sha(b):return hashlib.sha256(b).hexdigest()
assert not git(REPO,'status','--porcelain')
git(REPO,'pull','--ff-only','--quiet','origin','main')
parent=git(REPO,'rev-parse','HEAD').decode().strip()
target=REPO/DEST
assert target.is_dir()
old=json.loads((target/'manifest.json').read_text(encoding='utf8'))
files=[]
for f in sorted(P.rglob('*')):
    if not f.is_file() or '__pycache__' in f.parts or 'local_source_snapshots' in f.parts:continue
    if f.name in ['manifest.json','sync_receipt.json','sync_attempts.jsonl']:continue
    data=f.read_bytes();rel=f.relative_to(P).as_posix()
    if f.suffix in ['.py','.json','.md','.csv','.svg']:
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data.decode('utf-8-sig'))
    if f.suffix=='.py':compile(data,str(f),'exec')
    dst=target/rel;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    files.append({'path':rel,'sha256':sha(data),'bytes':len(data)})
manifest={**old,'publication_followup_parent_commit':parent,'files':files,
          'remote_readability':'All files independently read through fresh authenticated Git clone; anonymous raw URL returned404 and is not claimed publicly readable.'}
blob=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8')
(P/'manifest.json').write_bytes(blob);(target/'manifest.json').write_bytes(blob)
git(REPO,'add','--',DEST)
changed=[x for x in git(REPO,'diff','--cached','--name-only','-z').decode().split('\0') if x]
allowed={'manifest.json','sync_public.py','sync_attempt_02_http_failed.json','publication_validation.json','finalize_publication.py'}
assert all(x.startswith(DEST+'/') and x[len(DEST)+1:] in allowed for x in changed),changed
for f in files:assert sha(git(REPO,'show',':'+DEST+'/'+f['path']))==f['sha256']
git(REPO,'-c','user.name=Codex','-c','user.email=codex@localhost','commit','-m',
    'Record anonymous HTTP failure and authenticated fresh-clone verification for C2-RAG evidence')
commit=git(REPO,'rev-parse','HEAD').decode().strip()
git(REPO,'push','origin','HEAD:main')
assert not git(READBACK,'status','--porcelain')
git(READBACK,'pull','--ff-only','--quiet','origin','main')
git(READBACK,'merge-base','--is-ancestor',commit,'HEAD')
for f in files:
    assert sha((READBACK/DEST/f['path']).read_bytes())==f['sha256'],f['path']
assert sha((READBACK/DEST/'manifest.json').read_bytes())==sha(blob)
receipt={'status':'SYNCED_FRESH_AUTHENTICATED_REMOTE_CLONE_VERIFIED','commit':commit,
         'verified_remote_payload_files':len(files),'manifest_verified':True,
         'anonymous_raw_https':'HTTP404 recorded; no anonymous-access claim',
         'old_experimental_files_modified':False,
         'main_result_protocol_sha256':sha((P/'protocol.json').read_bytes()),
         'url':'https://github.com/guoshaung/research-sync/tree/'+commit+'/'+DEST}
(P/'sync_receipt.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps(receipt,ensure_ascii=False))
