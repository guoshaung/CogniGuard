"""Bounded delivery follower; never launches generation or repeats experiments."""
from common_adjusted import *
import time,os

def main():
    put(O/'ARCHIVE_FOLLOWER_STARTED.json',dict(unix=time.time(),script_sha256=sha(Path(__file__)),generation=False))
    start=time.monotonic()
    while not (O/'PIPELINE_FINISHED.json').exists():
        if (O/'PIPELINE_FAILURE.json').exists():raise RuntimeError('UPSTREAM_FAILURE: inspect preserved PIPELINE_FAILURE.json')
        if time.monotonic()-start>21600:raise TimeoutError('DELIVERY_WAIT_LIMIT')
        time.sleep(15)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    def run(script,*args):
        subprocess.run([sys.executable,str(E/script),*args],cwd=W,env=env,check=True)
    run('report_t5.py');run('package_remaining.py','P3-P4');run('publish_stage.py','P3-P4')
    run('report_expanded.py');run('package_remaining.py','P1-expanded');run('publish_stage.py','P1-expanded')
    put(O/'DELIVERY_FINISHED.json',dict(unix=time.time(),stages=['P3-P4','P1-expanded'],P4='WAITING_TWO_INDEPENDENT_HUMANS',P5='OPTIONAL_NOT_STARTED',new_generation_started=False))

if __name__=='__main__':
    try:main()
    except Exception as e:
        put(O/'DELIVERY_FAILURE.json',dict(unix=time.time(),error=type(e).__name__+': '+str(e)));raise
