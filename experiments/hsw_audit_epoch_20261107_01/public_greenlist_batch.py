"""Exact public-scoring adaptation to author's existing score_batch interface.

Same public tokenizer IDs, h2, v2 full-gram dedup, PRF and p-value. No method
parameter change, no new detector threshold, no private generation input.
"""
import importlib,math,torch
from methods import load_official
c,_,detector_module=load_official()
core=importlib.import_module('textseal.watermarking.core')

def score_public(text,tokenizer,key):
 cfg=c.WatermarkConfig(watermark_type='greenlist',secret_key=key,ngram=2,gamma=.25,delta=2.,
  after_topp=False,repeated_windows='reuse',scoring_method='v2')
 ids=tokenizer.encode(text,add_special_tokens=False)
 if len(ids)<=2:
  return {'score_sum':0.,'scoring_tokens':0,'p_value':None,'status':'INSUFFICIENT_OR_OFFICIAL_NONFINITE'}
 tokens=torch.tensor(ids,dtype=torch.long);grams=tokens.unfold(0,3,1)
 scores,_=core.score_batch(grams[:,:2],grams[:,2],cfg,seen_windows=set())
 T=len(scores);G=float(sum(scores));d=detector_module.build_detector(tokenizer,cfg,model=None)
 p=float(d.get_pvalue(G,T,eps=1e-200)) if T else None
 return {'score_sum':G,'scoring_tokens':T,'p_value':p,
  'status':'SCORABLE' if p is not None and math.isfinite(p) else 'INSUFFICIENT_OR_OFFICIAL_NONFINITE',
  'scoring_method':'v2','seen_window_scope':'fresh per public text','entropy_filter':False,'detector_model_loaded':False,
  'source_commit':'0b76bc64013081c570b8633d3d3585e3ee9a495a','compute_adapter':'unchanged official score_batch; paired windows and targets'}
