from initialize import *
import os,time,textwrap
os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2';os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True';os.environ['PADDLE_PDX_CACHE_HOME']=str(E1/'runtime/pdxcache')
def main():
 from PIL import Image,ImageDraw,ImageFont
 from paddleocr import PaddleOCR
 dest=O/'ocr';dest.mkdir(exist_ok=True);(dest/'images').mkdir(exist_ok=True);(dest/'texts').mkdir(exist_ok=True);(dest/'records').mkdir(exist_ok=True)
 assert not (dest/'START.json').exists();put(dest/'START.json',dict(unix=time.time(),device='cpu',max_wall_seconds=10800))
 f=read(E1/'OCR_RENDER_FREEZE.json');assert sha(Path(f['font']))==f['font_sha256'];font=ImageFont.truetype(f['font'],20)
 engine=PaddleOCR(text_detection_model_name='PP-OCRv4_mobile_det',text_detection_model_dir=str(E1/'runtime/ocr_models/PP-OCRv4_mobile_det'),text_recognition_model_name='en_PP-OCRv4_mobile_rec',text_recognition_model_dir=str(E1/'runtime/ocr_models/en_PP-OCRv4_mobile_rec'),use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,device='cpu',cpu_threads=2,enable_mkldnn=False)
 sources=read(O/'materials02/T4.json');start=time.monotonic();cache={};count=0
 while time.monotonic()-start<10800:
  tasks=[dict(id='T4__'+x['id']+'__Fingerprint',text=x['text'],source_id=x['id'],method='Fingerprint') for x in sources]
  for root in [O,O/'scoring_recovery01']:
   for path in (root/'records').glob('T4__*.json'):
    r=read(path)
    if r.get('status')=='PREDICTED_TARGET_REACHED':tasks.append(dict(id=r['id'],source_id=r['source_id'],method=r['method'],text=(root/'outputs'/(r['id']+'.txt')).read_text(encoding='utf8')))
  todo=[x for x in tasks if not (dest/'records'/(x['id']+'.json')).exists()]
  for x in todo:
   if time.monotonic()-start>=10800:break
   tick=time.monotonic();digest=hashlib.sha256(x['text'].encode()).hexdigest();r=dict(id=x['id'],source_id=x['source_id'],method=x['method'],input_sha256=digest,status='FAILED');pages=[]
   try:
    if digest in cache:out,pages=cache[digest];r['exact_byte_cache_reuse']=True
    else:
     lines=[]
     for line in x['text'].splitlines():lines.extend(textwrap.wrap(line,width=85,replace_whitespace=False,drop_whitespace=False) or [''])
     texts=[]
     for at in range(0,len(lines),60):
      im=Image.new('RGB',(1000,1800),'white');draw=ImageDraw.Draw(im)
      for j,line in enumerate(lines[at:at+60]):draw.text((40,30+28*j),line,font=font,fill='black')
      ip=dest/'images'/(x['id']+f'__{at//60:03d}.png');im.save(ip);rr=list(engine.predict(input=str(ip)));words=[];confidence=[]
      for v in rr:words.extend(v['rec_texts']);confidence.extend(float(q) for q in v['rec_scores'])
      texts.append('\n'.join(words));pages.append(dict(image=ip.relative_to(O).as_posix(),sha256=sha(ip),texts=words,confidence=confidence))
     out='\n\n'.join(texts);cache[digest]=(out,pages);r['exact_byte_cache_reuse']=False
    with (dest/'texts'/(x['id']+'.txt')).open('x',encoding='utf8',newline='') as f:f.write(out)
    r.update(status='COMPLETE',pages=pages,output_sha256=hashlib.sha256(out.encode()).hexdigest())
   except Exception as e:r['error']=type(e).__name__+': '+str(e)
   r['seconds']=time.monotonic()-tick;put(dest/'records'/(x['id']+'.json'),r);count+=1
   if count%20==0:print('OCR',count,round(time.monotonic()-start),flush=True)
  done=(O/'scoring_recovery01/INSERT_T4_all_RESULT.json').exists()
  if done and not todo:break
  if not todo:time.sleep(5)
 put(dest/'FINISHED.json',dict(attempted=count,seconds=time.monotonic()-start,gpu=0,paid_API=0,generation_done=(O/'scoring_recovery01/INSERT_T4_all_RESULT.json').exists()))
if __name__=='__main__':main()
