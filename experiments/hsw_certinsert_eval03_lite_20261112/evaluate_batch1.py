"""CPU public scores and source matching, no model generation."""
from initialize import *
import sys,re,csv,time,numpy as np
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'))
from prepare_cpu import make_detector,R,OLD
from e1_v4r8_selector import selector
from e1_v4r7f_anchors import anchors,numbers,forms
from e1_v4r3_core import exact,pb_tail

def main():
 z=O/'evaluation_batch1';z.mkdir(exist_ok=True);(z/'records').mkdir(exist_ok=True);(z/'quality').mkdir(exist_ok=True);(z/'crops').mkdir(exist_ok=True)
 sources=read(O/'materials02/T4.json');src={x['id']:x for x in sources};freq=read(E2/'DOMAIN_FREQUENCIES.json')['probabilities'];det,key=make_detector(read(R/'VOCABULARY.json'));sel=selector(det,key,4,read(R/'VOCABULARY.json'));glob=sel('')
 mf=read(OLD/'attack_three_seed_round01/FINGERPRINT_FREEZE.json');prime=mf['prime'];rng=np.random.default_rng(mf['seed']);a=rng.integers(1,prime,128,dtype=np.uint64);b=rng.integers(0,prime,128,dtype=np.uint64)
 def sig(t):
  fs=anchors(t)
  if not fs:return None
  h=np.array([int.from_bytes(hashlib.sha256(x.encode()).digest()[:4],'little')%prime for x in fs],dtype=np.uint64)
  return ((a[:,None]*h+b[:,None])%prime).min(1)
 corpus={x['id']:x for x in read(OLD/'attack_three_seed_round01/FINGERPRINT_CORPUS.json')}
 for x in sources+read(O/'materials02/IN_DOMAIN.json'):corpus[x['id']]=x
 ids=[];ss=[];badindex=[]
 for i,x in corpus.items():
  try:s=sig(x['text'])
  except Exception as e:badindex.append(dict(id=i,error=str(e)));continue
  if s is not None:ids.append(i);ss.append(s)
 mat=np.stack(ss);put(z/'FINGERPRINT_INDEX.json',dict(ids=ids,empty_or_invalid_excluded=len(corpus)-len(ids),errors=badindex,rule='same full source index for all methods; unique positive maximum else reject/ambiguous',freeze=mf))
 started=time.monotonic();count=0
 while True:
  tasks=[dict(id='T4__'+x['id']+'__Fingerprint',method='Fingerprint',source_id=x['id'],text=x['text'],base=None,attack='none') for x in sources]
  for root in [O,O/'scoring_recovery01']:
   for p in (root/'records').glob('T4__*.json'):
    r=read(p)
    if r.get('status')=='PREDICTED_TARGET_REACHED':tasks.append(dict(id=r['id'],method=r['method'],source_id=r['source_id'],text=(root/'outputs'/(r['id']+'.txt')).read_text(encoding='utf8'),base=r,attack='none'))
  orig=list(tasks)
  for t in orig:
   matches=list(re.finditer(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",t['text']))
   if len(matches)>=100:
    for kind,at in [('crop_first100',0),('crop_middle100',(len(matches)-100)//2)]:
     tx=t['text'][matches[at].start():matches[at+99].end()];item=dict(t,id=t['id']+'__'+kind,attack=kind,text=tx);tasks.append(item);p=z/'crops'/(item['id']+'.txt')
     if not p.exists():p.write_bytes(tx.encode())
   p=O/'ocr/records'/(t['id']+'.json')
   if p.exists() and read(p)['status']=='COMPLETE':tasks.append(dict(t,id=t['id']+'__ocr',attack='ocr',text=(O/'ocr/texts'/(t['id']+'.txt')).read_text(encoding='utf8')))
  todo=[t for t in tasks if not (z/'records'/(t['id']+'.json')).exists()]
  for t in todo:
   x=src[t['source_id']];text=t['text'];row={k:t[k] for k in ['id','source_id','method','attack']};row.update(kind='evaluation',dataset='T4',explanation_words=x['explanation_words'],input_sha256=x['text_sha256'],output_sha256=hashlib.sha256(text.encode()).hexdigest(),detected=None,certificate=None,anchor_invariant=None,selection_invariant=None,numeric_formula_intact=None)
   try:
    aa=anchors(x['text']);ab=anchors(text);row['anchor_invariant']=aa==ab;row['numeric_formula_intact']=set(numbers(x['text']))<=set(numbers(text)) and set(forms(x['text']))<=set(forms(text));row['knowledge']='MECHANICAL_ONLY_NOT_SEMANTIC_GOLD'
    if t['base'] and t['attack']=='none':
     restored=text
     for s in reversed(t['base']['spans']):restored=restored[:s['start']]+restored[s['end']:]
     chars=list(restored)
     for c in t['base']['case_changes']:
      assert chars[c['offset']]==c['after'];chars[c['offset']]=c['before']
     row['certificate']=''.join(chars).encode()==x['text'].encode()
   except Exception as e:row['quality_error']=type(e).__name__+': '+str(e)
   qp=z/'quality'/(t['id']+'.json')
   if not qp.exists():put(qp,dict(row,watermark_score_not_yet_computed=True))
   try:
    ws=glob if t['method']=='RC' else sel(text);pv=pb_tail([freq[w] for w in ws],sum(exact(text,w) for w in ws));row.update(p=pv,selected_public=ws,detected=pv<.01 if t['method']!='Fingerprint' else None)
    if t['base']:row['selection_invariant']=ws==t['base']['selected']
   except Exception as e:row['detection_error']=str(e)
   try:
    s=sig(text)
    if s is None:pred='REJECT';mx=0
    else:
     scores=(mat==s).mean(1);mx=float(scores.max());wins=[ids[j] for j,v in enumerate(scores) if v==mx];pred=wins[0] if len(wins)==1 and mx>0 else 'AMBIGUOUS' if mx>0 else 'REJECT'
    row.update(fingerprint_prediction=pred,fingerprint_correct=pred==x['id'],fingerprint_wrong=pred not in [x['id'],'REJECT','AMBIGUOUS'],fingerprint_score=mx)
    if t['method']=='Fingerprint':row['detected']=row['fingerprint_correct']
   except Exception as e:row['fingerprint_error']=str(e)
   put(z/'records'/(t['id']+'.json'),row);count+=1
   if count%100==0:print('CPU_EVAL',count,flush=True)
  if (O/'ocr/FINISHED.json').exists() and (O/'scoring_recovery01/INSERT_T4_all_RESULT.json').exists() and not todo:break
  if time.monotonic()-started>14400:break
  if not todo:time.sleep(5)
 put(z/'FINISHED.json',dict(rows=count,seconds=time.monotonic()-started,ocr_finished=(O/'ocr/FINISHED.json').exists()))
if __name__=='__main__':main()
