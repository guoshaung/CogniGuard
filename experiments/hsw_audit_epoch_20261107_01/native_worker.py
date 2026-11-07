"""Read-only existing native provider; no Torch in this runtime process."""
import os,sys,json,hashlib
from multiprocessing import shared_memory
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,'D:/pycharm/CogniGuard/var/results/hsw_copyright_transfer01_20261106/engine')
import numpy as np
from native_adapter import NativeModel
model=None;shm=None
try:
 model=NativeModel(sys.argv[1],int(sys.argv[3]))
 shm=shared_memory.SharedMemory(name=sys.argv[2]);buf=np.ndarray((model.vocab,),dtype=np.float32,buffer=shm.buf)
 print(json.dumps({'ready':True,'vocab':model.vocab,'pid':os.getpid()}),flush=True)
 for line in sys.stdin:
  x=json.loads(line)
  if x['op']=='close':break
  if x['op']=='clear':model.clear();r={'ok':True}
  elif x['op']=='forward':
   logits=model.forward(x['ids']);buf[:]=logits;r={'ok':True,'finite':bool(np.isfinite(logits).all()),'sha256':hashlib.sha256(logits.tobytes()).hexdigest()}
  else:raise ValueError('unsupported operation')
  print(json.dumps(r),flush=True)
finally:
 if model:model.close()
 if shm:shm.close()
