from initialize import *
import sys,collections,time,numpy as np
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'))
from prepare_cpu import make_detector,R,OLD
from e1_v4r8_selector import selector
from e1_v4r7f_anchors import anchors
from e1_v4r3_core import exact,pb_tail

def main():
 z=O/'key_stress';z.mkdir(exist_ok=True);assert not (z/'START.json').exists()
 f=read(E/'KEY_STRESS_FREEZE.json');data=(O/'restricted/diagnostic_keys.bin').read_bytes();assert hashlib.sha256(data).hexdigest()==f['aggregate_sha256']
 put(z/'START.json',dict(unix=time.time(),freeze_sha256=sha(E/'KEY_STRESS_FREEZE.json')))
 voc=read(R/'VOCABULARY.json');freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];det,_=make_detector(voc)
 rows=read(O/'materials02/IN_DOMAIN.json');errors=[];valid=[]
 for x in rows:
  try:anchors(x['text']);valid.append(x)
  except Exception as e:errors.append(dict(id=x['id'],error=str(e)))
 for at in range(0,len(valid),16):det.embed(['\n'.join(anchors(x['text'])) for x in valid[at:at+16] if len(anchors(x['text']))>=5]) if any(len(anchors(x['text']))>=5 for x in valid[at:at+16]) else None
 table=det.embed([x['text'] for x in read(OLD/'development_round01/SECTABLE_CORPUS.json')[:len(voc)]])
 accum={x['id']:{str(a):0 for a in f['alphas']} for x in valid};ks=[]
 with (z/'PER_KEY.jsonl').open('x',encoding='utf8') as log:
  for i in range(1000):
   key=data[i*32:(i+1)*32];order=sorted(range(len(voc)),key=lambda j:hashlib.sha256(key+b'|sectable|'+str(j).encode()).digest());det.table=table[order];sel=selector(det,key,4,voc);counts={str(a):0 for a in f['alphas']}
   for x in valid:
    ws=sel(x['text']);pv=pb_tail([freq[w] for w in ws],sum(exact(x['text'],w) for w in ws))
    for a in f['alphas']:
     counts[str(a)]+=int(pv<a);accum[x['id']][str(a)]+=int(pv<a)
   r=dict(key_id=f'DIAG_{i+1:04d}',n=len(valid),counts=counts);log.write(json.dumps(r)+'\n');ks.append(r)
   if i%100==0:print('keys',i,flush=True)
 put(z/'RESULT.json',dict(keys=1000,actual_texts=len(valid),independent_examples=len({x['example_id'] for x in valid}),errors=errors,aggregate={str(a):dict(k=sum(r['counts'][str(a)] for r in ks),n=1000*len(valid)) for a in f['alphas']},per_text=accum,warning='Text-key pairs are dependent; not independent sample count. No threshold retuning.'))
if __name__=='__main__':main()
