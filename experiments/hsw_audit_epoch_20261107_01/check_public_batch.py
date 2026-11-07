"""All cached round01 Greenlist controls; no test-selected score changes."""
import json,os,sys,time,hashlib
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');sys.dont_write_bytecode=True
import torch
from transformers import AutoTokenizer
from bootstrap import E,R,save,digest
from secrets_store import read
from public_greenlist_batch import score_public
torch.set_num_threads(2)
save(R/'PUBLIC_SCORING_OPTIMIZATION_FREEZE.json',{'status':'BEFORE_VECTOR_REGRESSION_AND_ALL_TEST_SCORES','method':'official unchanged TextSeal core.score_batch',
 'meaning':'computational adaptation only; same canonical public IDs, h2/v2/key, official PRF and pvalue; no generation change',
 'regression':'every unique cached round01 public-byte/key pair, exact T/G/pvalue; fail blocks use, no threshold tuning',
 'new_model_calls':0,'code_sha256':digest(E/'public_greenlist_batch.py'),'previous_scores_preserved':True,
 'future_WM_budget':'cumulative 1800 wall seconds for detector scoring; old main92.803446 + null111.387571 + conservative120s prior fixtures/alignment reserved; reuse exact scores only under unchanged method/key/tokenizer identity'})
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
D=R/'analysis_round01';keys=read(D/'DETECTOR_KEYS.dpapi')['B2_keys']
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text());bypub={q['public_sha256']:q for q in queries}
cached={}
for line in (D/'WM_SCORES.jsonl').read_text().splitlines():
 r=json.loads(line)
 if r['method']=='B2_TOOLKIT_GREENLIST':cached[(r['public_sha256'],r['candidate_key_id'])]=r['scores']
start=time.perf_counter();mismatch=[]
for (sha,name),old in cached.items():
 text=open(bypub[sha]['public_path'],encoding='utf-8',newline='').read();assert hashlib.sha256(text.encode()).hexdigest()==sha
 new=score_public(text,tok,keys[name[4:]])
 if any(new[k]!=old[k] for k in ['score_sum','scoring_tokens','p_value','status']):mismatch.append({'public_sha256':sha,'key_id':name})
save(R/'PUBLIC_BATCH_REGRESSION.json',{'status':'PASS' if not mismatch else 'FAIL','comparisons':len(cached),'mismatches':mismatch,
 'wall_seconds':time.perf_counter()-start,'model_forward_calls':0,'new_answer_generation':0,'private_traces_read':False,
 'TEST_scores_read':False,'official_code_modified':False,'adapter_sha256':digest(E/'public_greenlist_batch.py')})
assert not mismatch,'Official batch interface did not preserve cached scores'
print(json.dumps({'status':'OFFICIAL_BATCH_PUBLIC_SCORE_EXACT','comparisons':len(cached),'seconds':time.perf_counter()-start}))
