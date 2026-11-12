from initialize import *
import urllib.request,concurrent.futures,time,xml.etree.ElementTree as ET
plan=read(E/'ADDITIONAL_SOURCE_FREEZE_02.json'); ledger=O/'ADDITIONAL_FETCH_02.jsonl'
done={json.loads(l)['url'] for l in ledger.read_text().splitlines()} if ledger.exists() else set()
rows=[]
for s in plan['sources']:
 for m in s['modules']:
  rows.append(dict(repo=s['repo'],revision=s['revision'],module=m,url=f"https://raw.githubusercontent.com/openstax/{s['repo']}/{s['revision']}/modules/{m}/index.cnxml"))
def fetch(r):
 t=time.monotonic();r=dict(r,status='FAILED',attempts=1)
 try:
  with urllib.request.urlopen(r['url'],timeout=30) as q:b=q.read(2097153)
  assert len(b)<=2097152
  ET.fromstring(b);p=O/'source_cache'/r['repo']/(r['module']+'.cnxml');p.parent.mkdir(exist_ok=True)
  with p.open('xb') as f:f.write(b)
  r.update(status='FETCHED',path=str(p),sha256=sha(p),bytes=len(b))
 except Exception as e:r['error']=type(e).__name__+': '+str(e)
 r['seconds']=time.monotonic()-t
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for i,r in enumerate(pool.map(fetch,[r for r in rows if r['url'] not in done])):
  with ledger.open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n')
  if i%25==0:print(i,r['status'],flush=True)
rr=[json.loads(l) for l in ledger.read_text().splitlines()]
print('FINISHED',len(rr),sum(r['status']=='FETCHED' for r in rr),flush=True)
