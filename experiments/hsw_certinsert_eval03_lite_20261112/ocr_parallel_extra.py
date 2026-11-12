"""Same OCR/render configuration; exclusive per-task claims, CPU processes only."""
from initialize import *
import os,sys,time,textwrap
os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2';os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True';os.environ['PADDLE_PDX_CACHE_HOME']=str(E1/'runtime/pdxcache')
D=O/'ocr';P=D/'parallel01'
def atomic(p,value):
 t=p.with_suffix(p.suffix+'.tmp'+str(os.getpid()));t.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.replace(t,p)
def load_engine():
 from paddleocr import PaddleOCR
 from PIL import ImageFont
 f=read(E1/'OCR_RENDER_FREEZE.json');assert sha(Path(f['font']))==f['font_sha256']
 font=ImageFont.truetype(f['font'],20)
 engine=PaddleOCR(text_detection_model_name='PP-OCRv4_mobile_det',text_detection_model_dir=str(E1/'runtime/ocr_models/PP-OCRv4_mobile_det'),text_recognition_model_name='en_PP-OCRv4_mobile_rec',text_recognition_model_dir=str(E1/'runtime/ocr_models/en_PP-OCRv4_mobile_rec'),use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,device='cpu',cpu_threads=2,enable_mkldnn=False)
 return engine,font

def recognize(engine,font,x,folder):
 from PIL import Image,ImageDraw
 lines=[]
 for line in x['text'].splitlines():lines.extend(textwrap.wrap(line,width=85,replace_whitespace=False,drop_whitespace=False) or [''])
 texts=[];pages=[]
 for at in range(0,len(lines),60):
  im=Image.new('RGB',(1000,1800),'white');draw=ImageDraw.Draw(im)
  for j,line in enumerate(lines[at:at+60]):draw.text((40,30+28*j),line,font=font,fill='black')
  ip=folder/(x['id']+f'__{at//60:03d}.png');assert not ip.exists();im.save(ip)
  words=[];confidence=[]
  for v in engine.predict(input=str(ip)):words.extend(v['rec_texts']);confidence.extend(float(q) for q in v['rec_scores'])
  texts.append('\n'.join(words));pages.append(dict(image=ip.relative_to(O).as_posix(),sha256=sha(ip),texts=words,confidence=confidence))
 return '\n\n'.join(texts),pages

def main():
 mode=sys.argv[1];P.mkdir(exist_ok=True)
 if mode=='probe':
  engine,font=load_engine();folder=P/'probe_images';folder.mkdir(exist_ok=True)
  tasks={x['id']:x for x in read(P/'TASKS.json')};records=[read(p) for p in (D/'records').glob('*.json')];records=sorted([r for r in records if r.get('status')=='COMPLETE' and len(r.get('pages',[]))==1],key=lambda r:r['seconds'])[:2];assert len(records)==2
  results=[]
  for r in records:
   t=time.monotonic();out,pages=recognize(engine,font,tasks[r['id']],folder);expected=(D/'texts'/(r['id']+'.txt')).read_bytes();results.append(dict(id=r['id'],text_bytes_equal=out.encode()==expected,render_bytes_equal=[p['sha256'] for p in pages]==[p['sha256'] for p in r['pages']],seconds=time.monotonic()-t))
  put(P/'PROBE.json',dict(rows=results,PASS=all(r['text_bytes_equal'] and r['render_bytes_equal'] for r in results),purpose='engineering equivalence, not new experimental samples'));print(results,flush=True);return
 wid=mode;assert read(P/'PROBE.json')['PASS'];assert (P/'MIGRATION.json').exists();engine,font=load_engine();folder=P/('images_'+wid);folder.mkdir(exist_ok=True);tick=time.monotonic();n=0
 for x in read(P/'TASKS.json'):
  rp=D/'records'/(x['id']+'.json')
  if rp.exists():continue
  if (P/('STOP_'+wid)).exists():break
  if time.time()>read(P/'PLAN.json')['deadline_unix']:break
  claim=P/'claims'/(x['id']+'.json')
  try:put(claim,dict(pid=os.getpid(),worker=wid,unix=time.time(),id=x['id']))
  except FileExistsError:continue
  if rp.exists():continue
  start=time.monotonic();row=dict(id=x['id'],source_id=x['source_id'],method=x['method'],input_sha256=hashlib.sha256(x['text'].encode()).hexdigest(),status='FAILED',worker=wid,parallel_queue=True)
  try:
   out,pages=recognize(engine,font,x,folder);tp=D/'texts'/(x['id']+'.txt');assert not tp.exists(),'UNCOMMITTED_PRIOR_TEXT_REQUIRES_AUDIT'
   tmp=tp.with_suffix('.txt.tmp'+wid);tmp.write_bytes(out.encode());os.replace(tmp,tp);row.update(status='COMPLETE',pages=pages,output_sha256=hashlib.sha256(out.encode()).hexdigest(),exact_byte_cache_reuse=False)
  except Exception as e:row['error']=type(e).__name__+': '+str(e)
  row['seconds']=time.monotonic()-start;assert not rp.exists();atomic(rp,row);n+=1
  if n%10==0:print(wid,n,round(time.monotonic()-tick),flush=True)
 put(P/(wid+'_DONE.json'),dict(worker=wid,processed=n,seconds=time.monotonic()-tick,pid=os.getpid()))
if __name__=='__main__':main()
