"""Source selection without reading any method results."""
from pathlib import Path
import hashlib,html,json,re,sys,shutil
from core.paths import PROJECT_ROOT, RESULTS_DIR
P=RESULTS_DIR/'c2rag_real_source_structure_20261027_01'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True)
 with f.open('x',encoding='utf8') as s:json.dump(x,s,ensure_ascii=False,indent=2)
def norm(raw):
 raw=re.sub(r'<annotation-xml\b.*?</annotation-xml>','',raw,flags=re.S)
 return ' '.join(html.unescape(re.sub('<[^>]+>','',raw)).split())
def paragraphs(raw):
 out=[]
 for p in re.findall(r'<p\b[^>]*>.*?</p>',raw,re.S):
  loc=re.search(r'id="([^"]+)"',p);text=norm(p)
  if text:out.append({'id':loc.group(1) if loc else None,'text':text})
 return out
def examples(raw):
 out=[]
 for start in re.finditer(r'<div\b[^>]*data-type="example"[^>]*>',raw):
  depth=1;end=None
  for tag in re.finditer(r'</?div\b[^>]*>',raw[start.end():]):
   depth+=-1 if tag.group().startswith('</') else 1
   if depth==0:end=start.end()+tag.end();break
  if end:
   block=raw[start.start():end];ps=paragraphs(block)
   if ps:out.append({'example_heading':norm(block[:block.find('<p')]),'paragraphs':ps,'raw_block_sha256':sha(block.encode())})
 return out
def main():
 sys.stdout.reconfigure(encoding='utf8');P.mkdir(parents=True,exist_ok=False)
 r9=PROJECT_ROOT/'experiments/c2rag_r9_real_text_20261019_01'
 reg=json.loads((r9/'source_registry.json').read_text(encoding='utf8'))
 annotations=json.loads((r9/'e1_author_annotations.json').read_text(encoding='utf8'))
 oldhtml=PROJECT_ROOT/'experiments/relation_closure_20261019_01/document_preparation/local_source_snapshots'
 candidates=[];seen=set();hashes={}
 # The four pre-registered R9 examples, independent of new structural outcomes.
 chosen_ids=['linear-points','population-text','ohm-question','power-process']
 locators=['fs-id821146','fs-id1768953','import-auto-id1170614061055','import-auto-id2590834']
 for source,loc,aid in zip(reg['sources'],locators,chosen_ids):
  f=oldhtml/(source['id']+'.html');b=f.read_bytes();ps=paragraphs(b.decode('utf8'));q=next(p for p in ps if p['id']==loc)
  hashes[str(f.relative_to(PROJECT_ROOT))]=sha(b)
  candidates.append({'source_id':source['id'],'url':source['url'],'book':source['book'],'question':q,'paragraphs':ps,
   'example_heading':source['locator'],'html_sha256':sha(b),'local_html':str(f.relative_to(PROJECT_ROOT)),
   'origin':'real_source_problem_researcher_requests','selection_reason':'R9 source registry order, original source problem, not R10 author numerical rewrite'})
  seen.add((source['url'],loc))
 r10=PROJECT_ROOT/'experiments/c2rag_r10_20261020_01'
 for a in json.loads((r10/'adjudicated_assets.json').read_text(encoding='utf8')):
  if not a['source_verified']:
   candidates.append({'source_id':a['id'],'url':a['url'],'excluded_reason':'prior source verification failed','selected':False});continue
  f=r10/'local_sources'/(a['book']+'__'+a['page']+'.html')
  if not f.exists():continue
  b=f.read_bytes();hashes[str(f.relative_to(PROJECT_ROOT))]=sha(b)
  for ex in examples(b.decode('utf8')):
   loc=ex['paragraphs'][0]['id'];key=(a['url'],loc)
   if key in seen:
    candidates.append({'source_id':a['id'],'url':a['url'],'question':ex['paragraphs'][0],'selected':False,'excluded_reason':'same source problem already selected from R9'});continue
   seen.add(key)
   candidates.append({'source_id':a['id'],'url':a['url'],'book':a['book'],'question':ex['paragraphs'][0],
    'paragraphs':ex['paragraphs'],'example_heading':ex['example_heading'],'html_sha256':sha(b),'local_html':str(f.relative_to(PROJECT_ROOT)),
    'origin':'real_source_problem_researcher_requests','selection_reason':'R10 source registry then worked-example DOM order; no outcome filtering'})
 selected=[]
 for row in candidates:
  if row.get('excluded_reason'):continue
  if len(selected)>=12:row.update(selected=False,excluded_reason='12-task cap reached in fixed source order');continue
  row.update(selected=True,task_id=f'T{len(selected)+1:02d}');selected.append(row)
 write('selected_sources.json',selected)
 write('selection_register.json',[{k:v for k,v in r.items() if k!='paragraphs'} for r in candidates])
 write('source_hashes_before.json',hashes)
 base=PROJECT_ROOT/'experiments/results/_root_workspaces_20261023/c2rag-support-optimization-20261022/baseline'
 expected={'engines.py':'ed3b646d94bd9b2a395284f41fac7e87c3f277d149a05c2641b367fe6ef5fcce',
 'reference.py':'7e6cfc329afc69e135b2a92e0fcfe9d8536636b4c21f0089d7e5b4fd7cd5a472'}
 for name,h in expected.items():
  data=(base/name).read_bytes();assert sha(data)==h;dst=P/'snapshot'/name;dst.parent.mkdir(exist_ok=True);dst.write_bytes(data)
 write('reuse_manifest.json',{'baseline_path':str(base.relative_to(PROJECT_ROOT)),'sha256':expected,
  'local_followups':'coalition 20261021 and support optimization 20261022 are synthetic implementation studies, not this real-source check',
  'remote_diagnostics_seen':['2026-10-27-c2rag-forward-release-r32'],'newer_same_task_found':False})
 for s in selected:print(s['task_id'],s['example_heading'][:100],s['question']['id'],s['question']['text'])
if __name__=='__main__':main()
