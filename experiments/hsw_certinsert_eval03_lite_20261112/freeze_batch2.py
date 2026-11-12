from initialize import *
import time
B=O/'batch02';B.mkdir(exist_ok=False)
for n in ['records','outputs','restricted']:(B/n).mkdir()
f=read(E1/'EVAL_FREEZE.json');ids=read(O/'materials02/PAIRED_IDS.json');src={x['id']:x for x in read(O/'materials02/T4.json')};assert len(ids)==60 and len(set(ids))==60
old=W/'var/results/hsw-st/english_replication_20261110_01/e1_guarded';key=(old/'frozen_comparison09/restricted/kgw_key.txt').read_bytes();ug=E1/'restricted/UNIGRAM_GREEN.json'
for name,digest in f['model7b_parts'].items():assert sha(Path(f['model7b']).parent/name)==digest
assert sha(Path(f['server']))==f['server_sha256']
records={r['id']:r for r in read(O/'INSERT_T4_all_RESULT.json')['rows']};records.update({r['id']:r for r in read(O/'scoring_recovery01/INSERT_T4_all_RESULT.json')['rows']})
cert=[]
for sid in ids:
 ident='T4__'+sid+'__CertInsert';r=records[ident]
 root=O/'scoring_recovery01' if (O/'scoring_recovery01/records'/(ident+'.json')).exists() else O
 cert.append(dict(source_id=sid,parent=ident,status='AVAILABLE' if r['status']=='PREDICTED_TARGET_REACHED' else 'NOT_RUN_PARENT_UNWATERMARKABLE',path=str(root/'outputs'/(ident+'.txt')),sha256=sha(root/'outputs'/(ident+'.txt'))))
freeze=dict(task='EVAL03-LITE-BATCH02',before_generation=True,paired_ids_sha256=sha(O/'materials02/PAIRED_IDS.json'),source_hashes={sid:src[sid]['text_sha256'] for sid in ids},baseline_methods=['KGW','Unigram'],baseline_tasks=120,compression_methods=['CertInsert','KGW','Fingerprint'],compression_ratio=70,compression_replicates=1,compression_planned=180,cert_available=sum(x['status']=='AVAILABLE' for x in cert),CertInsert_parents=cert,seed=2026111203,seed_rule='uint31(first8hex SHA256(2026111203|method|source_id)) baseline; SHA256(2026111203|source_id|method|concise70|1) compression',KGW_backend='UNCHANGED_STEPWISE_HTTP_NO_MIGRATION',internal_equivalence='NOT_APPLICABLE_NO_BACKEND_CHANGE',key_sha256=hashlib.sha256(key).hexdigest(),unigram_mask_sha256=sha(ug),model7b=f['model7b'],model7b_parts=f['model7b_parts'],server=f['server'],server_sha256=f['server_sha256'],server_config=f['server_config'],generation=f['generation'],KGW=f['KGW'],Unigram=f['Unigram'],rewrite_prompt=f['rewrite_prompt'],compression_prompt=f['attacks']['concise'].format(ratio=70),parallel='single shared model, slot0 KGW, slot1 Unigram followed by pending compression; explicit IDs, no shared histories',max_total_EVAL03_GPU_seconds=172800,prior_GPU_seconds=read(O/'scoring_recovery01/INSERT_T4_all_RESULT.json')['seconds'],max_baseline_retries=0,max_attack_retries=0,per_request_timeout_seconds=240,failed_parents_not_replaced=True)
put(B/'FREEZE.json',freeze);put(B/'PAIRED_IDS.json',ids);put(B/'SOURCES.json',[src[sid] for sid in ids]);put(E/'BATCH02_FREEZE.json',freeze)
put(B/'STATE.json',dict(stage='FROZEN_BEFORE_GENERATION',baseline_attempted=0,attack_attempted=0,paid_API=0))
print('frozen60; baseline120; compression eligible upper bound',120+freeze['cert_available'])
