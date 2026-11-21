"""Read-only verification of the published package using Python standard library."""
from pathlib import Path
import json,hashlib,gzip,collections
from truth import execute
P=Path(__file__).parent
def lines(path):
    if not path.exists():path=Path(str(path)+'.gz')
    op=gzip.open if path.suffix=='.gz' else open
    with op(path,'rt',encoding='utf8') as f:
        for line in f:yield json.loads(line)
def main():
    manifest=json.loads((P/'manifest.json').read_text())
    for name,row in manifest['files'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==row['sha256'],name
    for name,row in manifest['data_compression'].items():
        with gzip.open(P/name,'rb') as f:assert hashlib.sha256(f.read()).hexdigest()==row['uncompressed_sha256'],name
    lock=json.loads((P/'final_freeze.json').read_text())
    for name,h in lock['sources'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==h,name
    for name,h in lock['external_dependencies'].items():assert hashlib.sha256((P/'dependencies'/name).read_bytes()).hexdigest()==h,name
    students={};tasks={};counts={}
    for phase,n in [('train',5000),('dev',1000),('test',10000)]:
        profiles=list(lines(P/f'data/{phase}/profiles.jsonl'));students[phase]={r['student_id'] for r in profiles}
        tt=list(lines(P/f'data/{phase}/tasks.jsonl'));oo=list(lines(P/f'data/{phase}/oracle.jsonl'));assert len(tt)==len(oo)==n
        assert len({t['request_id'] for t in tt})==n;tasks[phase]={t['request_id'] for t in tt}
        for t,o in zip(tt,oo):
            assert t['request_id']==o['request_id'] and t['student_id'] in students[phase]
            assert execute(t['type_id'],t['variant'],o['source_values'],t['params'])==o['reference']
        families=collections.Counter(t['family'] for t in tt);assert len(families)==32
        counter=collections.Counter();seen=set()
        for r in lines(P/f'var/results/{phase}/raw_rows.jsonl.gz'):
            key=(r['case'],r['method'],r['K']);assert key not in seen;seen.add(key)
            assert r['case'] in tasks[phase] and r['fields']==len(r['selected'])<=r['K'] and r['tokens']<=96
            assert {x.split('=',1)[0] for x in r['wire'].splitlines()}==set(r['selected'])
            counter[(r['method'],r['K'])]+=1
        assert len(counter)==42 and set(counter.values())=={n};counts[phase]=len(seen)
    assert not students['train']&students['dev'] and not students['train']&students['test'] and not students['dev']&students['test']
    assert sum(map(len,students.values()))==5000
    assert len(json.loads((P/'attacks_test/metrics.json').read_text()))==340
    print(json.dumps({'status':'VERIFIED','manifest_files':len(manifest['files']),'raw_rows':counts,'students':5000,'test_episodes':10000,'truth_recomputed_episodes':16000,'production_files_modified':0},indent=2))
if __name__=='__main__':main()
