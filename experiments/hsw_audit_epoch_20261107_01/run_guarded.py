"""Prospective single-controller lease around the frozen generator.

Does not mutate or retry tasks. A live prior controller blocks startup even if
its old lease was released; PID reuse is checked against this exact script path.
"""
import argparse,json,msvcrt,os,subprocess,sys,time
from pathlib import Path
import psutil
from bootstrap import E,R,save
ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['probe','s2','s3','cal','reissue'],required=True);ap.add_argument('--check',action='store_true');a=ap.parse_args()
directory=R/'locks';directory.mkdir(exist_ok=True);handle=(directory/'single_controller.lock').open('a+b')
if handle.tell()==0:handle.write(b'0');handle.flush()
handle.seek(0)
try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
except OSError:print(json.dumps({'status':'GUARD_BLOCKED_LIVE_LEASE','formal_attempts_consumed':0}));raise SystemExit(2)
try:
 live=[]
 for p in R.glob('generation_*'):
  f=p/'LOADED.json'
  if not f.is_file() or (p/'EXITED.json').exists():continue
  loaded=json.loads(f.read_text(encoding='utf-8'));pid=loaded['controller_pid']
  try:
   command=psutil.Process(pid).cmdline()
   if any(Path(x).name=='run_generation.py' and Path(x).resolve()==(E/'run_generation.py').resolve() for x in command):live.append({'stage':p.name,'controller_pid':pid})
  except (psutil.NoSuchProcess,psutil.AccessDenied):pass
 if live:
  print(json.dumps({'status':'GUARD_BLOCKED_EXISTING_OWN_CONTROLLER','live':live,'formal_attempts_consumed':0}));raise SystemExit(2)
 avail=psutil.virtual_memory().available
 if avail<6.5*2**30:
  print(json.dumps({'status':'RESOURCE_WAIT_KEEP_7B','available_GiB':avail/2**30,'formal_attempts_consumed':0}));raise SystemExit(3)
 if a.check:
  print(json.dumps({'status':'GUARD_READY_NO_GENERATION','available_GiB':avail/2**30,'formal_attempts_consumed':0}));raise SystemExit(0)
 # Child remains the original frozen executor, with the same exact model input.
 child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(E/'run_generation.py'),'--phase',a.phase],cwd=E.parents[1])
 tag=str(time.time_ns());save(directory/('controller_'+tag+'.json'),{'phase':a.phase,'wrapper_pid':os.getpid(),'controller_pid':child.pid,
  'uses_unchanged_frozen_generator':True,'new_algorithm_or_retry':False})
 code=child.wait();raise SystemExit(code)
finally:
 handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1);handle.close()
