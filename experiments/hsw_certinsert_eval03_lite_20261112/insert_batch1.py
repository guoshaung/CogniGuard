"""Frozen revision09 scoring, with explicitly labelled single-factor ablations."""
import time,math,random,subprocess
from collections import Counter
from initialize import *
import sys
sys.path.insert(0,str(W/"experiments/hsw_certinsert_eval_20261111_01"))
from common import OLD,R
sys.path.insert(0,str(W/"experiments/hsw_english_replication_20261110_01"))
def spent():return 0
def account(stage,seconds):
 with (O/'GPU_USAGE.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(stage=stage,seconds=seconds))+'\n')
def failure(stage,reason):
 with (O/'FAILURES.md').open('a',encoding='utf8') as f:f.write('\n- '+stage+': '+reason+'\n')
def checkpoint(stage,**kw):
 with (O/'CHECKPOINTS.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(stage=stage,**kw))+'\n')
from e1_long_context_run import GPUScorer,context_pair
from e1_register_core import assemble
from e1_v4r9_run import pb

def main():
 stage=sys.argv[1];dest=O/'prepared_batch1';plans=read(dest/'PLANS.json');caps={x['id']:x for x in read(dest/'CAPACITY.json')};voc={v['text']:v for v in read(dest/'VOCABULARY.json')};freq=read(dest/'FREQUENCIES.json');sd=read(dest/'SCALE.json')['sd'];f=read(R/'FREEZE.json')
 mode=sys.argv[2] if len(sys.argv)>2 else 'all'
 plans=[p for p in plans if mode=='all' or (p['method']=='CertInsert')==(mode=='primary')]
 label='INSERT_'+stage+'_'+mode;assert not (O/'records'/f'{label}_START.json').exists()
 ledger=O/'GPU_USAGE.jsonl';prior_insert=sum(json.loads(l)['seconds'] for l in ledger.read_text().splitlines() if json.loads(l)['stage'].startswith('INSERT_')) if ledger.exists() else 0
 limit=max(0,min(7200-prior_insert,21600-spent()-10))
 put(O/'records'/f'{label}_START.json',dict(unix=time.time(),cap_seconds=limit,code_sha256=sha(__file__),scaling='FROZEN_DEVELOPMENT_SD',sd=sd))
 start=time.monotonic();sc=None;rows=[];cache={};loader_error=None
 # Primary methods before ablations; seeded order inside each arm is fixed without outcomes.
 plans.sort(key=lambda p:(p['method']!='CertInsert',p['set'],hashlib.sha256(('2026111203|insert|'+p['id']).encode()).hexdigest()))
 put(O/'records'/f'{label}_ORDER.json',[p['id'] for p in plans])
 try:
  for p in plans:
   ident=p['id'];cap=caps[ident];chosen=[];tick=time.monotonic();u=dict(tokens=0,sequences=0);error=None;status=cap['status'];natural=set(cap['natural_hits']);ps=[freq[w] for w in p['selected']]
   predicted=lambda:pb(ps,len(natural|{c['word'] for c in chosen}))
   # Fixed-budget ablation still attempts low-capacity sources; no favourable screening.
   admitted=status=='ELIGIBLE' or p['method']=='A3'
   if time.monotonic()-start>=limit:status='NOT_RUN_GPU_BUDGET';admitted=False
   rng=random.Random(int(hashlib.sha256(('2026111203|RC|'+ident).encode()).hexdigest(),16))
   try:
    while admitted:
     remaining=p['budget']-sum(c['word_cost'] for c in chosen)
     if p['method']!='A3' and predicted()<.001:status='PREDICTED_TARGET_REACHED';break
     if remaining<=0:status='FIXED_BUDGET_REACHED';break
     cc=[];used={c['group'] for c in chosen}
     for s in p['candidates']:
      if any(abs(s['word_index']-c['word_index'])<8 or s['sentence']==c['sentence'] for c in chosen):continue
      for word in p['selected']:
       v=voc[word]
       if 1 not in v['layers'] or v['group'] in used or v['word_cost']>remaining:continue
       if v['function']=='advance' and not s.get('then_allowed'):continue
       if v['function']=='begin' and not s.get('explanation_first'):continue
       if v['function']=='forward' and not s.get('paragraph_initial'):continue
       cc.append(dict(s,word=word,word_cost=v['word_cost'],group=v['group'],layer=1,sentence_initial=True,inserted=word[0].upper()+word[1:]+', ',case_adjust=s['offset'] in p['case_eligibility']))
     if not cc:status='UNWATERMARKABLE_GREEDY_EXHAUSTED' if p['method']!='A3' else 'FIXED_BUDGET_CAPACITY_SHORTFALL';break
     if p['method']=='RC':best=rng.choice(cc)
     else:
      if sc is None:
       if loader_error:raise RuntimeError('PRIOR_MODEL_ADMISSION_FAILURE_NO_RETRY:'+loader_error)
       try:
        free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0]);assert free>=3500,'GPU_MEMORY_ADMISSION'
        assert sha(f['qwen_model'])==f['qwen_sha256'],'FROZEN_MODEL_HASH'
        sc=GPUScorer(W/'var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime',Path(f['qwen_model']))
       except Exception as ex:loader_error=type(ex).__name__+': '+str(ex);raise
      queries=[]
      for c in cc:
       a,b,win=context_pair(p,chosen,c);queries.extend([a,b]);c['context_window']=win
      missing=list(dict.fromkeys(t for t in queries if t not in cache))
      for at in range(0,len(missing),4):
       if time.monotonic()-start>=limit or time.monotonic()-tick>=300:raise TimeoutError('FROZEN_SCORING_TIME_LIMIT')
       batch=missing[at:at+4];lens=[len(sc.tokenize(t))+len(sc.prefix_ids) for t in batch]
       if max(lens)>1024:raise ValueError('FROZEN_CONTEXT_LIMIT_NO_TRUNCATION')
       if u['tokens']+sum(lens)>250000:raise TimeoutError('FROZEN_TOKEN_LIMIT')
       rr=sc.score_many(batch)
       with (O/'SCORING_LEDGER.jsonl').open('a',encoding='utf8') as log:
        for t,r in zip(batch,rr):
         assert math.isfinite(r['log_probability']);cache[t]=r['log_probability'];u['tokens']+=r['input_tokens'];u['sequences']+=1;log.write(json.dumps(dict(id=ident,context_sha256=hashlib.sha256(t.encode()).hexdigest(),**r))+'\n')
      for i,c in enumerate(cc):c['delta_logP']=cache[queries[2*i+1]]-cache[queries[2*i]];c['score']=-c['delta_logP']/sd
      best=min(cc,key=lambda c:(c['score'],c['offset'],c['word']))
     chosen.append(best)
   except Exception as e:
    status='RESOURCE_LIMIT' if isinstance(e,TimeoutError) else 'SCORING_FAILURE';error=type(e).__name__+': '+str(e);failure(ident,error)
   text,spans,changes,raw=assemble(p,chosen)
   # Unwatermarkable original is explicitly not a successful watermarked sample.
   (O/'outputs'/f'{ident}.txt').write_bytes(text.encode())
   row=dict(id=ident,set=p['set'],method=p['method'],source_id=p['source_id'],status=status,error=error,budget=p['budget'],inserted_entries=len(chosen),inserted_words=sum(c['word_cost'] for c in chosen),predicted_p=predicted(),assembly_inverse_assertion_passed=True,raw_deletion_inverse=raw,case_changes=changes,spans=spans,chosen=chosen,source_sha256=p['source_sha256'],output_sha256=hashlib.sha256(text.encode()).hexdigest(),seconds=time.monotonic()-tick,usage=u)
   row['selected']=p['selected']
   put(O/'records'/f'{ident}.json',row);rows.append(row)
   if len(rows)%10==0:checkpoint(label,processed=len(rows));print(label,len(rows),round(time.monotonic()-start,1),flush=True)
 finally:
  if sc:sc.close()
  account(label,time.monotonic()-start);put(O/f'{label}_RESULT.json',dict(rows=rows,seconds=time.monotonic()-start,own_model_closed=True));checkpoint(label+'_DONE',processed=len(rows))
if __name__=='__main__':main()
