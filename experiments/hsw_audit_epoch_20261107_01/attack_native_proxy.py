"""Attack-only 3B provider. Main 7B provider remains unchanged and frozen."""
import hashlib,json,os,subprocess,sys,threading,queue
from multiprocessing import shared_memory
from pathlib import Path
import numpy as np
class NativeModel:
 def __init__(self,model_path:Path,run:Path,threads=2):
  self.vocab=151936;self.calls=0;self.process=None
  self.shared=shared_memory.SharedMemory(create=True,size=self.vocab*4)
  self.buffer=np.ndarray((self.vocab,),dtype=np.float32,buffer=self.shared.buf)
  self.err=(run/'logs'/('native_'+self.shared.name+'.log')).open('xb');self.queue=queue.Queue()
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':str(threads)}
  self.process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('native_worker.py')),str(model_path),self.shared.name,str(threads)],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,cwd=run,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  def reader():
   for line in self.process.stdout:self.queue.put(line)
   self.queue.put(None)
  threading.Thread(target=reader,daemon=True).start()
  try:
   ready=self._read(120)
   if not ready.get('ready') or ready['vocab']!=self.vocab:raise RuntimeError('Attack model identity admission failed')
  except BaseException:
   self.close();raise
 def _read(self,timeout=90):
  try:line=self.queue.get(timeout=timeout)
  except queue.Empty:raise TimeoutError('Owned inference IPC timeout')
  if line is None:raise RuntimeError('Owned native process exited')
  return json.loads(line)
 def request(self,x):
  self.process.stdin.write((json.dumps(x)+'\n').encode());self.process.stdin.flush();r=self._read()
  if not r.get('ok'):raise RuntimeError('Native command failed')
  return r
 def clear(self):self.request({'op':'clear'})
 def forward(self,ids):
  r=self.request({'op':'forward','ids':list(map(int,ids))});self.calls+=1;raw=self.buffer.copy()
  if not r['finite'] or hashlib.sha256(raw.tobytes()).hexdigest()!=r['sha256']:raise RuntimeError('Nonfinite or IPC byte mismatch')
  return raw
 def close(self):
  if self.process and self.process.poll() is None:
   try:self.process.stdin.write(b'{"op":"close"}\n');self.process.stdin.flush();self.process.wait(timeout=30)
   except (OSError,subprocess.TimeoutExpired):self.process.kill();self.process.wait(timeout=10)
  if self.process:self.process.stdin.close();self.process.stdout.close()
  self.err.close();self.shared.close();self.shared.unlink()
