"""Bounded public-source retrieval; no model/service operations."""
from initialize import *
import urllib.request,concurrent.futures,time,xml.etree.ElementTree as ET
def main():
 rows=read(O/'MISSING_MODULES.json');dest=O/'source_cache';dest.mkdir(exist_ok=True)
 plan=E/'SOURCE_FETCH_FREEZE.json'
 assert plan.exists() and read(plan)['source_manifest_sha256']==sha(O/'MISSING_MODULES.json')
 ledger=O/'SOURCE_FETCH_LEDGER.jsonl';done={x['module'] for x in [json.loads(l) for l in ledger.read_text().splitlines()]} if ledger.exists() else set()
 def fetch(r):
  start=time.monotonic();out=dict(r,status='FAILED',attempts=1)
  try:
   req=urllib.request.Request(r['url'],headers={'User-Agent':'CogniGuard-research-source-audit'})
   with urllib.request.urlopen(req,timeout=30) as response:
    b=response.read(2*1024*1024+1);assert len(b)<=2*1024*1024,'SOURCE_SIZE_LIMIT';out['http_status']=response.status
   ET.fromstring(b);p=dest/(r['module']+'.cnxml')
   with p.open('xb') as f:f.write(b)
   out.update(status='FETCHED',bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),path=str(p))
  except Exception as ex:out['error']=type(ex).__name__+': '+str(ex)
  out['seconds']=time.monotonic()-start;return out
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for r in pool.map(fetch,[r for r in rows if r['module'] not in done]):
   with ledger.open('a',encoding='utf8') as f:f.write(json.dumps(r)+'\n')
   print(r['module'],r['status'],flush=True)
 rr=[json.loads(l) for l in ledger.read_text().splitlines()]
 put(O/'SOURCE_FETCH_RESULT.json',dict(planned=len(rows),attempted=len(rr),fetched=sum(r['status']=='FETCHED' for r in rr),failed=sum(r['status']=='FAILED' for r in rr),retry=0,GPU=0,API=0))
if __name__=='__main__':main()
