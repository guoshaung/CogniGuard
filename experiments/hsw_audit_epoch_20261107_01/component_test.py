"""Zero language-model calls. Finite synthetic scores are UNIT_FIXTURE only."""
import json,time,hashlib
from pathlib import Path
import numpy as np
import torch
from transformers import AutoTokenizer
from bootstrap import R,save
from methods import Sampler,mpac_public,mpac_params,WatermarkDetector,V
from secrets_store import store,read
torch.set_num_threads(2)
t=time.perf_counter()
tok=AutoTokenizer.from_pretrained('D:/pycharm/CogniGuard/assets/models/qwen2.5-7b-q4km-dequant-f16-hsw-repro02',local_files_only=True)
key=1234567 # PUBLIC UNIT FIXTURE ONLY, never production/runtime watermark key
sampler=Sampler(tok,'B3',key,'01010101'*4)
raw=np.linspace(-3,3,V,dtype=np.float32)
history=[10,20,30,40]
token,diag=sampler.select(raw,history)
assert diag['bias_exact'] and diag['biased_count']==V//4
d=WatermarkDetector(**mpac_params(key),tokenizer=tok,normalizers=[],ignore_repeated_ngrams=True)
ids=tok.encode('This is a public software fixture about pressure and inertia. It is not a real research generation.',add_special_tokens=False)
out=[]
for dummy in ['0'*32,'1'*32]:
 v=d._score_sequence(torch.tensor(ids),message=dummy,return_z_at_T=False,return_bit_match=False,return_z_score_max=False)
 out.append({k:v[k] for k in ['pred_message','num_tokens_scored','num_green_tokens','z_score']})
assert out[0]==out[1], 'No-oracle extraction must not depend on diagnostic dummy'
path=R/'private/DPAPI_FIXTURE.dat';store(path,{'fixture':'public nonsecret unit control'})
assert read(path)=={'fixture':'public nonsecret unit control'}
save(R/'COMPONENT_TEST.json',{'status':'PASS','kind':'UNIT_FIXTURE_NOT_RESEARCH_TEXT','bias':diag,
 'dummy_gold_invariance':True,'DPAPI_roundtrip':True,'model_forward_calls':0,'GPU_calls':0,
 'method':'Official MPAC32bit radix4 CPU h2; exact processor source','wall_seconds':time.perf_counter()-t})
print('OFFICIAL_COMPONENT_AND_NO_ORACLE_EXTRACTION_PASS')
