from common_adjusted import *
import shutil
src=BASE/'batch02';dst=O/'publication_superseded-60-pair-queue';dst.mkdir(exist_ok=False)
def cp(p,rel):q=dst/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for name in ['FREEZE.json','SOURCES.json','PAIRED_IDS.json','ADMISSION.json','STARTED.json','GENERATION_RESULT.json','GENERATION_FINISHED.json','GPU_USAGE.json','RUN_MANIFEST.jsonl','FAILURES.jsonl','KGW_HTTP_LEDGER.jsonl','PROTOCOL_REPLACEMENT_PROCESSES.json']:
 p=src/name
 if p.exists():cp(p,'evidence/'+name)
for root in ['outputs','records','evaluation','ocr','background']:
 for p in (src/root).rglob('*'):
  if p.is_file() and p.suffix not in ['.log','.png'] and '__pycache__' not in p.parts:cp(p,'evidence/'+p.relative_to(src).as_posix())
for name in ['run_batch2.py','freeze_batch2.py','evaluate_batch2.py','ocr_batch2.py','background_batch2.py','close_superseded_batch2.py']:cp(PREV/name,'code/'+name)
fc=read(O/'delivery_P6/figure_counts.json');put(dst/'figure_counts.json',fc)
(dst/'RESULT.md').write_text('''# Previous60-pair queue: superseded, not complete

Stopped when user replaced Batch02/03 plan.26attempts: KGW2completed+1connectionfailure+1interrupted;Unigram21completed+1interrupted.23completed outputs retained;94unstarted baseline slots cancelled. No compression started, no failure retried.591.451seconds ownGPU residence;server terminated and consumers completed.

These outputs are historical partial evidence, not a completed60-source paired study. Eligible completed outputs may be reused by laterP5 with exact input/method/config checks; interrupted/failed slots are not silently rerun. New priority-stage results live in siblingP1-N10-P2 andP6 directories.

figure_counts.json is the current adjusted-plan snapshot, not fabricated completed old baseline counts. per_item.csv records the actual partial outputs separately. Bias echo comparison uses the inherited schema-mismatched comparator; rawFalse is preserved and exact normalized equality isUNKNOWN. Public detection independently rescored real text. No semantic/human quality gold.
''',encoding='utf8')
import csv
rows=[read(p) for p in (src/'evaluation/records').glob('*.json')];fields=sorted({k for r in rows for k in r})
with (dst/'per_item.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
cp(E2/'BIAS_ECHO_AUDIT.json','BIAS_ECHO_AUDIT.json');cp(O/'publication_P1N10_P2/LICENSES.md','LICENSES.md');(dst/'.gitattributes').write_text('* -text\n')
files=[]
for p in sorted(dst.rglob('*')):
 if p.is_file():
  bb=p.read_bytes();files.append(dict(path=p.relative_to(dst).as_posix(),bytes=len(bb),sha256=hashlib.sha256(bb).hexdigest(),git_blob_sha1=hashlib.sha1(b'blob '+str(len(bb)).encode()+b'\0'+bb).hexdigest()))
put(dst/'FILE_MANIFEST.json',dict(files=files,self_excluded=True));print(len(files),'files')
