"""Unchanged public watermarkers; engine and no-oracle extraction adapters only."""
from pathlib import Path
import sys
import numpy as np
import torch
E=Path(__file__).resolve().parent
sys.path.insert(0,str(E/'vendor/mpac'))
sys.path.insert(0,'D:/pycharm/CogniGuard/var/results/hsw_copyright_transfer01_20261106/textseal_audit')
from official_sampler import OfficialNextTokenSampler,load_official,evaluate_public
from mb_watermark_processor import WatermarkLogitsProcessor,WatermarkDetector
V=152064

def config(method,key):
 c,_,_=load_official()
 return c.WatermarkConfig(watermark_type=method,secret_key=key,ngram=2,gamma=.25,delta=2.,
   after_topp=False,repeated_windows='reuse',scoring_method='v2')

def mpac_params(key):
 return dict(vocab=list(range(V)),gamma=.25,delta=2.,seeding_scheme=f'ff-additive_prf-2-False-{key}',
   base=4,message_length=32,code_length=32,use_position_prf=True,use_fixed_position=False,device='cpu')

class Sampler:
 def __init__(self,tokenizer,method,key,message):
  self.method=method;self.proc=None
  self.sample=OfficialNextTokenSampler(tokenizer,config('greenlist' if method=='B2' else 'none',key),.8,.95,V)
  self.sample.generator._seen=[set()]
  if method=='B3':
   self.proc=WatermarkLogitsProcessor(**mpac_params(key),store_spike_ents=False,use_feedback=False)
   assert len(message)==32 and set(message)<={'0','1'}
   self.proc.set_message(message)
 def select(self,raw,history):
  diagnostic={}
  if self.proc is not None:
   scores=torch.from_numpy(raw.copy())[None]
   changed=self.proc(torch.tensor([history],dtype=torch.long),scores).numpy()[0]
   bias=changed-raw
   assert np.isfinite(changed).all()
   diagnostic={'position':int(self.proc.bit_position),'favored_color':int(self.proc.message_char),
    'biased_count':int(np.count_nonzero(bias)),'bias_exact':bool(np.all(np.isclose(bias,0,atol=1e-6)|np.isclose(bias,2,atol=1e-6)))}
   token=self.sample.select(changed,history)
   diagnostic['selected_favored']=bool(bias[token]>0)
  else:
   token=self.sample.select(raw,history)
   if self.method=='B2':
    colors=self.sample.generator.green_scores(torch.tensor([history[-2:]],dtype=torch.long),V)[0]
    diagnostic={'selected_favored':bool(colors[token].item()),'biased_count':int(colors.sum().item()),'official_delta':2.,'before_top_p':True}
  return token,diagnostic

def greenlist_public(text,tokenizer,key):
 return evaluate_public(text,tokenizer,config('greenlist',key))

def mpac_public(text,tokenizer,key):
 """No true source/issue/message/epoch input. Dummy gold used only for unused BER fields.

 Official detect() demands ground-truth position/message for evaluation summaries.
 Invoke unchanged _score_sequence with a fixed all-zero diagnostic string, discard
 every BER/gold-position field; only its independently extracted top1 is used.
 All candidates and all epochs are resolved by external predeclared register.
 """
 d=WatermarkDetector(**mpac_params(key),tokenizer=tokenizer,normalizers=[],ignore_repeated_ngrams=True,z_threshold=4.)
 ids=tokenizer.encode(text,add_special_tokens=False)
 if len(ids)<=2:return {'status':'INSUFFICIENT','T':0,'decoded_message':None}
 raw=d._score_sequence(torch.tensor(ids,dtype=torch.long),message='0'*32,return_z_at_T=False,
   return_bit_match=False,return_green_token_mask=False,return_z_score_max=False)
 msg=raw['pred_message'];bits=format(int(msg,4),'032b')
 return {'status':'SCORABLE','T':int(raw['num_tokens_scored']),'G':int(raw['num_green_tokens']),
   'z':float(raw['z_score']),'p_value':float(raw['p_value']),'decoded_message':bits,'radix_message':msg,
   'confidence_per_position':list(map(float,raw['confidence_per_position'])),
   'gold_message_read':False,'private_generation_trajectory_read':False,'likelihood_guarantee_claimed':False}
