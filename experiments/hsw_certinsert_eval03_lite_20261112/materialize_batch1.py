"""Full-source inventory and fixed chapter split, before any scores."""
from initialize import *
import re,sys,xml.etree.ElementTree as ET,collections
def tag(e):return e.tag.split('}')[-1]
def rank(x):return hashlib.sha256(('2026111203|batch1|'+x).encode()).hexdigest()
def main():
 assert not (O/'BATCH1_DATA_FREEZE.json').exists()
 sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));import build_data as b
 inv=read(O/'SOURCE_INVENTORY.json');excluded=set(inv['excluded_chapter_ids']);modules={}
 for c,ch in inv['chapters'].items():
  if c not in excluded:
   for m in ch['modules']:modules[m]=dict(chapter=c,subject=ch['subject'],repo=ch['repo'],revision=ch['revision'])
 extra=read(E/'ADDITIONAL_STEM_SOURCE_FREEZE.json')['source'];root=ET.parse(extra['path']).getroot();parents={c:a for a in root.iter() for c in a}
 for e in root.iter():
  if tag(e)!='module':continue
  a=parents.get(e);chain=[]
  while a is not None:
   if tag(a)=='subcollection':chain.append(next((''.join(x.itertext()).strip() for x in a if tag(x)=='title'),'UNTITLED'))
   a=parents.get(a)
  if chain:modules[e.get('document')]=dict(chapter=extra['repo']+'|'+'/'.join(reversed(chain)),subject='statistics',repo=extra['repo'],revision=extra['revision'])
 ledger=[]
 for name in ['SOURCE_FETCH_LEDGER.jsonl','STATISTICS_FETCH_LEDGER.jsonl']:
  ledger.extend(json.loads(l) for l in (O/name).read_text(encoding='utf8').splitlines())
 pool=[];paragraphs=[];rejected=[];seen=set()
 for r in ledger:
  if r['status']!='FETCHED' or r['module'] not in modules:continue
  ch=modules[r['module']];path=Path(r['path']);assert sha(path)==r['sha256'];rt=ET.parse(path).getroot()
  for ix,e in enumerate(rt.iter()):
   if not(tag(e)=='example' or tag(e)=='note' and e.get('class')=='worked-example'):continue
   t=b.text(e);why=b.bad(e,t);eid=r['module']+'_'+e.get('id',str(ix));solution=next((z for z in e.iter() if tag(z)=='solution'),None);st=b.text(solution) if solution is not None else ''
   h=re.search(r'(?mi)^\s*(Strategy|Solution|Discussion|Significance)(?:\s+for\s+[^\n]+)?\s*$',t);start=h.end() if h else t.find(st) if st else -1
   if start<0:why.append('NO_KNOWN_EXPLANATION_BOUNDARY')
   if not t or b.wordcount(t)<20:why.append('EXAMPLE_TOO_SHORT')
   normalized=re.sub(r'\s+',' ',t).strip();digest=hashlib.sha256(normalized.encode()).hexdigest()
   if digest in seen:why.append('EXACT_DUPLICATE')
   if why:rejected.append(dict(id=eid,reasons=why,chapter=ch['chapter']));continue
   seen.add(digest);source=dict(id=ch['subject']+'_'+r['module'],subject=ch['subject'],revision=ch['revision'],url=r['url'],raw_path=str(path),raw_sha256=r['sha256'],license='CC BY4.0 pinned collection')
   item=dict(id=eid,subject=ch['subject'],source=source,chapter=ch['chapter'],text=t,body_start=start,explanation_words=b.wordcount(t[start:]),words=b.wordcount(t),text_sha256=hashlib.sha256(t.encode()).hexdigest(),normalized_sha256=digest,quality='STRUCTURAL_SCREEN_ONLY_PENDING_NUMERICAL_CHECK')
   pool.append(item)
   # Controls are intact paragraphs from the same independently assigned example group.
   for j,p in enumerate(e.iter()):
    if tag(p)!='para':continue
    pt=b.text(p);off=t.find(pt)
    if off<start or not 30<=b.wordcount(pt)<=600 or b.bad(p,pt):continue
    paragraphs.append(dict(id=eid+'_p'+str(j),example_id=eid,chapter=ch['chapter'],subject=ch['subject'],source=source,text=pt,words=b.wordcount(pt),text_sha256=hashlib.sha256(pt.encode()).hexdigest()))
 # Chapter assignment is based only on IDs, not capacity, detection or quality output.
 chs=sorted({p['chapter'] for p in pool},key=rank);n=len(chs);nt=min(n,max(1,round(n*.6))) if n else 0;tchap=set(chs[:nt]);bchap=set(chs[nt:]);t4=sorted([x for x in pool if x['chapter'] in tchap],key=lambda x:rank(x['id']))[:400];bg=sorted([x for x in paragraphs if x['chapter'] in bchap],key=lambda x:rank(x['id']))[:1000]
 seenbg=set();bg=[x for x in bg if not(x['text_sha256'] in seenbg or seenbg.add(x['text_sha256']))]
 pairs=sorted(t4,key=lambda x:rank('paired|'+x['id']))[:60]
 put(O/'ALL_WORKED_EXAMPLES.json',pool);put(O/'ALL_CONTROL_PARAGRAPHS.json',paragraphs);put(O/'MATERIAL_REJECTIONS.json',rejected)
 put(O/'T4.json',t4);put(O/'IN_DOMAIN.json',bg);put(O/'PAIRED_IDS.json',[x['id'] for x in pairs]);put(O/'DISJOINTNESS.json',dict(chapter_split=True,T4_chapters=sorted(tchap),control_chapters=sorted(bchap),chapter_intersection=sorted(tchap&bchap),exact_text_overlap=sorted({x['text_sha256'] for x in t4}&{x['text_sha256'] for x in bg}),old_excluded_chapters=sorted(excluded),limits='Exact chapter and normalized-byte exclusion; cross-edition semantic near-duplicate review still required.'))
 result=dict(phase='MATERIAL_SCREEN_BEFORE_SCORING',pool_examples=len(pool),control_paragraph_pool=len(paragraphs),T4=len(t4),T4_subjects=dict(collections.Counter(x['subject'] for x in t4)),in_domain=len(bg),background_examples=len({x['example_id'] for x in bg}),paired=len(pairs),requested=dict(T4=400,in_domain=1000,paired=60),actual_shortage_authority='User batch revision: actual numbers if insufficient, no repeated historical samples',T5='OPTIONAL_NOT_STARTED',data_hashes={f:sha(O/f) for f in ['T4.json','IN_DOMAIN.json','PAIRED_IDS.json','DISJOINTNESS.json']},generation=0)
 put(O/'BATCH1_DATA_FREEZE.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
