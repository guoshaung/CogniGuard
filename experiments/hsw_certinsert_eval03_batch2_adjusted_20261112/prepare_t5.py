"""Streaming frozen Markdown structure adapter + unchanged CertInsert/RC planning."""
from common_adjusted import *
import time,re
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));import prepare_cpu as legacy
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_02'));from structure_adapter import split,allowed_offset

def main():
 d=O/'T5_prepared';d.mkdir(exist_ok=False);(d/'records').mkdir();(d/'structures').mkdir();voc=read(legacy.R/'VOCABULARY.json');freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];det,key=legacy.make_detector(voc);sel=legacy.selector(det,key,4,voc);glob=sel('');tasks=read(O/'data/T5_QUESTIONS.json');plans=[];caps=[];finished=set();errors=[]
 put(d/'START.json',dict(unix=time.time(),adapter_sha256=sha(W/'experiments/hsw_certinsert_eval_20261111_02/structure_adapter.py'),method_freeze_sha256=sha(PREV/'EVAL_FREEZE.json'),code_sha256=sha(Path(__file__))))
 while True:
  added=False
  for x in tasks:
   if x['id'] in finished:continue
   rec=O/'P3/records'/('T5__'+x['id']+'.json');tp=O/'P3/outputs'/('T5__'+x['id']+'.txt')
   if not rec.exists():continue
   try:r=read(rec)
   except ValueError:continue
   finished.add(x['id']);added=True
   if not tp.exists():errors.append(dict(source_id=x['id'],status='NOT_RUN_SOURCE_GENERATION_FAILED'));continue
   text=tp.read_text(encoding='utf8');seg=split(text,x['question']);put(d/'structures'/(x['id']+'.json'),seg)
   for method in ['CertInsert','RC']:
    try:
     p=legacy.build_plan(dict(x,text=text),'T5','A4',sel if method=='CertInsert' else lambda t:glob);p['id']=p['id'].replace('__A4','__'+method);p['method']=method
     if method=='CertInsert':p['candidates']=[s for s in p['candidates'] if allowed_offset(seg,s['offset'])]
     body=''.join(text[a:b] for a,b in seg['body_intervals']);p['explanation_words']=legacy.word_count(body);first=next((a+m.start() for a,b in seg['body_intervals'] if (m:=re.search('[A-Za-z]',text[a:b]))),-1)
     if method=='CertInsert':
      for s in p['candidates']:s['explanation_first']=s['offset']==first
     p['source_generation_status']=r['status'];p['source_natural_eos']=r.get('stop_type')=='eos';p['structure_adapter_sha256']=sha(W/'experiments/hsw_certinsert_eval_20261111_02/structure_adapter.py');c=legacy.capacity(p,voc,freq);put(d/'records'/(p['id']+'.json'),dict(plan=p,capacity=c));plans.append(p);caps.append(c)
    except Exception as e:
     er=dict(source_id=x['id'],method=method,error=type(e).__name__+': '+str(e),status='PREPARATION_FAILED');errors.append(er);put(d/'records'/('T5__'+x['id']+'__'+method+'.failed.json'),er)
  if (O/'P3/RESULT.json').exists() and not added:break
  if not added:time.sleep(5)
  else:print('T5 planned sources',len(finished),flush=True)
 for name,value in [('PLANS',plans),('CAPACITY',caps),('VOCABULARY',voc),('FREQUENCIES',freq),('SCALE',read(legacy.R/'FLUENCY_SCALE_LOCK.json')),('ERRORS',errors)]:put(d/(name+'.json'),value)
 put(d/'FINISHED.json',dict(planned_sources=len(tasks),source_records=len(finished),plans=len(plans),errors=len(errors),GPU=0,API=0))
if __name__=='__main__':main()
