"""No model calls; exact pinned XML inventory, text dedup, input freeze."""
from common_adjusted import *
import re,xml.etree.ElementTree as ET,collections
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));import build_data as b

def tag(e):return e.tag.split('}')[-1]
def main():
 d=O/'data';d.mkdir(exist_ok=False);inv=read(BASE/'SOURCE_INVENTORY.json');old=set(inv['excluded_chapter_ids']);t4chap=set(read(BASE/'materials02/DISJOINTNESS.json')['T4_chapters']);modules={}
 for c,ch in inv['chapters'].items():
  if c not in old:
   for m in ch['modules']:modules[ch['repo']+'|'+m]=dict(chapter=c,subject=ch['subject'],repo=ch['repo'],revision=ch['revision'])
 for ex in [read(PREV/'ADDITIONAL_STEM_SOURCE_FREEZE.json')['source']]+read(PREV/'ADDITIONAL_SOURCE_FREEZE_02.json')['sources']:
  rt=ET.parse(ex['path']).getroot();parents={c:a for a in rt.iter() for c in a}
  for e in rt.iter():
   if tag(e)!='module':continue
   a=parents.get(e);chain=[]
   while a is not None:
    if tag(a)=='subcollection':chain.append(next((''.join(x.itertext()).strip() for x in a if tag(x)=='title'),'UNTITLED'))
    a=parents.get(a)
   if chain:modules[ex['repo']+'|'+e.get('document')]=dict(chapter=ex['repo']+'|'+'/'.join(reversed(chain)),subject=ex['repo'].replace('osbooks-',''),repo=ex['repo'],revision=ex['revision'])
 known=[]
 for path in [BASE/'materials02/T4.json',BASE/'materials02/IN_DOMAIN.json',E1/'data/selection02/T1.json',E1/'data/selection02/T2.json']:
  known.extend(read(path))
 oldbg=read(E1/'data/selection02/BACKGROUND.json');known+=oldbg['confirm']+oldbg['holdout']
 usedtext=[re.sub(r'\s+',' ',x['text']).strip().lower() for x in known];usedhash={hashlib.sha256(x.encode()).hexdigest() for x in usedtext}
 ledger=[]
 for n in ['SOURCE_FETCH_LEDGER.jsonl','STATISTICS_FETCH_LEDGER.jsonl','ADDITIONAL_FETCH_02.jsonl']:ledger.extend(json.loads(s) for s in (BASE/n).read_text().splitlines())
 paras=[];qs=[];seen=set();reject=[];source_manifest=[]
 for r in ledger:
  if r['status']!='FETCHED':continue
  mk=r.get('repo','')+'|'+r['module']
  if mk not in modules:
   choices=[k for k in modules if k.endswith('|'+r['module'])]
   if len(choices)!=1:continue
   mk=choices[0]
  if mk in seen:continue
  seen.add(mk);ch=modules[mk]
  if ch['chapter'] in old or ch['chapter'] in t4chap:continue
  path=Path(r['path']);assert sha(path)==r['sha256'];rt=ET.parse(path).getroot();parents={c:a for a in rt.iter() for c in a}
  source=dict(id=mk,chapter=ch['chapter'],subject=ch['subject'],revision=ch['revision'],url=r['url'],raw_path=str(path),raw_sha256=r['sha256'],license='CC BY4.0 pinned collection');source_manifest.append(source)
  for ix,e in enumerate(rt.iter()):
   typ=tag(e)
   if typ not in ['para','problem']:continue
   a=parents.get(e);anc=[]
   while a is not None:anc.append(tag(a));a=parents.get(a)
   if typ=='para' and set(anc)&{'example','exercise','problem','solution','figure','table','para','note'}:continue
   text=b.text(e);wc=b.wordcount(text);why=b.bad(e,text);ident=ch['repo']+'_'+r['module']+'_'+e.get('id',str(ix));norm=re.sub(r'\s+',' ',text).strip().lower()
   if why or not (40<=wc<=600 if typ=='para' else 8<=wc<=500):continue
   h=hashlib.sha256(norm.encode()).hexdigest()
   if h in usedhash or any(norm in z or z in norm for z in usedtext if len(z)>80):reject.append(dict(id=ident,reason='PRIOR_TEXT_OR_SUBSTRING'));continue
   row=dict(id=ident,text=text,words=wc,body_start=0,chapter=ch['chapter'],subject=ch['subject'],source=source,text_sha256=hashlib.sha256(text.encode()).hexdigest(),normalized_sha256=h)
   (paras if typ=='para' else qs).append(row)
 # Freeze chapter allocation before inference/scores; no capacity-based selection.
 qchap=sorted({x['chapter'] for x in qs},key=lambda c:rank('T5_chapter',c));reserve=set(qchap[:max(1,round(len(qchap)*.35))])
 q=[];seenq=set()
 for x in sorted(qs,key=lambda x:rank('T5',x['id'])):
  if x['chapter'] in reserve and x['normalized_sha256'] not in seenq:q.append(dict(x,question=x['text']));seenq.add(x['normalized_sha256'])
  if len(q)>=200:break
 p=[];seenp=set()
 for x in sorted(paras,key=lambda x:rank('background',x['id'])):
  if x['chapter'] not in reserve and x['normalized_sha256'] not in seenp:p.append(x);seenp.add(x['normalized_sha256'])
 learn=p[:100];spoof=p[100:300];hold=p[300:800]
 put(d/'LEARNING_BACKGROUND.json',learn);put(d/'SPOOF_TARGETS.json',spoof);put(d/'P6_BACKGROUND.json',hold);put(d/'T5_QUESTIONS.json',q);put(d/'SOURCE_MANIFEST.json',source_manifest);put(d/'REJECTIONS.json',reject)
 obs={};allout={}
 for method,folder in [('CertInsert',BASE/'scoring_recovery01'),('RC',BASE)]:
  rr=read(folder/'INSERT_T4_all_RESULT.json')['rows'];ok=[]
  for r in rr:
   if r['method']!=method or r['status']!='PREDICTED_TARGET_REACHED':continue
   tp=folder/'outputs'/(r['id']+'.txt');rp=folder/'records'/(r['id']+'.json');assert tp.exists() and rp.exists();ok.append(dict(id=r['id'],source_id=r['source_id'],text_path=str(tp),text_sha256=sha(tp),record_path=str(rp),record_sha256=sha(rp)))
  ok.sort(key=lambda x:rank('observe|'+method,x['source_id']));allout[method]=ok
  obs[method]={str(n):dict(status='AVAILABLE' if len(ok)>=n else 'NOT_AVAILABLE_PENDING_T5',ids=[x['id'] for x in ok[:n]] if len(ok)>=n else [],available=len(ok)) for n in [10,50,200]}
 put(d/'PUBLIC_OUTPUTS.json',allout);put(d/'OBSERVATIONS.json',obs)
 freeze=dict(stage='INPUTS_FROZEN_BEFORE_ANY_NEW_SCORES',learning_background=len(learn),spoof_targets=len(spoof),P6_background=len(hold),T5_questions=len(q),T5_chapters=sorted(reserve),T4_chapters_excluded=sorted(t4chap),old_chapters_excluded=True,exact_and_substring_dedup=True,semantic_dedup_not_certified=True,source_clusters='chapter/module',public_outputs={m:len(v) for m,v in allout.items()},hashes={p.name:sha(p) for p in d.glob('*.json')})
 put(E/'DATA_FREEZE.json',freeze);put(d/'DATA_FREEZE.json',freeze);print(json.dumps({k:v for k,v in freeze.items() if k in ['learning_background','spoof_targets','P6_background','T5_questions','public_outputs']}))
if __name__=='__main__':main()
