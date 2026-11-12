"""Real frozen detector, separate public attack construction, zero GPU/API."""
from common_adjusted import *
import math,time,collections,numpy as np
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'))
from prepare_cpu import make_detector,R,OLD
import e1_v4r8_selector as sm
from e1_v4r7f_anchors import anchors,numbers,forms
from e1_v4r3_core import exact,pb_tail

def main():
 mode=sys.argv[1];d=O/mode;d.mkdir(exist_ok=True);(d/'scores').mkdir(exist_ok=True)
 put(d/'SCORE_STARTED.json',dict(unix=time.time(),mode=mode,code_sha256=sha(Path(__file__)),GPU=0,API=0))
 vocab=read(R/'VOCABULARY.json');freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];det,key=make_detector(vocab);sel=sm.selector(det,key,4,vocab);glob=sel('');rows=[]
 tasks=read(O/'P1/TASKS.json') if mode=='P1' else [dict(x,method=m,attack='background') for x in read(O/'data/P6_BACKGROUND.json') for m in ['CertInsert','RC']]
 for x in tasks:
  out=d/'scores'/(x['id']+('__'+x['method'] if mode!='P1' else '')+'.json')
  if out.exists():rows.append(read(out));continue
  r={k:v for k,v in x.items() if k not in ['text','source']};r.update(detected=None,p=None)
  try:
   ws=glob if x['method']=='RC' else sel(x['text']);hits=sum(exact(x['text'],w) for w in ws);pv=pb_tail([freq[w] for w in ws],hits);r.update(selected_public=ws,hits=hits,p=pv,detected=pv<.01,scorable=True)
  except Exception as e:r.update(scorable=False,error=type(e).__name__+': '+str(e))
  put(out,r);rows.append(r)
  if len(rows)%100==0:print(mode,'scored',len(rows),flush=True)
 counts={};rng=np.random.default_rng(2026111206)
 def summarize(rr):
  valid=[r for r in rr if isinstance(r['detected'],bool)];groups=collections.defaultdict(list)
  for r in valid:groups[r.get('cluster',r.get('chapter',r['id']))].append(r['detected'])
  k=sum(r['detected'] for r in valid);n=len(valid);ci=None
  if groups:
   a=np.array([[sum(v),len(v)] for v in groups.values()]);s=a[rng.integers(len(a),size=(2000,len(a)))].sum(1);ci=[float(v) for v in np.quantile(s[:,0]/s[:,1],[.025,.975])]
  z=1.959963984540054;wil=None
  if n:
   p=k/n;c=(p+z*z/(2*n))/(1+z*z/n);h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n);wil=[c-h,c+h]
  return dict(k=k,n=n,planned_actual=len(rr),unknown=len(rr)-n,source_clusters=len(groups),cluster_bootstrap95=ci,descriptive_wilson95=wil)
 for method in ['CertInsert','RC']:
  counts[method]={}
  if mode=='P1':
   for N in [10,50,200]:
    for m in [4,8]:
     label=f'N{N}_m{m}';counts[method][label]={a:summarize([r for r in rows if r['method']==method and r['N']==N and r['m']==m and r['attack']==a]) if any(r['method']==method and r['N']==N and r['m']==m for r in rows) else None for a in ['spoofing','scrubbing']}
  else:counts[method]=summarize([r for r in rows if r['method']==method])
 put(d/'RESULT.json',dict(counts=counts,rows=len(rows),GPU=0,API=0,threshold=.01,warning='Source-cluster bootstrap; degenerate zero-event intervals do not certify global zero risk. Wilson ignores chapter dependence. NOT_AVAILABLE is not zero.'))
 print(mode,'COMPLETE',json.dumps(counts),flush=True)
if __name__=='__main__':main()
