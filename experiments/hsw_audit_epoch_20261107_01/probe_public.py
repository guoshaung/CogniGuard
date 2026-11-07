"""All candidate keys/epochs, final-text only; does not use a query's true mapping."""
import os,sys,time,json,hashlib
from bootstrap import R,save,digest
os.environ['HF_HOME']=str(R/'cache/hf');os.environ['HF_HUB_OFFLINE']='1';sys.dont_write_bytecode=True
import torch
from transformers import AutoTokenizer
from methods import greenlist_public,mpac_public
from secrets_store import read
assert (R/'reviews/PROBE_QUALITY_LOCK.json').exists()
q=json.loads((R/'reviews/PROBE_QUALITY_LOCK.json').read_text())['rows']
assert all(not r['detection_scores_seen_before_lock'] for r in q)
secret=read(R/'private/RUN_SECRETS.dpapi');cfg=json.loads((R/'CONFIG_FROZEN.json').read_text())
tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True);torch.set_num_threads(2)
t=time.perf_counter();rows=[];ok=[]
for query in q:
 tid=query['task_id'];p=R/'raw'/tid/'public.txt';assert digest(p)==query['public_sha256'];text=p.read_text(encoding='utf-8')
 # These loops do not receive the true query method, source, issue or epoch as a filter.
 for candidate_id,key in secret['B2_keys'].items():
  d=greenlist_public(text,tok,key)
  rows.append({'query_id':tid,'method':'B2_TOOLKIT_GREENLIST','candidate_key_id':'KEY_'+candidate_id,
    **{k:v for k,v in d.items() if k!='public_token_ids'}})
 for epoch,key in secret['epoch_keys'].items():
  d=mpac_public(text,tok,key);rows.append({'query_id':tid,'method':'B3_MPAC','candidate_key_id':'MPAC_'+epoch,**d})
 result=json.loads((R/'raw'/tid/'result.json').read_text());trace=[json.loads(l) for l in (R/'raw'/tid/'trace.jsonl').read_text().splitlines()]
 # Private trajectory read only AFTER scoring, only for engineering check, not detector inputs.
 text_ok=p.read_bytes()==tok.decode(result['generated_ids'],skip_special_tokens=True,clean_up_tokenization_spaces=False).encode('utf-8')
 ok.append({'task_id':tid,'A_public_bytes':text_ok,'natural_EOS':result['natural_EOS'],
    'raw_finite_all':all(r['raw_logits_finite'] for r in trace),'B_equal':result['B_ids_equal'],
    'generated_tokens':len(result['generated_ids']),'public_tokens':len(tok.encode(text,add_special_tokens=False)),
    'quality':query['overall'],'independent_public_score_rows':len(secret['B2_keys'])+len(secret['epoch_keys'])})
save(R/'analysis/PROBE_ALL_CANDIDATE_SCORES.json',rows)
allowed=[r['task_id'].rsplit('_',1)[1] for r in ok if r['A_public_bytes'] and r['natural_EOS'] and r['raw_finite_all']]
save(R/'ADMISSION_PROBE.json',{'status':'TECHNICAL_PROBE_PASS' if len(allowed)==3 else 'PARTIAL',
 'methods_allowed':allowed,'rows':ok,'quality_lock_sha256':digest(R/'reviews/PROBE_QUALITY_LOCK.json'),
 'knowledge_PASS_methods':[r['task_id'].rsplit('_',1)[1] for r in ok if r['quality']=='PASS'],
 'quality_FAIL_retained_not_overwritten':True,'p_values_do_not_certify_FPR':True,
 'declared_all_keys':len(secret['B2_keys']),'declared_all_epochs':len(secret['epoch_keys']),
 'elapsed_seconds':time.perf_counter()-t,'new_generated_answers':0})
print(json.dumps({'status':'PROBE_TECHNICAL_COMPLETE','methods_allowed':allowed,'score_rows':len(rows),'elapsed_seconds':time.perf_counter()-t}))
