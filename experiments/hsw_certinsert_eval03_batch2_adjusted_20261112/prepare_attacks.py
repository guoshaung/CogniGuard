"""Learn from public text only; freeze attack strings before true-key scoring."""
from common_adjusted import *
import re,collections,xml.etree.ElementTree as ET
sys.path.insert(0,str(W/'experiments/hsw_english_replication_20261110_01'))
from capacity_shared_v32 import nlp
BLOCK=set('then thus so therefore hence however next now first finally'.split())
def spans(text):
 masked=re.sub(r'\\\(.*?\\\)',lambda m:' '*len(m[0]),text,flags=re.S)
 return [(s.start_char,s.end_char) for s in nlp(masked).sents]
def prefixes(text):
 out=set()
 for a,z in spans(text):
  s=text[a:z].lstrip();m=re.match(r"((?:[A-Za-z]+(?:['’-][A-Za-z]+)*\s+){0,4}[A-Za-z]+),",s)
  if m:out.add(re.sub(r'\s+',' ',m[1]).lower())
 return out

def main():
 d=O/'P1';d.mkdir(exist_ok=False);pub=read(O/'data/PUBLIC_OUTPUTS.json');obs=read(O/'data/OBSERVATIONS.json');background=read(O/'data/LEARNING_BACKGROUND.json');targets=read(O/'data/SPOOF_TARGETS.json');bc=collections.Counter(w for x in background for w in prefixes(x['text']));learning={};tasks=[]
 for method,items in pub.items():
  for N in [10,50,200]:
   o=obs[method][str(N)]
   if o['status']!='AVAILABLE':continue
   ids=set(o['ids']);training=[x for x in items if x['id'] in ids];freq=collections.Counter(w for x in training for w in prefixes(Path(x['text_path']).read_text(encoding='utf8')));ranked=sorted(freq,key=lambda w:(-(freq[w]/N-bc[w]/len(background)),w));learning[method+f'_N{N}']=[dict(phrase=w,observed_docs=freq[w],observed_n=N,background_docs=bc[w],background_n=len(background),excess=freq[w]/N-bc[w]/len(background)) for w in ranked]
   for m in [4,8]:
    words=ranked[:m];label=f'N{N}_m{m}'
    for x in targets:
     t=x['text'];ss=spans(t);wordpos=list(re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",t));budget=int(.06*len(wordpos));slots=[]
     for a,z in ss:
      mm=re.search('[A-Za-z]',t[a:z])
      if not mm:continue
      a+=mm.start();fw=re.match('[A-Za-z]+',t[a:])[0].lower()
      if fw in BLOCK or a<x.get('body_start',0):continue
      slots.append(a)
     slots.sort(key=lambda a:rank('spoof_position|'+x['id'],str(a)));chosen=[];groups=set();used=0
     for w in words:
      cost=len(w.split());group=' '.join(w.split()[:2])
      if group in groups or used+cost>budget:continue
      pos=next((a for a in slots if all(sum(a0<=p.start()<a1 for p in wordpos)>=8 for a0,a1 in [sorted((a,v['offset'])) for v in chosen])),None)
      if pos is None:continue
      chosen.append(dict(offset=pos,phrase=w,inserted=w[0].upper()+w[1:]+', '));groups.add(group);slots.remove(pos);used+=cost
     out=t
     for v in sorted(chosen,key=lambda v:v['offset'],reverse=True):out=out[:v['offset']]+v['inserted']+out[v['offset']:]
     ident=f'{method}__{label}__spoof__{x["id"]}';tasks.append(dict(id=ident,source_id=x['id'],cluster=x['source']['id'],method=method,N=N,m=m,actual_learned=len(words),attack='spoofing',text=out,input_sha256=x['text_sha256'],output_sha256=hashlib.sha256(out.encode()).hexdigest(),insertions=chosen,budget_words=budget,inserted_words=used))
    for x in items:
     if x['id'] in ids:continue
     t=Path(x['text_path']).read_text(encoding='utf8');edits=[]
     for a,z in spans(t):
      q=t[a:z];lead=len(q)-len(q.lstrip());start=a+lead
      for w in words:
       match=re.match(re.escape(w)+r',\s*',t[start:z],re.I)
       if match:edits.append((start,start+match.end()));break
     out=t
     for a,z in sorted(edits,reverse=True):out=out[:a]+out[z:]
     ident=f'{method}__{label}__scrub__{x["source_id"]}';tasks.append(dict(id=ident,source_id=x['source_id'],cluster=x['source_id'],method=method,N=N,m=m,actual_learned=len(words),attack='scrubbing',text=out,input_sha256=x['text_sha256'],output_sha256=hashlib.sha256(out.encode()).hexdigest(),removed_spans=edits,observation_overlap=False))
 put(d/'LEARNED_PHRASES.json',learning);put(d/'TASKS.json',tasks);put(E/'P1_INPUT_FREEZE.json',dict(tasks=len(tasks),task_sha256=sha(d/'TASKS.json'),learned_sha256=sha(d/'LEARNED_PHRASES.json'),scored=False,stage='N10_ONLY_OTHER_N_PENDING_T5',observation_split=obs));print('P1 frozen',len(tasks),'targets')
 # P2 original insertion offsets; no new text generated.
 source={x['id']:x for x in read(BASE/'materials02/T4.json')};rows=[]
 for method,items in pub.items():
  for it in items:
   x=source[it['source_id']];r=read(Path(it['record_path']));t=x['text'];rt=ET.parse(x['source']['raw_path']).getroot();titles={''.join(e.itertext()).strip() for e in rt.iter() if e.tag.split('}')[-1]=='title'};title_spans=[]
   for match in re.finditer(r'(?m)^.*$',t):
    line=match[0].strip()
    if line and (line in titles or line in ['Strategy','Solution','Discussion','Significance']):title_spans.append((match.start(),match.end()))
   ins=[]
   for c in r['chosen']:
    pos=c['offset'];reg='title_or_label' if any(a<=pos<=z for a,z in title_spans) else 'problem' if pos<x['body_start'] else 'explanation';s=next((t[a:z] for a,z in spans(t) if a<=pos<z),'');adj=bool(re.search(r'\d|\\\(',s));ins.append(dict(offset=pos,phrase=c['word'],region=reg,anchor_adjacent=adj))
   out=Path(it['text_path']).read_text(encoding='utf8');rest=out
   for s in sorted(r['spans'],key=lambda a:a['start'],reverse=True):assert rest[s['start']:s['end']]==s['inserted'];rest=rest[:s['start']]+rest[s['end']:]
   for cc in r.get('case_changes',[]):rest=rest[:cc['offset']]+cc['before']+rest[cc['offset']+1:]
   assert rest==t,'INVERSE_FAILED'
   rows.append(dict(id=it['id'],source_id=x['id'],method=method,insertions=ins,any_title_or_problem=any(v['region']!='explanation' for v in ins),certificate_pass=True,source_sha256=x['text_sha256']))
 p=O/'P2';p.mkdir(exist_ok=False);put(p/'per_output.json',rows);put(p/'COUNTS.json',{m:dict(k=sum(r['any_title_or_problem'] for r in rows if r['method']==m),n=sum(r['method']==m for r in rows)) for m in pub});print('P2',read(p/'COUNTS.json'))
if __name__=='__main__':main()
