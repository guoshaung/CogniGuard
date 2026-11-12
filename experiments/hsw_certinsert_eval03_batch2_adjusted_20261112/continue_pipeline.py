"""Wait for existing T5 jobs, freeze exact texts, then execute already-authorized stages."""
from common_adjusted import *
import time,os,re,concurrent.futures
PY=W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded/protocol_v3/runtime/Scripts/python.exe'
OCR=W/'var/results/hsw-st/certinsert_eval_20261111_01/run01/runtime/ocr/Scripts/python.exe'
BASEPY=Path('D:/pycharm/CogniGuard/.venv/Scripts/python.exe')
def launch(script,args=(),python=PY):
 env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1');r=subprocess.run([str(python),str(E/script),*args],cwd=W,env=env);assert r.returncode==0,(script,r.returncode)
def commit(paths,msg):
 rel=[p.relative_to(W).as_posix() for p in paths];subprocess.run(['git','add','--sparse','--',*rel],cwd=W,check=True);subprocess.run(['git','commit','--only','-m',msg,'--',*rel],cwd=W,check=True)
def main():
 put(O/'PIPELINE_STARTED.json',dict(unix=time.time(),code_sha256=sha(Path(__file__)),scope='T5 insertion/OCR/public evaluation/expanded attack preparation/human package, no P5'))
 tick=time.monotonic()
 while not((O/'P3/RESULT.json').exists() and (O/'T5_prepared/FINISHED.json').exists()):
  if time.monotonic()-tick>14400:raise TimeoutError('WAIT_LIMIT_EXISTING_T5_JOBS')
  time.sleep(10)
 gen=read(O/'P3/RESULT.json');plans=read(O/'T5_prepared/PLANS.json');pp={p['source_id']:p for p in plans};qq={x['id']:x for x in read(O/'data/T5_QUESTIONS.json')};src=[];missing=[]
 for r in gen['rows']:
  sid=r['source_id'];tp=O/'P3/outputs'/(r['id']+'.txt')
  if r['status']!='COMPLETED' or not tp.exists() or not tp.read_text(encoding='utf8').strip():missing.append(dict(id=sid,status=r['status']));continue
  t=tp.read_text(encoding='utf8');x=dict(qq[sid],text=t,text_sha256=sha(tp),explanation_words=pp.get(sid,{}).get('explanation_words',0),source_generation_status=r['status'],natural_eos=r.get('stop_type')=='eos',body_start=0);src.append(x)
 put(O/'T5_SOURCES.json',src);put(E/'T5_TEXT_FREEZE.json',dict(planned=200,attempted=gen['attempted'],actual_sources=len(src),missing=missing,texts_sha256=sha(O/'T5_SOURCES.json'),plans_sha256=sha(O/'T5_prepared/PLANS.json'),capacity_sha256=sha(O/'T5_prepared/CAPACITY.json'),format_only=True,source_quality_not_gold=True));commit([E/'T5_TEXT_FREEZE.json'],'Freeze actual T5 text and prepared insertion plans before scoring')
 launch('insert_t5.py',['T5','all'])
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  a=pool.submit(launch,'ocr_t5.py',(),OCR);b=pool.submit(launch,'evaluate_t5.py');a.result();b.result()
 launch('freeze_expanded_pool.py',python=BASEPY);commit([E/'EXPANDED_POOL_FREEZE.json'],'Freeze expanded observation pool before frequency attacks')
 launch('prepare_expanded_attacks.py');commit([E/'P1_EXPANDED_INPUT_FREEZE.json'],'Freeze expanded attack texts before true-key scoring')
 launch('score_expanded.py',['P1_expanded']);launch('prepare_human.py',python=BASEPY)
 put(O/'PIPELINE_FINISHED.json',dict(unix=time.time(),stages=['T5_insertion','T5_OCR','T5_public_detection','P1_expanded','P4_package'],human_labels='PENDING_NOT_FILLED',P5='NOT_STARTED_OPTIONAL'))
if __name__=='__main__':
 try:main()
 except Exception as e:
  put(O/'PIPELINE_FAILURE.json',dict(unix=time.time(),error=type(e).__name__+': '+str(e)));raise
