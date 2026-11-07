"""Public queries + complete public delivery index only; no query truth/trace."""
import argparse,csv,hashlib,importlib.util,json,math,os,re,sys,time
from pathlib import Path
from collections import Counter
from bootstrap import R,save,digest
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false',HF_HOME=str(R/'cache/hf'))
sys.dont_write_bytecode=True
import numpy as np
import psutil
import torch
from transformers import AutoTokenizer,AutoModel
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
assert not (D/'FP_SCORES.csv').exists()
policy=json.loads((R/'PUBLIC_EVALUATION_FREEZE.json').read_text())
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text());gallery=json.loads((D/'GALLERY_PUBLIC.json').read_text())
assert psutil.virtual_memory().available>2.5*2**30,'Encoder waits rather than preempt other task'
torch.set_num_threads(2);psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
start=time.perf_counter()
p=Path('D:/pycharm/CogniGuard/var/results/hsw_r37n_necessity_20261103/fingerprints.py')
spec=importlib.util.spec_from_file_location('frozen_r37n_fp',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);fp=module.Fingerprints()
model_path=Path('D:/pycharm/CogniGuard/assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41')
tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True);model=AutoModel.from_pretrained(model_path,local_files_only=True,trust_remote_code=False,dtype=torch.float32).eval().to('cpu')
texts={}
for item in queries+gallery:
 b=Path(item['public_path']).read_bytes();assert hashlib.sha256(b).hexdigest()==item['public_sha256'];texts[item['public_sha256']]=b
features={k:fp.featurize(b)[0] for k,b in texts.items()}
def char_counts(raw):
 s=re.sub(r'\s+','',raw.decode('utf-8'))
 return Counter(s[i:i+3] for i in range(max(1,len(s)-2)))
lex={k:char_counts(b) for k,b in texts.items()}
vec={k:[] for k in texts};windows=[]
for key,b in texts.items():
 ids=tok.encode(b.decode('utf-8'),add_special_tokens=False)
 starts=[0] if len(ids)<=256 else list(range(0,len(ids),192))
 for st in starts:
  part=ids[st:st+256]
  if not part:continue
  inp=tok.prepare_for_model(part,add_special_tokens=True,return_attention_mask=True)
  windows.append({'key':key,'start':st,'end':st+len(part),'full_subtokens':len(ids),'input':inp})
forward=0.;ledger=[]
for i in range(0,len(windows),8):
 batch=windows[i:i+8];x=tok.pad([w['input'] for w in batch],padding=True,return_tensors='pt');assert x['input_ids'].shape[1]<=512
 t=time.perf_counter()
 with torch.inference_mode():
  y=model(**x).last_hidden_state;mask=x['attention_mask'].unsqueeze(-1);z=(y*mask).sum(1)/mask.sum(1).clamp(min=1);z=torch.nn.functional.normalize(z,p=2,dim=1).cpu().numpy()
 elapsed=time.perf_counter()-t;forward+=elapsed
 if forward>300:raise TimeoutError('Frozen encoder forward budget')
 for w,v in zip(batch,z):vec[w['key']].append(v)
 ledger.append({'batch':i//8,'windows':len(batch),'padded_tokens':int(x['input_ids'].shape[1]),'forward_seconds':elapsed})
for k in vec:vec[k]=np.stack(vec[k])
rows=[]
def lexical(x,y):
 den=math.sqrt(sum(v*v for v in x.values())*sum(v*v for v in y.values()))
 return sum(v*y.get(k,0) for k,v in x.items())/den if den else 0.
for q in queries:
 qk=q['public_sha256']
 for ref in gallery:
  rk=ref['public_sha256'];mh=float(np.mean(features[qk]==features[rk]));lc=lexical(lex[qk],lex[rk]);sem=float(np.clip(vec[qk]@vec[rk].T,0,1).max(axis=1).mean())
  rows.append({'query_id':q['query_id'],'candidate_id':ref['issue_id'],'reference_id':ref['reference_id'],
   'MINHASH128_CHAR3':mh,'LEXICAL_CHAR3_COSINE':lc,'MINILM_EN_WINDOWS':sem,'HYBRID_EQUAL':.5*lc+.5*sem,
   'EXACT_BYTES':int(qk==rk),'query_public_sha256':qk,'candidate_public_sha256':rk})
with (D/'FP_SCORES.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save(D/'FP_COMPUTE.json',{'status':'COMPLETE','queries':len(queries),'gallery_instances':len(gallery),'score_rows':len(rows),
 'unique_public_byte_inputs':len(texts),'new_encoder_batches':len(ledger),'embedding_windows':len(windows),'encoder_forward_seconds':forward,
 'stage_wall_seconds':time.perf_counter()-start,'model_path':str(model_path),'model_sha256':digest(model_path/'model.safetensors'),
 'immutable_minhash_source_sha256':digest(p),'query_truth_read':False,'private_generation_trace_or_key_read':False,
 'new_generative_answers':0,'paid_API_calls':0,'GPU_calls':0,'method_language':'en','BGE_zh_not_mislabeled_as_English_model':True,
 'ledger':ledger})
print(json.dumps({'status':'FP_COMPLETE','rows':len(rows),'forward_seconds':forward}))
