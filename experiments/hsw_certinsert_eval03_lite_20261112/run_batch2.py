"""Two-slot original7B generation. All60 baseline sources attempted once; no retry."""
from initialize import *
import sys,os,time,socket,threading,urllib.request,queue,concurrent.futures
BASE=O;O=BASE/'batch02';F=read(O/'FREEZE.json');OLD=W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded'
sys.path.insert(0,'D:/pycharm/CogniGuard/var/results/hsw_gpu0_deploy_20261102_r21')
from kgw_ref.kgw import Greenlist
LOCK=threading.Lock()
def log(name,x):
 with LOCK:
  with (O/name).open('a',encoding='utf8') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n')
def failure(ident,e):log('FAILURES.jsonl',dict(id=ident,error=type(e).__name__+': '+str(e),unix=time.time()))
def chat(prompt,text):return '<|im_start|>system\nYou are a careful English science textbook editor.<|im_end|>\n<|im_start|>user\n'+prompt+'\n\n'+text+'<|im_end|>\n<|im_start|>assistant\n'
def seed(s):return int(hashlib.sha256(s.encode()).hexdigest()[:8],16)&0x7fffffff
class Server:
 def __init__(self):
  self.start=time.monotonic();self.cap=F['max_total_EVAL03_GPU_seconds']-F['prior_GPU_seconds'];self.end=self.start+self.cap-10;self.closed=False;self.proc=None;self.port=11603
  assert int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).splitlines()[0])>=3200
  s=socket.socket();s.bind(('127.0.0.1',self.port));s.close();assert sha(Path(F['server']))==F['server_sha256']
  args=[F['server'],'-m',F['model7b'],'--host','127.0.0.1','--port',str(self.port),'-ngl','20','-fa','on','--no-kv-unified','--parallel','2','--no-warmup','-b','512','-ub','128','-t','4','-c','8192','-lv','5']
  env=os.environ.copy();env['PATH']=str(Path(F['server']).parent)+';C:/Users/guoshuang/AppData/Local/Programs/Ollama/lib/ollama/cuda_v12;'+env['PATH'];self.log=(O/'records/SERVER.log').open('xb');self.proc=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
  put(O/'records/SERVER_START.json',dict(pid=self.proc.pid,args=args,unix=time.time(),max_seconds=self.cap,prior_GPU_seconds=F['prior_GPU_seconds']))
  def drain():
   for line in iter(self.proc.stdout.readline,b''):
    self.log.write(line if len(line)<4096 else b'LONG_LINE_SHA256 '+hashlib.sha256(line).hexdigest().encode()+b' bytes='+str(len(line)).encode()+b'\n');self.log.flush()
  self.thread=threading.Thread(target=drain,daemon=True);self.thread.start();self.timer=threading.Timer(self.cap,self.stop);self.timer.daemon=True;self.timer.start()
  try:
   for _ in range(120):
    if self.proc.poll() is not None:raise RuntimeError('SERVER_EXITED')
    try:
     with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health',timeout=1) as r:
      if r.status==200:break
    except Exception:time.sleep(1)
   else:raise RuntimeError('LOAD_TIMEOUT')
  except Exception:self.stop();raise
 def request(self,path,payload,timeout=240):
  remaining=self.end-time.monotonic()
  if remaining<=0:raise TimeoutError('GPU_BUDGET')
  q=urllib.request.Request(f'http://127.0.0.1:{self.port}/'+path,json.dumps(payload).encode(),{'Content-Type':'application/json'})
  with urllib.request.urlopen(q,timeout=max(1,min(timeout,remaining))) as r:return json.loads(r.read())
 def stop(self):
  if self.closed:return
  self.closed=True
  if self.proc and self.proc.poll() is None:
   self.proc.terminate()
   try:self.proc.wait(timeout=5)
   except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
  self.timer.cancel();self.thread.join(timeout=5);self.log.close();put(O/'GPU_USAGE.json',dict(seconds=time.monotonic()-self.start,own_worker_stopped=True))
 def complete(self,ident,text,method,sid,attack,extra=None):
  assert not (O/'records'/(ident+'.request.json')).exists(),'NO_RETRY'
  sd=seed(f'2026111203|{method}|{sid}') if attack=='none' else seed(f'2026111203|{sid}|{method}|concise70|1')
  prompt=F['rewrite_prompt'] if attack=='none' else F['compression_prompt'];payload=dict(prompt=chat(prompt,text),n_predict=1024,temperature=.7,top_p=.9,top_k=40,repeat_penalty=1.,seed=sd,cache_prompt=False,stream=False,return_tokens=True,id_slot=1)
  if extra:payload.update(extra)
  saved={k:v for k,v in payload.items() if k!='logit_bias'};saved['input_sha256']=hashlib.sha256(text.encode()).hexdigest()
  if 'logit_bias' in payload:saved.update(logit_bias_sha256=hashlib.sha256(json.dumps(payload['logit_bias']).encode()).hexdigest(),logit_bias_count=len(payload['logit_bias']))
  put(O/'records'/(ident+'.request.json'),saved);tick=time.monotonic();r=dict(id=ident,source_id=sid,set='T4',method=method,attack=attack,status='FAILED',input_sha256=saved['input_sha256'],seed=sd)
  log('RUN_MANIFEST.jsonl',dict(id=ident,event='ATTEMPT_STARTED',unix=time.time(),slot=1))
  try:
   d=self.request('completion',payload);out=d['content'];(O/'outputs'/(ident+'.txt')).write_bytes(out.encode());public=self.request('tokenize',dict(content=out,add_special=False,parse_special=False))['tokens'];put(O/'records'/(ident+'.tokens.json'),dict(generated=d.get('tokens',[]),public=public,output_sha256=hashlib.sha256(out.encode()).hexdigest()))
   r.update(status='COMPLETED',tokens=d.get('tokens_predicted'),stop_type=d.get('stop_type'),truncated=d.get('truncated'),natural_eos=d.get('stop_type')=='eos',output_sha256=hashlib.sha256(out.encode()).hexdigest())
   if 'logit_bias' in payload:
    echo=d.get('generation_settings',{}).get('logit_bias');r.update(bias_echo_available=echo is not None,bias_echo_matches_request=echo==payload['logit_bias'] if echo is not None else None)
  except Exception as e:r['error']=type(e).__name__+': '+str(e);failure(ident,e)
  r['seconds']=time.monotonic()-tick;put(O/'records'/(ident+'.json'),r);log('RUN_MANIFEST.jsonl',dict(id=ident,event='ATTEMPT_FINISHED',status=r['status'],seconds=r['seconds']));return r

