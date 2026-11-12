from common_adjusted import *
import concurrent.futures,os,time
sys.path.insert(0,str(PREV));import ocr_parallel as impl
impl.O=O;D=O/'T5_ocr'
def work(wid):
 engine,font=impl.load_engine();folder=D/('images_'+str(wid));folder.mkdir();n=0
 for x in read(D/'TASKS.json'):
  try:put(D/'claims'/(x['id']+'.json'),dict(worker=wid,pid=os.getpid()))
  except FileExistsError:continue
  tick=time.monotonic();r=dict(id=x['id'],source_id=x['source_id'],method=x['method'],status='FAILED')
  try:
   out,pages=impl.recognize(engine,font,x,folder);(D/'texts'/(x['id']+'.txt')).write_bytes(out.encode());r.update(status='COMPLETE',pages=pages,input_sha256=hashlib.sha256(x['text'].encode()).hexdigest(),output_sha256=hashlib.sha256(out.encode()).hexdigest())
  except Exception as e:r['error']=type(e).__name__+': '+str(e)
  r['seconds']=time.monotonic()-tick;impl.atomic(D/'records'/(x['id']+'.json'),r);n+=1
 return dict(worker=wid,processed=n)
def main():
 D.mkdir(exist_ok=False)
 for n in ['claims','texts','records']:(D/n).mkdir()
 tasks=[dict(id='T5__'+x['id']+'__Fingerprint',method='Fingerprint',source_id=x['id'],text=x['text']) for x in read(O/'T5_SOURCES.json')]
 for r in read(O/'T5_insertion/INSERT_T5_all_RESULT.json')['rows']:
  if r['status']=='PREDICTED_TARGET_REACHED':tasks.append(dict(id=r['id'],method=r['method'],source_id=r['source_id'],text=(O/'T5_insertion/outputs'/(r['id']+'.txt')).read_text(encoding='utf8')))
 put(D/'TASKS.json',tasks);put(D/'START.json',dict(workers=8,tasks=len(tasks),unix=time.time(),same_Batch01_CPU_OCR=True))
 with concurrent.futures.ProcessPoolExecutor(max_workers=8) as pool:rows=list(pool.map(work,range(8)))
 put(D/'FINISHED.json',dict(workers=rows,tasks=len(tasks),unix=time.time()))
if __name__=='__main__':main()
