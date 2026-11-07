"""Build retained audit material and opaque queries; truth is separate from detection.

Only reads actual delivered public texts after quality locks. Never loads weights,
calls API, regenerates a failed answer, or silently registers unstarted slots.
"""
import argparse,hashlib,json,os,re,sys
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1';sys.dont_write_bytecode=True
from bootstrap import E,R,save,digest
os.environ['HF_HOME']=str(R/'cache/hf');os.environ['HF_HUB_OFFLINE']='1'
from transformers import AutoTokenizer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from secrets_store import read,store
from lifecycle import Register,canonical

ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args()
D=R/('analysis_'+a.round);D.mkdir()
for sub in ['queries','gallery']: (D/sub).mkdir()
cfg=json.loads((R/'CONFIG_FROZEN.json').read_text());tok=AutoTokenizer.from_pretrained(cfg['tokenizer_path'],local_files_only=True)
all_tasks=json.loads((R/'TASKS_FROZEN.json').read_text());tasks={t['task_id']:t for t in all_tasks}
quality={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for r in json.loads(p.read_text()).get('rows',[]):
  if r['task_id'] in quality:assert quality[r['task_id']]['public_sha256']==r['public_sha256']
  assert r['detection_scores_seen_before_lock'] is False
  quality[r['task_id']]=r
actual=[]
for p in (R/'raw').glob('*/result.json'):
 d=json.loads(p.read_text());t=tasks[d['task_id']];q=quality.get(t['task_id'])
 assert q and digest(p.parent/'public.txt')==q['public_sha256'],'All actual outputs need prior quality lock'
 assert d['A_bytes'] and (p.parent/'public.txt').read_bytes()==tok.decode(d['generated_ids'],skip_special_tokens=True,clean_up_tokenization_spaces=False).encode('utf-8')
 actual.append((t,d,q,p.parent/'public.txt'))
actual.sort(key=lambda x:(0 if x[0].get('epoch')=='E1' else 1,x[0]['task_id']))
private=read(R/'private/RUN_SECRETS.dpapi')
sign_path=R/'private/ISSUER_SIGNING.dpapi'
if not sign_path.exists():
 key=Ed25519PrivateKey.generate()
 store(sign_path,{'private_seed_hex':key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()).hex()})
else:key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(read(sign_path)['private_seed_hex']))
pub=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
reg=Register(D/'register.sqlite3',pub);reg.add_epoch('E1',0,100,900);reg.add_epoch('E2',100,200,1000)
records=[];gallery=[];query_parents=[];pairs={};material={'B2_keys':{},'epoch_keys':private['epoch_keys']}
for t,d,q,path in actual:
 if t['issue_id'] is None:
  query_parents.append({'parent_id':t['task_id'],'path':path,'role':'CAL','source_id':t['source_id'],'issue_id':None,'quality':q['overall'],'EOS':d['natural_EOS']});continue
 issue=t['issue_id'];epoch=t['epoch'];clock=20 if epoch=='E1' else 120
 rec={'issue_id':issue,'source_id':t['source_id'],'issuer_id':'SIMULATED_ISSUER_01','recipient_pseudonym':t['recipient_pseudonym'],
  'content_version':'v1','key_epoch':epoch,'parent_issue_id':t.get('parent_issue_id'),'method':t['method'],'key_id':t['key_id'],
  'public_sha256':digest(path),'issued_at':clock,'message_code':t['message_code']}
 if rec['parent_issue_id'] and not any(r['record']['issue_id']==rec['parent_issue_id'] for r in records):
  raise ValueError('Real reissue must retain actual parent, not fabricate it')
 sig=key.sign(canonical(rec));reg.register(rec,sig);records.append({'record':rec,'signature_ed25519_hex':sig.hex()})
 if t['method']=='B2':material['B2_keys'][issue]=private['B2_keys'][issue]
 gp=D/'gallery'/f'REF_{len(gallery):04}.txt';gp.write_bytes(path.read_bytes())
 gallery.append({'reference_id':gp.stem,'issue_id':issue,'source_id':t['source_id'],'method':t['method'],'key_epoch':epoch,
  'key_id':t['key_id'],'message_code':t['message_code'],'public_path':str(gp),'public_sha256':digest(gp)})
 query_parents.append({'parent_id':issue,'path':path,'role':t['source_split'],'source_id':t['source_id'],'issue_id':issue,
  'quality':q['overall'],'EOS':d['natural_EOS'],'method':t['method'],'epoch':epoch})
 pairs.setdefault(t['pair_id'],t)
for pair,t in sorted(pairs.items()):
 path=Path(t['source_path']);issue='B0_'+pair;epoch=t['epoch'];clock=20 if epoch=='E1' else 120
 rec={'issue_id':issue,'source_id':t['source_id'],'issuer_id':'SIMULATED_ISSUER_01','recipient_pseudonym':t['recipient_pseudonym'],
  'content_version':'v1','key_epoch':epoch,'parent_issue_id':None,'method':'B0','key_id':'NONE','public_sha256':digest(path),'issued_at':clock,'message_code':'NO_MESSAGE_'+pair}
 sig=key.sign(canonical(rec));reg.register(rec,sig);records.append({'record':rec,'signature_ed25519_hex':sig.hex()})
 gp=D/'gallery'/f'REF_{len(gallery):04}.txt';gp.write_bytes(path.read_bytes())
 gallery.append({'reference_id':gp.stem,'issue_id':issue,'source_id':t['source_id'],'method':'B0','key_epoch':epoch,
  'key_id':'NONE','message_code':rec['message_code'],'public_path':str(gp),'public_sha256':digest(gp)})
 query_parents.append({'parent_id':issue,'path':path,'role':t['source_split'],'source_id':t['source_id'],'issue_id':issue,'quality':'PASS_PROVISIONAL_SOURCE','EOS':None,'method':'B0','epoch':epoch})