def main():
 assert not (O/'STARTED.json').exists();put(O/'STARTED.json',dict(unix=time.time(),code_sha256=sha(Path(__file__)),freeze_sha256=sha(O/'FREEZE.json')))
 key=(OLD/'frozen_comparison09/restricted/kgw_key.txt').read_text();assert hashlib.sha256(key.encode()).hexdigest()==F['key_sha256'];maskpath=E1/'restricted/UNIGRAM_GREEN.json';assert sha(maskpath)==F['unigram_mask_sha256'];green=read(maskpath);sources=read(O/'SOURCES.json');assert len(sources)==60
 Q=queue.Queue();done=threading.Event();server=None;baseline_rows=[];attack_rows=[]
 def kgw(x):
  ident='T4__'+x['id']+'__KGW';assert not (O/'records'/(ident+'.request.json')).exists();tick=time.monotonic();outids=[];trace=[];status='COMPLETED';error=None;ended=False;prf=Greenlist(key);history=[]
  log('RUN_MANIFEST.jsonl',dict(id=ident,event='ATTEMPT_STARTED',unix=time.time(),slot=0))
  try:
   prompt=chat(F['rewrite_prompt'],x['text']);history=server.request('tokenize',dict(content=prompt,add_special=False,parse_special=True))['tokens'];put(O/'records'/(ident+'.request.json'),dict(prompt=prompt,prompt_ids=history,key_sha256=prf.key_sha256,delta=4,max_new_tokens=1024,temperature=0.,retry=0,input_sha256=x['text_sha256']))
   for step in range(1024):
    gs=prf.indices(history);payload=dict(prompt=history,n_predict=1,temperature=0.,repeat_penalty=1.,cache_prompt=True,stream=False,return_tokens=True,logit_bias=[[int(i),4.] for i in gs],id_slot=0)
    log('KGW_HTTP_LEDGER.jsonl',dict(id=ident,step=step,context4=history[-4:],green_sha256=hashlib.sha256(gs.astype('<u4').tobytes()).hexdigest()))
    d=server.request('completion',payload,90);tt=d.get('tokens',[])
    if not tt and d.get('stop_type')=='eos':ended=True;break
    if len(tt)!=1 or not isinstance(tt[0],int):raise ValueError('ONE_TOKEN_RESPONSE_INVALID')
    token=tt[0];echo=d.get('generation_settings',{}).get('logit_bias');trace.append(dict(step=step,token=token,context4=history[-4:],green=bool(token in gs),bias_echo_available=echo is not None,bias_echo_matches_request=echo==payload['logit_bias'] if echo is not None else None))
    if token in (151643,151645):ended=True;break
    outids.append(token);history.append(token)
    if d.get('stop_type')=='eos':ended=True;break
   else:status='TOKEN_LIMIT'
  except Exception as e:status='FAILED';error=type(e).__name__+': '+str(e);failure(ident,e)
  put(O/'records'/(ident+'.raw_tokens.json'),dict(generated=outids,trace=trace,status=status,error=error))
  if outids:
   try:
    text=server.request('detokenize',dict(tokens=outids))['content'];(O/'outputs'/(ident+'.txt')).write_bytes(text.encode());public=server.request('tokenize',dict(content=text,add_special=False,parse_special=False))['tokens'];put(O/'records'/(ident+'.tokens.json'),dict(generated=outids,public=public,token_history_equal=public==outids,output_sha256=hashlib.sha256(text.encode()).hexdigest()))
   except Exception as e:status='FAILED';error='PUBLIC_DECODE:'+str(e);failure(ident,e)
  r=dict(id=ident,source_id=x['id'],set='T4',method='KGW',attack='none',status=status,error=error,tokens=len(outids),seconds=time.monotonic()-tick,natural_eos=ended,input_sha256=x['text_sha256']);put(O/'records'/(ident+'.json'),r);log('RUN_MANIFEST.jsonl',dict(id=ident,event='ATTEMPT_FINISHED',status=status,seconds=r['seconds']));return r
 def kgw_queue():
  try:
   for x in sources:
    if server.closed or time.monotonic()>=server.end:break
    r=kgw(x);baseline_rows.append(r)
    if r['status'] in ['COMPLETED','TOKEN_LIMIT'] and (O/'outputs'/(r['id']+'.txt')).exists():Q.put(dict(source_id=x['id'],method='KGW',parent=r['id'],path=str(O/'outputs'/(r['id']+'.txt'))))
    else:log('NOT_RUN.jsonl',dict(source_id=x['id'],method='KGW',attack='compress70',reason='FAILED_PARENT'))
    print('KGW',sum(r['method']=='KGW' for r in baseline_rows),r['status'],flush=True)
  finally:done.set()
 def other_queue():
  for x in sources:
   if server.closed or time.monotonic()>=server.end:return
   ident='T4__'+x['id']+'__Unigram';r=server.complete(ident,x['text'],'Unigram',x['id'],'none',dict(logit_bias=[[i,2.] for i in green],temperature=0.));baseline_rows.append(r);print('Unigram',sum(r['method']=='Unigram' for r in baseline_rows),r['status'],flush=True)
  for x in F['CertInsert_parents']:
   if x['status']=='AVAILABLE':Q.put(dict(source_id=x['source_id'],method='CertInsert',parent=x['parent'],path=x['path']))
   else:log('NOT_RUN.jsonl',dict(source_id=x['source_id'],method='CertInsert',attack='compress70',reason='PARENT_UNWATERMARKABLE'))
  for x in sources:
   path=O/'outputs'/('T4__'+x['id']+'__Fingerprint.txt');path.write_bytes(x['text'].encode());Q.put(dict(source_id=x['id'],method='Fingerprint',parent=path.stem,path=str(path)))
  while not done.is_set() or not Q.empty():
   if server.closed or time.monotonic()>=server.end:return
   try:x=Q.get(timeout=1)
   except queue.Empty:continue
   ident=x['parent']+'__compress70__1';r=server.complete(ident,Path(x['path']).read_text(encoding='utf8'),x['method'],x['source_id'],'compress70');attack_rows.append(r);Q.task_done();print('compress70',len(attack_rows),r['status'],flush=True)
 try:
  server=Server()
  from tokenizers import Tokenizer
  v=read(E1/'PUBLIC_TOKENIZER_VALIDATION.json');assert sha(Path(v['path']))==v['sha256'];tok=Tokenizer.from_file(v['path']);text='A value of 2 kg. The formula is F = ma.';engine=server.request('tokenize',dict(content=text,add_special=False,parse_special=False))['tokens'];assert engine==tok.encode(text,add_special_tokens=False).ids
  put(O/'ADMISSION.json',dict(PASS=True,tokenizer_sha256=v['sha256'],engine_public_tokenization_equal=True,no_new_generation=True))
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(kgw_queue);b=pool.submit(other_queue);a.result();b.result()
 except Exception as e:failure('BATCH02_STAGE',e)
 finally:
  if server:server.stop()
  put(O/'GENERATION_RESULT.json',dict(baseline_rows=baseline_rows,attack_rows=attack_rows,planned_baselines=120,attempted_baselines=len(baseline_rows),planned_attacks=180,attempted_attacks=len(attack_rows),no_retry=True,paid_API=0,own_server_stopped=True));put(O/'GENERATION_FINISHED.json',dict(unix=time.time(),baseline_attempted=len(baseline_rows),attack_attempted=len(attack_rows)))
if __name__=='__main__':main()
