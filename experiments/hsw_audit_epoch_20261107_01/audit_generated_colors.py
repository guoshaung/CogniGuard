"""Trace-vs-public alignment, explicitly AFTER standalone public detection.

This diagnostic uses private history ONLY to audit implementation, never to
substitute attribution scores or select a decoding candidate by its truth.
"""
import json,os,sys
os.environ.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.dont_write_bytecode=True
import torch
from transformers import AutoTokenizer
from bootstrap import R,save
from methods import config,load_official,WatermarkDetector,mpac_params
from secrets_store import read
torch.set_num_threads(2)
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
secret=read(R/'private/RUN_SECRETS.dpapi');tasks=json.loads((R/'TASKS_FROZEN.json').read_text());rows=[]
assert (R/'analysis_round01/EVALUATION_RECEIPT.json').exists()
for t in tasks:
 p=R/'raw'/t['task_id']/'result.json'
 if not p.exists() or t['method']=='C0':continue
 r=json.loads(p.read_text());trace=[json.loads(l) for l in (p.parent/'trace.jsonl').read_text().splitlines()]
 public=tok.encode((p.parent/'public.txt').read_text(encoding='utf-8'),add_special_tokens=False)
 visible=[v for v in r['generated_ids'] if v not in tok.all_special_ids]
 assert public==visible,'Private-position comparison unsupported when B histories differ; never alter public detection'
 mismatch=0
 if t['method']=='B2':
  _,_,module=load_official();d=module.build_detector(tok,config('greenlist',secret['B2_keys'][t['issue_id']]),model=None)
  scores,masks=d.get_scores_by_t([(p.parent/'public.txt').read_text(encoding='utf-8')],scoring_method='v2',seen_windows=set(),return_aux=True)
  chosen=[i+2 for i,v in enumerate(masks[0]) if v]
  for pos,val in zip(chosen,scores[0]):mismatch+=int(bool(val)!=trace[pos]['diagnostic']['selected_favored'])
  row={'task_id':t['task_id'],'method':'B2','T':len(chosen),'G':int(sum(scores[0])),
   'trace_public_color_mismatch':mismatch,'first2_public_tokens_and_EOS_excluded':True}
 else:
  d=WatermarkDetector(**mpac_params(secret['epoch_keys'][t['epoch']]),tokenizer=tok,normalizers=[],ignore_repeated_ngrams=True)
  lookup,freq,posmap,_,_=d._score_ngrams_in_passage_sequential(torch.tensor(public,dtype=torch.long))
  digits=[int(t['message_code'][i:i+2],2) for i in range(0,32,2)];seen=set();trueG=0;positionmismatch=0;checked=0
  for pos in range(2,len(public)):
   gram=tuple(public[pos-2:pos+1]);diag=trace[pos]['diagnostic'];targetpos=posmap[gram]
   positionmismatch+=int(diag['position']!=targetpos)
   favored=bool(lookup[gram][digits[targetpos-1]])
   mismatch+=int(favored!=diag['selected_favored']);checked+=1
   if gram not in seen:trueG+=int(favored);seen.add(gram)
  row={'task_id':t['task_id'],'method':'B3','T':len(freq),'G_for_actual_embedded_code_POSTSCORE_ONLY':trueG,
   'trace_public_color_mismatch':mismatch,'position_PRF_mismatch':positionmismatch,'positions_checked_before_dedup':checked,
   'actual_message_used_for_alignment_not_for_blind_decode':True,'not_replacement_for_public_Top1_score':True}
 rows.append(row)
 assert mismatch==0 and row.get('position_PRF_mismatch',0)==0,'Actual sampled color or position misalignment'
save(R/'GENERATION_PUBLIC_ALIGNMENT.json',{'status':'PASS_POSTSCORE_DIAGNOSTIC','rows':rows,
 'private_history_used_in_this_diagnostic':True,'private_history_used_by_standalone_detector':False,
 'public_scores_replaced':False,'new_model_forward_calls':0})
print(json.dumps({'status':'GENERATED_COLORS_PUBLIC_HISTORY_MATCH','rows':rows}))