# CAL originals are independent chapters, never included in registered candidates.
for s in json.loads((R/'inputs/DATA_MANIFEST_FROZEN.json').read_text()):
 if s['split']=='CAL':query_parents.append({'parent_id':'ORIGINAL_'+s['source_id'],'path':Path(s['frozen_path']),
  'role':'CAL','source_id':s['source_id'],'issue_id':None,'quality':'PASS_PROVISIONAL_SOURCE','EOS':None,'method':'UNMARKED_AUTHOR'})
save(D/'REGISTER_PUBLIC.json',{'schema':'retained signed issuance records; simulated clock, not productionPKI',
 'signature_public_key_hex':pub.hex(),'signature_protocol_domain':'HSW-AUDIT-EPOCH-01/issuance/v1','rows':records})
save(D/'GALLERY_PUBLIC.json',gallery)
store(D/'DETECTOR_KEYS.dpapi',material)
queries=[];truth=[];n=0
for p in query_parents:
 b=p['path'].read_bytes();text=b.decode('utf-8',errors='strict');ids=tok.encode(text,add_special_tokens=False)
 variants=[('FULL',text),('CRLF',text.replace('\r\n','\n').replace('\n','\r\n')),
   ('COLLAPSE_WHITESPACE',re.sub(r'\s+',' ',text).strip())]
 for length in [50,100,200]:
  size=length+2
  for pos in ['start','middle','end']:
   kind=f'{pos.upper()}{length}'
   if len(ids)<size:
    truth.append({'parent_id':p['parent_id'],'variant':kind,'status':'NOT_APPLICABLE_TOO_SHORT','requested_effective_T':length,'actual_public_N':len(ids),'source_id':p['source_id'],'role':p['role']});continue
   start=0 if pos=='start' else (len(ids)-size)//2 if pos=='middle' else len(ids)-size
   sel=ids[start:start+size];fragment=tok.decode(sel,skip_special_tokens=True,clean_up_tokenization_spaces=False)
   if '\ufffd' in fragment:
    truth.append({'parent_id':p['parent_id'],'variant':kind,'status':'NOT_APPLICABLE_UTF8_BOUNDARY','source_id':p['source_id'],'role':p['role']});continue
   variants.append((kind,fragment))
 for kind,value in variants:
  n+=1;qid='QUERY_'+hashlib.sha256(f'opaque/{n}/{digest(p["path"])}'.encode()).hexdigest()[:20]
  path=D/'queries'/(qid+'.txt');path.write_bytes(value.encode('utf-8'))
  queries.append({'query_id':qid,'public_path':str(path),'public_sha256':digest(path),'variant':kind,
   'public_tokens':len(tok.encode(value,add_special_tokens=False)),'format_nonwhitespace_unchanged':re.sub(r'\s+','',value)==re.sub(r'\s+','',text) if kind in {'FULL','CRLF','COLLAPSE_WHITESPACE'} else None})
  truth.append({'query_id':qid,'parent_id':p['parent_id'],'variant':kind,'source_id':p['source_id'],'role':p['role'],
   'truth_issue_id':p['issue_id'],'quality':p['quality'],'EOS':p['EOS'],'issued_method':p.get('method'),
   'truth_epoch':p.get('epoch'),'status':'SCORABLE','public_sha256':digest(path)})
save(D/'DETECTOR_QUERIES.json',queries)
save(R/'private'/f'{a.round}_QUERY_TRUTH.json',truth)
before=reg.audit_candidates(150)
for row in records:
 if row['record']['recipient_pseudonym']=='R01' and row['record']['key_epoch']=='E1':reg.permission(row['record']['issue_id'],130,'REVOKED')
after=reg.audit_candidates(150)
assert before==after,'License status must not mutate historical identities'
lifecycle=[]
for p in query_parents:
 if not p['issue_id']:continue
 result=reg.exact_public(p['path'].read_bytes(),150)
 lifecycle.append({'parent_id':p['parent_id'],'expected_epoch':p.get('epoch'),'asof150_exact_association':result,
   'old_body_sha_unchanged':digest(p['path'])==hashlib.sha256(p['path'].read_bytes()).hexdigest()})
save(D/'REAL_TEXT_LIFECYCLE.json',lifecycle)
save(D/'PREPARATION_RECEIPT.json',{'status':'SIGNED_REGISTRY_AND_BLIND_QUERIES_PREPARED','actual_generated_outputs':len(actual),
 'registered_issue_count':len(records),'query_parent_count':len(query_parents),'queries':len(queries),
 'truth_and_seed_not_detector_inputs':True,'quality_locks_complete':True,'CAL_sources_not_registered':True,
 'new_model_calls':0,'signing_private_key_exported':False,'simulated_record_times_not_actual_delivery_TSA':True,
 'detector_keys_contains_sampling_seeds':False})
reg.close()
print(json.dumps({'status':'PREPARED','round':a.round,'actual_outputs':len(actual),'registered_issues':len(records),'queries':len(queries),'secret_values_printed':False}))
