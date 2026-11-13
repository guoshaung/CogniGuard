"""Fetch only frozen R modules; future T6 module contents are never requested."""
import concurrent.futures
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

W=Path(__file__).resolve().parents[2]
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    allocation=json.loads((O/'CHAPTER_ALLOCATION.json').read_bytes())
    assert allocation['R_T6_module_intersection']==0
    jobs={}
    for key,ch in allocation['R_chapters'].items():
        for module in ch['modules']:
            ident=ch['repo']+'|'+module
            jobs.setdefault(ident,dict(id=ident,module=module,repo=ch['repo'],revision=ch['revision'],
                chapters=[],subject=ch['subject']))['chapters'].append(key)
    raw=O/'raw';raw.mkdir(exist_ok=True)
    ledger=O/'R_FETCH_LEDGER.jsonl'
    if ledger.exists():
        raise FileExistsError('Preserve previous fetch attempt')
    # Existing source-cache reuse requires the exact pinned URL and SHA256.
    cache={}
    base=W/'var/results/hsw-st/certinsert_eval03_lite_20261112/run01'
    for name in ['SOURCE_FETCH_LEDGER.jsonl','STATISTICS_FETCH_LEDGER.jsonl','ADDITIONAL_FETCH_02.jsonl']:
        p=base/name
        if p.exists():
            for line in p.read_text(encoding='utf8').splitlines():
                row=json.loads(line)
                if row.get('status')=='FETCHED':
                    cache[row['url']]=row
    def fetch(job):
        row=dict(job)
        row['url']=f"https://raw.githubusercontent.com/openstax/{row['repo']}/{row['revision']}/modules/{row['module']}/index.cnxml"
        try:
            old=cache.get(row['url'])
            if old and Path(old['path']).exists():
                body=Path(old['path']).read_bytes()
                assert sha(body)==old['sha256']
                row['reused_exact_cached_url']=True
            else:
                response=requests.get(row['url'],timeout=(15,30))
                response.raise_for_status();body=response.content
                assert len(body)<=2097152
                row['reused_exact_cached_url']=False
            ET.fromstring(body)
            path=raw/(row['repo']+'_'+row['module']+'.cnxml')
            path.write_bytes(body)
            row.update(status='FETCHED',path=str(path),sha256=sha(body))
        except Exception as error:
            row.update(status='FAILED',error=type(error).__name__+': '+str(error))
        return row
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,row in enumerate(pool.map(fetch,jobs.values()),1):
            with ledger.open('a',encoding='utf8') as handle:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
            if i%25==0:
                print('R source fetch',i,'/',len(jobs),flush=True)
    rows=[json.loads(line) for line in ledger.read_text().splitlines()]
    failures=[r for r in rows if r['status']!='FETCHED']
    (O/'R_FETCH_RESULT.json').write_text(json.dumps(dict(planned=len(jobs),fetched=len(rows)-len(failures),
        failures=failures,T6_content_requests=0),ensure_ascii=False,indent=2),encoding='utf8')
    print('FETCH_COMPLETE',len(rows)-len(failures),'/',len(jobs),flush=True)


if __name__=='__main__':
    main()
