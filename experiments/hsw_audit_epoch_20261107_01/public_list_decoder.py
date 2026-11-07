"""Official MPAC confidence-list extraction, no gold message or positions.

Decode choices are intersected only with the public issued-code registry later.
This adapter does not edit the author's algorithm or generation-time parameters.
"""
import math
import torch
from scipy.stats import norm
from methods import WatermarkDetector,mpac_params
def decode_public(text,tokenizer,key):
 ids=tokenizer.encode(text,add_special_tokens=False)
 if len(ids)<=2:return {'status':'INSUFFICIENT','T':0,'top1':None,'candidates':[]}
 d=WatermarkDetector(**mpac_params(key),tokenizer=tokenizer,normalizers=[],ignore_repeated_ngrams=True)
 lookup,freq,positions,counts,position_sequence=d._score_ngrams_in_passage_sequential(torch.tensor(ids,dtype=torch.long))
 n_by_pos={p:0 for p in range(1,d.converted_msg_length+1)}
 for gram,pos in positions.items():n_by_pos[pos]+=freq[gram]
 confidence=[d._compute_max_multinomial_p_val(max(counts[p]),n_by_pos[p]) for p in range(1,d.converted_msg_length+1)]
 candidates,_,_=d._predict_message(n_by_pos,counts,confidence,num_candidates=16)
 out=[];seen=set();T=len(freq)
 for digits in candidates:
  radix=''.join(map(str,digits));bits=format(int(radix,4),'032b')
  if bits in seen:continue
  seen.add(bits)
  G=sum(int(lookup[gram][digits[positions[gram]-1]]) for gram in freq)
  z=(G-.25*T)/math.sqrt(.25*.75*T) if T else 0.
  out.append({'message_code':bits,'G':G,'z':z,'nominal_p_value':float(norm.sf(z))})
 return {'status':'SCORABLE','T':T,'top1':out[0]['message_code'],'candidates':out,
  'candidate_policy':'all unchanged official confidence list, deduplicated; no random-ablation list',
  'missing_supported_positions':[p for p in n_by_pos if n_by_pos[p]==0],
  'nominal_p_value_not_certified':True,'true_message_or_private_positions_used':False}
