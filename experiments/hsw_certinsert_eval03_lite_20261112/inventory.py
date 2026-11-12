"""After protocol commit: count licensed source groups before selecting any tests."""
from initialize import *
import sys,re,xml.etree.ElementTree as ET,collections
def tag(e):return e.tag.split('}')[-1]
def title(e):return next((''.join(x.itertext()).strip() for x in e if tag(x)=='title'),'UNTITLED')
def main():
 assert not (O/'SOURCE_INVENTORY.json').exists()
 head=subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()
 tracked=subprocess.check_output(['git','-C',str(W),'show',head+':experiments/'+E.name+'/EVAL_FREEZE.json'])
 assert hashlib.sha256(tracked).hexdigest()==sha(E/'EVAL_FREEZE.json'),'FREEZE_NOT_COMMITTED'
 sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));import build_data as b
 old=W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded';long=W/'var/results/hsw-st/insertion_feasibility_20261109_01/run08_long'
 used=set(read(E2/'data/EXCLUSION_FREEZE.json')['source_modules'])
 for rr in read(E2/'data/DOMAIN_SPLIT02.json').values():used.update(x['source_module'] for x in rr)
 vr=W/'var/results/hsw-st/certinsert_vocab_20261112_01/run01'
 for group in ['FIT','HOLDOUT']:
  used.update(x['module'] for x in read(vr/('SOURCES_'+group+'.json')))
 configs=[]
 for v in [1,2,3]:configs.append(('physics',old/f'protocol_v3_2/collections/university-physics-volume-{v}.xml','osbooks-university-physics-bundle','db44eb99e9aa1d9188cf182f82ccdece9c7b11'))
 # Use the already pinned revision spelling from original source provenance.
 configs=[(d,p,r,'db44eb99e9aa1d918fd8cf182f82ccdece9c7b11') for d,p,r,v in configs]
 configs += [('chemistry',old/'protocol_v3_2/collections/chemistry-2e.xml','osbooks-chemistry-bundle','32c719622fbb7a0ca729cd645c1df4cf4e7d5b3a'),('physics',E2/'data/college/collection.xml','osbooks-college-physics-bundle','84147e8ddbb1a7d2689e235630b230e6b4f20480'),('biology',E1/'vendor/biology/collections/biology-2e.collection.xml','osbooks-biology-bundle','4460012626ee747bdb9db8c4418317798fbc67ce')]
 for x in read(E2/'data/EXTRA_SOURCE_FREEZE.json'):
  if x['name'] in ['hsphysics','atomsfirst']:configs.append(('physics' if x['name']=='hsphysics' else 'chemistry',E2/'data'/(x['name']+'_collection.xml'),x['repo'],x['rev']))
 dirs=[long/'raw',old/'protocol_v3_2/raw',E1/'data/biology_raw',E2/'data/college/raw',E2/'data/extra_raw'];raw={}
 for d in dirs:
  for p in d.glob('*.cnxml'):raw.setdefault(p.stem.split('_',1)[-1],p)
 chapters={};provenance=[]
 for subject,path,repo,rev in configs:
  rt=ET.parse(path).getroot();licenses=[x.get('url','') for x in rt.iter() if tag(x)=='license'];assert any('creativecommons.org/licenses/by/4.0' in u for u in licenses)
  book=next((''.join(x.itertext()).strip() for x in rt.iter() if tag(x)=='title'),path.stem);parents={c:a for a in rt.iter() for c in a}
  for e in rt.iter():
   if tag(e)!='module':continue
   m=e.get('document');a=parents.get(e);anc=[]
   while a is not None:
    if tag(a)=='subcollection':anc.append(title(a))
    a=parents.get(a)
   if not anc:continue
   key=repo+'|'+book+'|'+'/'.join(reversed(anc));chapters.setdefault(key,dict(subject=subject,book=book,hierarchy=list(reversed(anc)),modules=[],repo=repo,revision=rev))['modules'].append(m)
  provenance.append(dict(path=str(path),sha256=sha(path),repo=repo,revision=rev,license=licenses,book=book))
 excluded={k for k,v in chapters.items() if set(v['modules'])&used};selected=[];missing=[];rejected=[];seen=set()
 for key,ch in chapters.items():
  if key in excluded:continue
  for mod in ch['modules']:
   if mod in seen:continue
   seen.add(mod);path=raw.get(mod)
   if path is None:
    missing.append(dict(module=mod,chapter=key,subject=ch['subject'],url=f'https://raw.githubusercontent.com/openstax/{ch["repo"]}/{ch["revision"]}/modules/{mod}/index.cnxml'));continue
   rt=ET.parse(path).getroot()
   for ix,e in enumerate(rt.iter()):
    if not(tag(e)=='example' or tag(e)=='note' and e.get('class')=='worked-example'):continue
    t=b.text(e);why=b.bad(e,t);h=re.search(r'(?mi)^\s*(Strategy|Solution|Discussion|Significance)(?:\s+for\s+[^\n]+)?\s*$',t);body_start=h.end() if h else None
    if body_start is None:
     sol=next((x for x in e.iter() if tag(x)=='solution'),None);st=b.text(sol) if sol is not None else '';at=t.find(st) if st else -1
     if at>=0:body_start=at
    if body_start is None:why.append('NO_KNOWN_EXPLANATION_BOUNDARY')
    if not t:why.append('EMPTY')
    ident=ch['subject']+'_'+mod+'_'+e.get('id',str(ix))
    if why:rejected.append(dict(id=ident,reason=why));continue
    selected.append(dict(id=ident,subject=ch['subject'],module=mod,chapter=key,text=t,body=t[body_start:],question=t[:body_start],body_start=body_start,words=b.wordcount(t),explanation_words=b.wordcount(t[body_start:]),sha256=hashlib.sha256(t.encode()).hexdigest(),raw_path=str(path),raw_sha256=sha(path),source_url=f'https://raw.githubusercontent.com/openstax/{ch["repo"]}/{ch["revision"]}/modules/{mod}/index.cnxml',license='CC BY4.0 pinned collection',quality='STRUCTURAL_SCREEN_ONLY; not numerical semantic gold'))
 put(O/'CANDIDATE_INVENTORY.json',selected);put(O/'MISSING_MODULES.json',missing);put(O/'SOURCE_REJECTIONS.json',rejected)
 result=dict(protocol_commit=head,collections=provenance,total_chapters=len(chapters),excluded_chapters=len(excluded),remaining_chapters={d:sum(v['subject']==d and k not in excluded for k,v in chapters.items()) for d in ['physics','chemistry','biology']},excluded_modules_direct=len(used),cached_eligible_examples=len(selected),by_subject=dict(collections.Counter(x['subject'] for x in selected)),uncached_remaining_modules=len(missing),material_gate='NOT_YET_ADMITTED',note='Counts are a cached lower bound, not final shortage if uncached modules exist. No inference or scores have run. No test sample selected.',chapters=chapters,excluded_chapter_ids=sorted(excluded))
 put(O/'SOURCE_INVENTORY.json',result);print(json.dumps({k:result[k] for k in ['protocol_commit','total_chapters','excluded_chapters','remaining_chapters','cached_eligible_examples','by_subject','uncached_remaining_modules','material_gate']}))
if __name__=='__main__':main()
