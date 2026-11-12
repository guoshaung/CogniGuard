from common_adjusted import *
import base64
r=read(O/'P1P2_PUSH_PENDING_VERIFY.json');s=W/'var/tmp/eval02_sync_20261112';repo='repos/guoshaung/research-sync'
def api(p):return json.loads(subprocess.check_output(['gh','api',repo+'/'+p]))
ref=api('git/ref/heads/'+r['branch']);assert ref['object']['sha']==r['commit'];tree=subprocess.check_output(['git','-C',str(s),'rev-parse',r['commit']+':'+r['path']],text=True).strip();remote=api('git/trees/'+tree+'?recursive=1');assert not remote.get('truncated');blobs={x['path']:x['sha'] for x in remote['tree'] if x['type']=='blob'};src=O/'publication_P1N10_P2';checks=[]
for p in src.rglob('*'):
 if not p.is_file():continue
 bb=p.read_bytes();rel=p.relative_to(src).as_posix();assert blobs[rel]==hashlib.sha1(b'blob '+str(len(bb)).encode()+b'\0'+bb).hexdigest();checks.append(rel)
readback=[]
for rel in ['RESULT.md','figure_counts.json','per_item.csv','INDEPENDENT_VALIDATION.json','FILE_MANIFEST.json']:
 obj=api('git/blobs/'+blobs[rel]);bb=base64.b64decode(obj['content']);assert bb==(src/rel).read_bytes();readback.append(dict(path=rel,sha256=hashlib.sha256(bb).hexdigest()))
put(O/'SYNC_RECEIPT_P1N10_P2.json',dict(**r,verified=True,remote_files=len(checks),critical_readback=readback,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));print('VERIFIED',r['commit'],len(checks))
