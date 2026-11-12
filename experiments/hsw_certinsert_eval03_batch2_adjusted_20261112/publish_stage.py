from common_adjusted import *
import shutil,re,base64
stage=sys.argv[1];src=O/('publication_'+stage);s=W/'var/tmp/eval02_sync_20261112';branch='codex/hsw-eval03-adjusted-batch02-20261112';rel='CG/experiments/2026-11-12-hsw-certinsert-eval03-lite/batch02-adjusted/'+stage
secrets=[(W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/development_round01/restricted/key.bin').read_bytes(),(W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/frozen_comparison09/restricted/kgw_key.txt').read_bytes()]
for p in src.rglob('*'):
 if p.is_file():
  bb=p.read_bytes();assert not any(k in bb or k.hex().encode() in bb for k in secrets);assert not re.search(rb'sk-[A-Za-z0-9_-]{24,}',bb);assert not re.search(rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?$',bb)
if stage=='P6':
 f=read(O/'P6/key_stress/RESULT.json');rr=[json.loads(x) for x in (O/'P6/key_stress/PER_KEY.jsonl').read_text().splitlines()]
 for m in ['CertInsert','RC']:
  for a,v in f['aggregate'][m].items():assert v['k']==sum(x['counts'][m][a] for x in rr)==sum(x[a] for x in f['per_text'][m].values());assert v['n']==sum(x['n'] for x in rr)
def git(*args):return subprocess.check_output(['git','-c','core.longpaths=true','-C',str(s),*args]).decode().strip()
assert git('branch','--show-current')==branch;assert all(p.startswith(rel+'/') for p in git('diff','--cached','--name-only').splitlines());base=git('rev-parse','HEAD');dst=s/rel;
if dst.exists():
 assert all((dst/p.relative_to(src)).read_bytes()==p.read_bytes() for p in src.rglob('*') if p.is_file())
else:shutil.copytree(src,dst)
git('read-tree',base);git('add','--',rel);assert all(p.startswith(rel+'/') for p in git('diff','--cached','--name-only').splitlines());tree=git('write-tree','--missing-ok');commit=git('commit-tree',tree,'-p',base,'-m','Archive adjusted Batch02 '+stage);git('update-ref','HEAD',commit,base);git('push','origin',branch)
def api(p):return json.loads(subprocess.check_output(['gh','api','repos/guoshaung/research-sync/'+p]))
assert api('git/ref/heads/'+branch)['object']['sha']==commit;tt=api('git/trees/'+git('rev-parse',commit+':'+rel)+'?recursive=1');assert not tt.get('truncated');bb={x['path']:x['sha'] for x in tt['tree'] if x['type']=='blob'};n=0
for p in src.rglob('*'):
 if p.is_file():
  b=p.read_bytes();assert bb[p.relative_to(src).as_posix()]==hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();n+=1
checks=[]
for name in ['RESULT.md','figure_counts.json','per_item.csv','FILE_MANIFEST.json']:
 b=base64.b64decode(api('git/blobs/'+bb[name])['content']);assert b==(src/name).read_bytes();checks.append(dict(path=name,sha256=hashlib.sha256(b).hexdigest()))
put(O/('SYNC_RECEIPT_'+stage+'.json'),dict(commit=commit,branch=branch,path=rel,verified=True,files=n,readback=checks,secret_scan_PASS=True));print('VERIFIED',commit,n)

