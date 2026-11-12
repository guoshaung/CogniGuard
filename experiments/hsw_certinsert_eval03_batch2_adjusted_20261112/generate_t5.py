"""Frozen T5 question-only generation, two slots, no retry; safe own-worker cleanup."""
from common_adjusted import *
import time,concurrent.futures,threading
sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'));import runtime7b as rt

def main():
 d=O/'P3';d.mkdir(exist_ok=False)
 for n in ['records','outputs']:(d/n).mkdir()
 f=read(E1/'EVAL_FREEZE.json');f['T3_prompt']=read(PREV/'EVAL_FREEZE.json')['prompts']['T3_prompt'];put(d/'EVAL_FREEZE.json',f)
 assert sha(Path(f['server']))==f['server_sha256']
 for name,digest in read(PREV/'EVAL_FREEZE.json')['model7b_parts'].items():
  assert sha(Path(f['model7b']).parent/name)==digest
 rt.O=d
 def log(name,row):
  with (d/name).open('a',encoding='utf8') as fp:fp.write(json.dumps(row)+'\n')
 rt.failure=lambda ident,reason:log('FAILURES.jsonl',dict(id=ident,error=reason,unix=time.time()))
 rt.checkpoint=lambda stage,**kw:log('CHECKPOINTS.jsonl',dict(stage=stage,**kw))
 rows=[];server=None;tasks=read(O/'data/T5_QUESTIONS.json');put(d/'TASK_FREEZE.json',dict(inputs_sha256=sha(O/'data/T5_QUESTIONS.json'),n=len(tasks),source_only=True,temperature=.7,max_new_tokens=1024,seed_rule='SHA256(2026111205|T5_generation|id) first32bit &0x7fffffff',no_retry=True,stage_seconds=7200))
 try:
  server=rt.Server('T5',7200)
  def run(pair):
   i,x=pair;ident='T5__'+x['id'];sd=int(rank('T5_generation',x['id'])[:8],16)&0x7fffffff
   rr=server.complete(ident,f['T3_prompt'],x['question'],sd,dict(id_slot=i%2));rr.update(source_id=x['id']);return rr
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   for i in range(0,len(tasks),2):
    if time.monotonic()>=server.end or (O/'STOP_NEW_GENERATION').exists():break
    rows.extend(pool.map(run,enumerate(tasks[i:i+2],start=i)));rt.checkpoint('T5_PROGRESS',attempted=len(rows));print('T5',len(rows),flush=True)
 except Exception as e:rt.failure('T5_STAGE',type(e).__name__+': '+str(e))
 finally:
  if server:server.stop()
  put(d/'RESULT.json',dict(planned=len(tasks),attempted=len(rows),rows=rows,not_run=len(tasks)-len(rows),quality='FORMAT_ONLY_NO_REPAIR',own_server_stopped=True,paid_API=0))
if __name__=='__main__':main()

