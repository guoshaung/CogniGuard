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
 d=O/'P1_expanded';d.mkdir(exist_ok=False);pub=read(O/'data_expanded/PUBLIC_OUTPUTS.json');obs=read(O/'data_expanded/OBSERVATIONS.json');background=read(O/'data/LEARNING_BACKGROUND.json');targets=read(O/'data/SPOOF_TARGETS.json');bc=collections.Counter(w for x in background for w in prefixes(x['text']));learning={};tasks=[]
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
    for x in sorted(items,key=lambda x:rank('scrub_target',x['source_id']))[:200]:
     t=Path(x['text_path']).read_text(encoding='utf8');edits=[]
     for a,z in spans(t):
      q=t[a:z];lead=len(q)-len(q.lstrip());start=a+lead
      for w in words:
       match=re.match(re.escape(w)+r',\s*',t[start:z],re.I)
       if match:edits.append((start,start+match.end()));break
     out=t
     for a,z in sorted(edits,reverse=True):out=out[:a]+out[z:]
     ident=f'{method}__{label}__scrub__{x["source_id"]}';tasks.append(dict(id=ident,source_id=x['source_id'],cluster=x['source_id'],method=method,N=N,m=m,actual_learned=len(words),attack='scrubbing',text=out,input_sha256=x['text_sha256'],output_sha256=hashlib.sha256(out.encode()).hexdigest(),removed_spans=edits,observation_overlap=x['id'] in ids))
 put(d/'LEARNED_PHRASES.json',learning);put(d/'TASKS.json',tasks);put(E/'P1_EXPANDED_INPUT_FREEZE.json',dict(tasks=len(tasks),task_sha256=sha(d/'TASKS.json'),learned_sha256=sha(d/'LEARNED_PHRASES.json'),scored=False,stage='EXPANDED_POOL_SEPARATE_FROM_INITIAL_N10',observation_split=obs));print('P1 frozen',len(tasks),'targets')

if __name__=='__main__':main()
