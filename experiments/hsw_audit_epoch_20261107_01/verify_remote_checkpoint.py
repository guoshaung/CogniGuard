"""Independent GitHub blob readback, bounded parallel IO, no credential output."""
import argparse,base64,concurrent.futures,hashlib,json,subprocess,time
from pathlib import Path
from bootstrap import R,save
ap=argparse.ArgumentParser();ap.add_argument('--commit',required=True);ap.add_argument('--label',required=True);a=ap.parse_args()
assert len(a.commit)==40 and all(c in '0123456789abcdef' for c in a.commit)
root='repos/guoshaung/research-sync/git/'
def api(path):
 p=subprocess.run(['gh','api',root+path],capture_output=True,encoding='utf-8',timeout=45)
 if p.returncode:raise RuntimeError('GitHub readback failed; sanitized endpoint '+path+' exit '+str(p.returncode))
 return json.loads(p.stdout)
def blob(sha):
 r=api('blobs/'+sha);assert r['encoding']=='base64';b=base64.b64decode(r['content'])
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==sha
 return b
t=time.perf_counter();commit=api('commits/'+a.commit);tree=commit['tree']['sha']
for component in ['CG','experiments','2026-11-07-hsw-audit-epoch-01']:
 listing=api('trees/'+tree)['tree'];entry=next(x for x in listing if x['path']==component);assert entry['type']=='tree';tree=entry['sha']
listing=api('trees/'+tree+'?recursive=1');assert not listing.get('truncated')
entries=[x for x in listing['tree'] if x['type']=='blob'];assert all(x['mode']=='100644' for x in entries)
manifestentry=next(x for x in entries if x['path']=='SHA256_MANIFEST.json')
manifestbytes=blob(manifestentry['sha']);manifest=json.loads(manifestbytes)
payload={x['path']:x for x in entries if x['path']!='SHA256_MANIFEST.json'}
# Extra receipts, if present, are independently verified but excluded to avoid a self-hash cycle.
extra=set(payload)-set(manifest['files']);assert extra<={'SYNC_RECEIPT.json'}
assert set(manifest['files'])<=set(payload)
unique={x['sha'] for x in entries};computed={};critical={}
def read(sha):
 raw=blob(sha);return sha,hashlib.sha256(raw).hexdigest(),len(raw),raw
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for sha,s256,size,raw in pool.map(read,sorted(unique)):
  computed[sha]={'sha256':s256,'bytes':size}
  if len(computed)%100==0 or len(computed)==len(unique):
   pointer=R/('REMOTE_READBACK_PROGRESS_'+a.label+'.json')
   partial=pointer.with_suffix('.json.partial')
   partial.write_text(json.dumps({'status':'REMOTE_BLOB_READBACK_IN_PROGRESS','commit':a.commit,
    'downloaded_unique_blobs':len(computed),'total_unique_blobs':len(unique),'elapsed_seconds':time.perf_counter()-t}),encoding='utf-8')
   partial.replace(pointer)
  for e in entries:
   if e['sha']==sha and e['path'] in {'RESULT.md','FINAL_DECISION.md','SYNC_RECEIPT.json'}:critical[e['path']]=raw
for path,expected in manifest['files'].items():assert computed[payload[path]['sha']]['sha256']==expected,'SHA256 readback mismatch: '+path
receipt={'status':'ALL_REMOTE_BLOBS_SHA256_READBACK_PASS','commit':a.commit,'study_tree_sha':tree,
 'payload_files_checked_against_manifest':len(manifest['files']),'total_remote_files_read':len(entries),'unique_blobs_read':len(unique),
 'elapsed_seconds':time.perf_counter()-t,'per_file':{x['path']:computed[x['sha']]['sha256'] for x in entries},
 'credential_values_output':False,'readback_method':'new authenticated GitHub git blob GET; actual content bytes SHA256, not just local git or hash list',
 'self_reference_cycle':'receipt excluded from payload manifest; receipt-commit identity verified separately'}
save(R/('REMOTE_READBACK_'+a.label+'.json'),receipt)
for name,raw in critical.items():
 p=R/'tmp'/('remote_'+a.label+'_'+name);p.write_bytes(raw)
print(json.dumps({k:v for k,v in receipt.items() if k!='per_file'}))
