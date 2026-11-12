from initialize import *
import time,subprocess,os
P=O/'ocr/parallel01';D=O/'ocr';PY=E1/'runtime/ocr/Scripts/python.exe'
def main():
 assert read(P/'PROBE.json')['PASS'];assert (P/'MIGRATION.json').exists();assert not (P/'COORDINATOR_START.json').exists()
 put(P/'COORDINATOR_START.json',dict(unix=time.time(),pid=os.getpid(),workers=4,code_sha256=sha(Path(__file__))))
 jobs=[]
 for i in range(4):
  wid='worker'+str(i+1);log=(P/(wid+'.log')).open('xb');env=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1');pr=subprocess.Popen([str(PY),str(E/'ocr_parallel.py'),wid],cwd=str(E),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));jobs.append((wid,pr,log));put(P/(wid+'_PID.json'),dict(pid=pr.pid,worker=wid,command=[str(PY),str(E/'ocr_parallel.py'),wid]));time.sleep(3)
 print('FOUR_WORKERS_STARTED',flush=True);deadline=read(P/'PLAN.json')['deadline_unix'];timed_out=False
 while any(p.poll() is None for _,p,_ in jobs):
  if time.time()>deadline:
   timed_out=True
   for _,pr,_ in jobs:
    if pr.poll() is None:pr.terminate()
   break
  time.sleep(5)
 statuses=[]
 for w,p,log in jobs:
  try:code=p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.kill();code=p.wait()
  log.close();statuses.append(dict(worker=w,returncode=code))
 records=[read(p) for p in (D/'records').glob('*.json')];todo=[x['id'] for x in read(P/'TASKS.json') if not (D/'records'/(x['id']+'.json')).exists()]
 put(P/'RESULT.json',dict(workers=statuses,timed_out=timed_out,records=len(records),complete=sum(r['status']=='COMPLETE' for r in records),failed=sum(r['status']!='COMPLETE' for r in records),not_run=todo))
 put(D/'FINISHED.json',dict(attempted=len(records),complete=sum(r['status']=='COMPLETE' for r in records),not_run=len(todo),parallel=True,seconds=time.time()-read(D/'START.json')['unix'],gpu=0,paid_API=0,generation_done=True))
 print('OCR_FINISHED',len(records),'NOT_RUN',len(todo),flush=True)
if __name__=='__main__':main()
