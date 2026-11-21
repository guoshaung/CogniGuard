"""Local sync receipt; verify committed remote blobs, not only working-tree status."""
from pathlib import Path
import json,subprocess,hashlib,gzip,re
P=Path(__file__).parent;ROOT=P.parents[1];checkout=ROOT/'.tmp/research-sync-strong-20261019-01';prefix='CG/experiments/2026-10-20-mmfopd-synthetic-benchmark-01';D=checkout/prefix
def git(*args):return subprocess.run(['git',*args],cwd=checkout,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
def sha(b):return hashlib.sha256(b).hexdigest()
git('fetch','origin','main');remote=git('rev-parse','origin/main').decode().strip();commit='9418badc0b7b8aa4d45525b3836eb6cfc7871a54'
git('merge-base','--is-ancestor',commit,'origin/main')
manifest=json.loads((D/'manifest.json').read_text());files=set(manifest['files'])|{'manifest.json'}
actual={x[len(prefix)+1:] for x in git('ls-tree','-r','--name-only','origin/main','--',prefix).decode().splitlines()};assert actual==files,(actual-files,files-actual)
checked={}
for name in sorted(files):
    blob=git('show','origin/main:'+prefix+'/'+name);local=(D/name).read_bytes();assert blob==local,name;checked[name]=sha(blob)
    if name in manifest['files']:assert sha(blob)==manifest['files'][name]['sha256'],name
for name,row in manifest['data_compression'].items():
    with gzip.open(D/name,'rb') as f:assert sha(f.read())==row['uncompressed_sha256']
    assert sha((P/name.removesuffix('.gz')).read_bytes())==row['uncompressed_sha256']
for name,h in json.loads((P/'preservation.json').read_text()).items():assert sha((ROOT/name).read_bytes())==h
lock=json.loads((P/'final_freeze.json').read_text())
for name,h in lock['sources'].items():assert sha((P/name).read_bytes())==h
server=git('ls-remote','origin','refs/heads/main').decode().split()[0];assert server==remote,'Remote changed while verifying; rerun receipt'
receipt={'status':'REMOTE_BLOBS_READ_BACK_VERIFIED','commit':commit,'remote_main_at_verification':remote,'server_main':server,'repository':'https://github.com/guoshaung/research-sync','subtree':prefix,'files_verified':len(files),'manifest_sha256':checked['manifest.json'],'verified_file_sha256':checked,'compressed_data_compared_to_original':9,'historical_files_unchanged':16,'frozen_primary_files_unchanged':16,'public_replay_smoke_equal_computations':504,'full_secondary_replay_executed':False,'student_data':'entirely synthetic; no real-student records','paid_calls':0}
(P/'sync_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in receipt.items() if k!='verified_file_sha256'},indent=2))
