"""Bounded 4->8 CPU throughput test. Existing OCR workers stay running."""
from initialize import *
import ctypes,os,time,subprocess
P=O/'ocr/parallel01';D=O/'ocr'
def count():return len(list((D/'records').glob('*.json')))
def main():
 assert not (D/'FINISHED.json').exists();pid=read(P/'COORDINATOR_START.json')['pid']
 cmd=subprocess.check_output(['powershell','-NoProfile','-Command',f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],text=True)
 assert 'ocr_parallel_coordinator.py' in cmd,'COORDINATOR_IDENTITY'
 k=ctypes.WinDLL('kernel32',use_last_error=True);nt=ctypes.WinDLL('ntdll');k.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];k.OpenProcess.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p];nt.NtSuspendProcess.argtypes=[ctypes.c_void_p];nt.NtResumeProcess.argtypes=[ctypes.c_void_p]
 handle=k.OpenProcess(0x0800,False,pid);assert handle,'OPEN_OWN_COORDINATOR'
 jobs=[];suspended=False;t0=time.time();n0=count();deadline=read(P/'PLAN.json')['deadline_unix']
 put(P/'SCALE8_START.json',dict(unix=t0,total_before=n0,coordinator_pid=pid,supervisor_pid=os.getpid(),baseline_per_minute=32/3,trial_seconds=150,required_improvement=1.1,workers=8,threads_each=2,completion_barrier='Pause only own coordinator while extra workers run; existing four workers keep running. Resume in finally.',code_sha256=sha(Path(__file__))))
 try:
  assert nt.NtSuspendProcess(handle)==0;suspended=True
  for i in range(5,9):
   wid='worker'+str(i);log=(P/(wid+'.log')).open('xb');env=dict(os.environ,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1');pr=subprocess.Popen([str(E1/'runtime/ocr/Scripts/python.exe'),str(E/'ocr_parallel_extra.py'),wid],cwd=str(E),env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));jobs.append((wid,pr,log));put(P/(wid+'_PID.json'),dict(pid=pr.pid,worker=wid));time.sleep(2)
  print('EIGHT_WORKERS_ACTIVE',flush=True)
  trial=time.time();start_count=count()
  while time.time()-trial<150 and any(p.poll() is None for _,p,_ in jobs):time.sleep(5)
  seconds=time.time()-trial;done=count()-start_count;rate=done/seconds*60;keep=rate>=(32/3)*1.1
  put(P/'SCALE8_TRIAL.json',dict(seconds=seconds,completed=done,per_minute=rate,baseline_per_minute=32/3,keep_extra_workers=keep,limits='Different task lengths, warm-up included; engineering scheduling observation, not scientific model performance.'))
  print('TRIAL',done,round(rate,2),'KEEP',keep,flush=True)
  if not keep:
   for wid,_,_ in jobs:(P/('STOP_'+wid)).write_text('Throughput benefit below10%; finish current task and stop. No retry.',encoding='utf8')
  while any(p.poll() is None for _,p,_ in jobs):
   if time.time()>deadline:
    for _,pr,_ in jobs:
     if pr.poll() is None:pr.terminate()
    break
   time.sleep(5)
 finally:
  for wid,pr,log in jobs:
   if pr.poll() is None:
    (P/('STOP_'+wid)).write_text('Supervisor cleanup; finish current task.',encoding='utf8')
    try:pr.wait(timeout=120)
    except subprocess.TimeoutExpired:pr.terminate();pr.wait(timeout=20)
   log.close()
  if suspended:
   code=nt.NtResumeProcess(handle);assert code==0,'RESUME_COORDINATOR_FAILED'
  k.CloseHandle(handle)
  put(P/'SCALE8_FINISHED.json',dict(unix=time.time(),total_after=count(),coordinator_resumed=True,workers=[dict(worker=w,returncode=p.returncode) for w,p,_ in jobs]))
  print('EXTRA_WORKERS_DONE_COORDINATOR_RESUMED',flush=True)
if __name__=='__main__':main()
