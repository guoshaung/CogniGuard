"""Same1000 diagnostic keys, unchanged selection; cache deterministic anchor extraction only."""
from common_adjusted import *
import time,collections,numpy as np
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));from prepare_cpu import make_detector,R,OLD
import e1_v4r8_selector as sm
from e1_v4r7f_anchors import anchors
from e1_v4r3_core import exact,pb_tail

def main():
 d=O/'P6/key_stress';d.mkdir(exist_ok=False);f=read(PREV/'KEY_STRESS_FREEZE.json');data=(BASE/'restricted/diagnostic_keys.bin').read_bytes();assert hashlib.sha256(data).hexdigest()==f['aggregate_sha256'];rows=read(O/'data/P6_BACKGROUND.json');vocab=read(R/'VOCABULARY.json');freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];det,_=make_detector(vocab);ac={};valid=[];errors=[]
 for x in rows:
  try:ac[x['text']]=anchors(x['text']);valid.append(x)
  except Exception as e:errors.append(dict(id=x['id'],error=str(e)))
 ac['']=anchors('');original=sm.anchors
 sm.anchors=lambda text:ac[text] if text in ac else original(text)
 # Cache values are byte-for-byte same lists, not a changed extraction rule.
 assert all(ac[x['text']]==original(x['text']) for x in valid)
 texts=['\n'.join(ac[x['text']]) for x in valid if len(ac[x['text']])>=5]
 for i in range(0,len(texts),16):det.embed(texts[i:i+16])
 table=det.embed([x['text'] for x in read(OLD/'development_round01/SECTABLE_CORPUS.json')[:len(vocab)]]);p_cache={};acc={m:{x['id']:{str(a):0 for a in f['alphas']} for x in valid} for m in ['CertInsert','RC']};per=[]
 put(d/'START.json',dict(unix=time.time(),keys=1000,keys_commitment=f['aggregate_sha256'],data_sha256=sha(O/'data/P6_BACKGROUND.json'),cache_exact_verified=True,thresholds=f['alphas']))
 with (d/'PER_KEY.jsonl').open('x',encoding='utf8') as log:
  for j in range(1000):
   key=data[j*32:(j+1)*32];order=sorted(range(len(vocab)),key=lambda i:hashlib.sha256(key+b'|sectable|'+str(i).encode()).digest());det.table=table[order];sel=sm.selector(det,key,4,vocab);glob=sel('');cc={m:{str(a):0 for a in f['alphas']} for m in acc}
   for x in valid:
    for m,ws in [('CertInsert',sel(x['text'])),('RC',glob)]:
     k=(x['id'],tuple(ws))
     if k not in p_cache:p_cache[k]=pb_tail([freq[w] for w in ws],sum(exact(x['text'],w) for w in ws))
     pv=p_cache[k]
     for a in f['alphas']:v=int(pv<a);cc[m][str(a)]+=v;acc[m][x['id']][str(a)]+=v
   r=dict(key_id=f'DIAG_{j+1:04d}',n=len(valid),counts=cc);log.write(json.dumps(r)+'\n');per.append(r)
   if j%100==0:print('P6 key',j,flush=True)
 put(d/'RESULT.json',dict(keys=1000,passages=len(valid),errors=errors,independent_source_modules=len({x['source']['id'] for x in valid}),aggregate={m:{str(a):dict(k=sum(r['counts'][m][str(a)] for r in per),n=len(valid)*1000) for a in f['alphas']} for m in acc},per_text=acc,warning='Dependent text-key trials, not500000 independent passages; no threshold fitting.'))
 print('P6 STRESS COMPLETE',flush=True)
if __name__=='__main__':main()
