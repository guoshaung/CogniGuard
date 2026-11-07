"""Join sealed truth only AFTER blind public scores; no new model/detector calls.

The detector stages never import this evaluator or its truth file. All issued
versions remain in the common gallery. Small CAL => infinite primary threshold.
"""
import argparse,csv,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from bootstrap import R,save,digest
from lifecycle import canonical

ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args()
D=R/('analysis_'+a.round)
assert not (D/'ATTRIBUTION_RESULTS.csv').exists()
assert json.loads((D/'FP_COMPUTE.json').read_text())['status']=='COMPLETE'
assert json.loads((D/'WM_COMPUTE.json').read_text())['status']=='COMPLETE'
truth_rows=json.loads((R/'private'/f'{a.round}_QUERY_TRUTH.json').read_text())
truth={x['query_id']:x for x in truth_rows if x['status']=='SCORABLE'}
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text())
gallery=json.loads((D/'GALLERY_PUBLIC.json').read_text());byissue={x['issue_id']:x for x in gallery}
register=json.loads((D/'REGISTER_PUBLIC.json').read_text())
record_byid={x['record']['issue_id']:x['record'] for x in register['rows']}
pub=Ed25519PublicKey.from_public_bytes(bytes.fromhex(register['signature_public_key_hex']))
for x in register['rows']:pub.verify(bytes.fromhex(x['signature_ed25519_hex']),canonical(x['record']))
for g in gallery:assert digest(g['public_path'])==g['public_sha256']
fp=defaultdict(list)
with (D/'FP_SCORES.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):fp[r['query_id']].append(r)
wm=defaultdict(list)
for line in (D/'WM_SCORES.jsonl').read_text().splitlines():
 r=json.loads(line);wm[r['query_id']].append(r)
assert set(fp)==set(wm)==set(truth)=={q['query_id'] for q in queries}
fpmethods=['MINHASH128_CHAR3','LEXICAL_CHAR3_COSINE','MINILM_EN_WINDOWS','HYBRID_EQUAL']
# All methods and windows/epochs are included in each calibration-source maximum.
cal=defaultdict(lambda:defaultdict(list))
for qid,t in truth.items():
 if t['role']!='CAL':continue
 for m in fpmethods:cal[m][t['source_id']].append(max(float(r[m]) for r in fp[qid]))
 for r in wm[qid]:
  s=r['scores']
  if r['method']=='B2_TOOLKIT_GREENLIST':
   if s['status']=='SCORABLE':cal['B2_TOOLKIT_GREENLIST'][t['source_id']].append(-math.log10(max(s['p_value'],1e-300)))
  else:
   for c in s.get('candidates',[]):cal['B3_MPAC32_OFFICIAL_LIST'][t['source_id']].append(-math.log10(max(c['nominal_p_value'],1e-300)))
calmax={m:{src:max(v) for src,v in groups.items()} for m,groups in cal.items()}
assert all(set(v)=={'S03','S04'} for v in calmax.values())
assert math.ceil((2+1)*.99)>2
rows=[];rankrows=[];ownwm=[]
def outcome(selected,t):
 if not selected:return 'REJECT'
 if len(selected)>1:return 'AMBIGUOUS'
 return 'CORRECT' if selected[0]==t['truth_issue_id'] else 'WRONG'
def add(q,t,method,rule,candidates,score=None,threshold=None):
 candidates=sorted(set(candidates));pred=candidates[0] if len(candidates)==1 else None
 byte_matches=[g['issue_id'] for g in gallery if q['public_sha256']==g['public_sha256']]
 true_record=record_byid.get(t.get('truth_issue_id'));pred_record=record_byid.get(pred)
 rows.append({'query_id':q['query_id'],'parent_id':t['parent_id'],'source_id':t['source_id'],'role':t['role'],
  'variant':t['variant'],'issued_method':t.get('issued_method'),'quality':t['quality'],'natural_EOS':t.get('EOS'),
  'method':method,'rule':rule,'status':outcome(candidates,t),'predicted_issue':pred,
  'candidate_issues':json.dumps(candidates),'true_issue':t.get('truth_issue_id'),'true_epoch':t.get('truth_epoch'),
  'wrong_epoch':bool(pred and t.get('truth_epoch') and byissue[pred]['key_epoch']!=t['truth_epoch']),
  'source_only_correct':bool(pred and pred!=t.get('truth_issue_id') and byissue[pred]['source_id']==t['source_id']),
  'predicted_recipient':pred_record['recipient_pseudonym'] if pred_record else None,
  'true_recipient':true_record['recipient_pseudonym'] if true_record else None,
  'predicted_epoch':pred_record['key_epoch'] if pred_record else None,
  'predicted_content_version':pred_record['content_version'] if pred_record else None,
  'wrong_recipient':pred_record['recipient_pseudonym']!=true_record['recipient_pseudonym'] if pred_record and true_record else None,
  'content_version_evaluation':'NOT_TESTED_CONSTANT_V1',
  'score':score,'threshold':threshold,'public_token_N':q['public_tokens'],
  'query_matches_any_registered_body':any(q['public_sha256']==g['public_sha256'] for g in gallery),
  'query_matches_predicted_body':bool(pred and q['public_sha256']==byissue[pred]['public_sha256']),
  'registered_same_byte_issue_count':len(byte_matches),
  'known_byte_identity_conflict':bool(pred and byte_matches and pred not in byte_matches),
  'safe_unique_identity_after_known_copy_collision_guard':bool(pred and len(byte_matches)<=1 and not (byte_matches and pred not in byte_matches)),
  'safe_status_with_known_copy_collision_guard':'AMBIGUOUS' if len(byte_matches)>1 else 'IDENTITY_CONFLICT' if pred and byte_matches and pred not in byte_matches else outcome(candidates,t),
  'association_does_not_sign_modified_query_bytes':True,
  'new_generative_answer':False,'1percent_target_certified':False})
for q in queries:
 qid=q['query_id'];t=truth[qid]
 exact=[r['candidate_id'] for r in fp[qid] if int(r['EXACT_BYTES'])]
 add(q,t,'EXACT_REGISTER','ENGINEERING_EXACT_ALL_MATCHES',exact)
 for m in fpmethods:
  scores=sorted([(float(r[m]),r['candidate_id']) for r in fp[qid]],reverse=True)
  best=scores[0][0];top=[issue for v,issue in scores if abs(v-best)<1e-9]
  second=max((v for v,issue in scores if issue not in top),default=best)
  margin=best-second if len(top)==1 else 0.
  matched=[issue for v,issue in scores if best>max(calmax[m].values()) and best-v<1e-9 and margin>=.03]
  add(q,t,m,'PRIMARY_1PCT_UNCERTIFIED_REJECT',[],best,'INFINITY_N2')
  add(q,t,m,'UNCERTIFIED_CAL_MAX_MARGIN_0.03',matched,best,max(calmax[m].values()))
  rank=None
  if t.get('truth_issue_id'):
   true_score=next(v for v,issue in scores if issue==t['truth_issue_id'])
   rank=1+sum(v>true_score+1e-9 for v,issue in scores)
   tied=sum(abs(v-true_score)<1e-9 for v,issue in scores)
  else:true_score=None;tied=None
  rankrows.append({'query_id':qid,'parent_id':t['parent_id'],'variant':t['variant'],'role':t['role'],
   'method':m,'top1_issues':json.dumps(top),'top1_unique_correct':len(top)==1 and top[0]==t.get('truth_issue_id'),
   'true_rank_lower_bound':rank,'true_score_tie_count':tied,'best_score':best,'margin':margin,
   'raw_ranking_not_accepted_identity':True})
 # Per-key detections: never use true key to narrow the search.
 b2=[];allb3=[];top1b3=[]
 for r in wm[qid]:
  s=r['scores']
  if r['method']=='B2_TOOLKIT_GREENLIST':
   issue=r['candidate_key_id'][4:]
   if s['status']=='SCORABLE':
    b2.append((s['p_value'],issue))
    if t.get('truth_issue_id')==issue:
     T=s['scoring_tokens'];G=s['score_sum']
     ownwm.append({'parent_id':t['parent_id'],'variant':t['variant'],'method':'B2','T':T,'G':G,
       'green_ratio':G/T if T else None,'nominal_z':(G-.25*T)/math.sqrt(.25*.75*T) if T else None,
       'nominal_p':s['p_value'],'true_key_used_only_for_after_score_description':True})
  else:
   epoch=r['candidate_key_id'][5:]
   for j,c in enumerate(s.get('candidates',[])):
    for g in gallery:
     if g['method']=='B3' and g['key_epoch']==epoch and g['message_code']==c['message_code']:
      allb3.append((c['nominal_p_value'],g['issue_id']))
      if j==0:top1b3.append((c['nominal_p_value'],g['issue_id']))
   if t.get('issued_method')=='B3' and epoch==t.get('truth_epoch'):
    target=byissue[t['truth_issue_id']]['message_code'];cands=s.get('candidates',[])
    ownwm.append({'parent_id':t['parent_id'],'variant':t['variant'],'method':'B3','T':s.get('T'),
      'G':cands[0]['G'] if cands else None,'nominal_z':cands[0]['z'] if cands else None,
      'nominal_p':cands[0]['nominal_p_value'] if cands else None,
      'top1_message_correct':s.get('top1')==target,'official_list_contains_true_code':any(c['message_code']==target for c in cands),
      'true_code_used_only_for_after_score_description':True})
 add(q,t,'B2_TOOLKIT_GREENLIST','PRIMARY_1PCT_UNCERTIFIED_REJECT',[])
 add(q,t,'B2_TOOLKIT_GREENLIST','NOMINAL_BONFERRONI_NOT_FPR_CERTIFIED',[i for p,i in b2 if p<.01/(29*13)])
 for name,ls in [('B3_MPAC32_TOP1',top1b3),('B3_MPAC32_OFFICIAL_LIST',allb3)]:
  add(q,t,name,'PRIMARY_1PCT_UNCERTIFIED_REJECT',[])
  add(q,t,name,'RAW_REGISTER_CODE_MATCH_NOT_FPR_CERTIFIED',[i for p,i in ls])
  add(q,t,name,'UNCERTIFIED_CAL_MAX_LIST_FAMILY',[i for p,i in ls if -math.log10(max(p,1e-300))>max(calmax['B3_MPAC32_OFFICIAL_LIST'].values())])

def write_csv(path,data):
 fields=list(dict.fromkeys(k for r in data for k in r))
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
write_csv(D/'ATTRIBUTION_RESULTS.csv',rows);write_csv(D/'RAW_RANKS.csv',rankrows);write_csv(D/'OWN_KEY_DIAGNOSTICS.csv',ownwm)
groups=defaultdict(Counter)
for r in rows:groups[(r['role'],r['variant'],r['method'],r['rule'])][r['status']]+=1
summary=[{'role':k[0],'variant':k[1],'method':k[2],'rule':k[3],'denominator_queries':sum(c.values()),**{s:c[s] for s in ['CORRECT','WRONG','AMBIGUOUS','REJECT']}}
 for k,c in sorted(groups.items())]
write_csv(D/'STATUS_SUMMARY.csv',summary)
save(D/'CALIBRATION_RESULT.json',{'status':'TARGET_1PCT_NOT_CERTIFIED','independent_CAL_chapters':2,
 'independent_unknown_TEST_sources':0,'CAL_source_maxima':calmax,'rank':3,'primary_threshold':'INFINITY',
 'unknown_CAL_texts_are_not_independent_test_FPR':True,'primary_rejection_not_defense_success':True,
 'illustrative_iid_upper95_if_zero_false_accepts_out_of_2':1-.05**.5,
 'illustration_not_an_independent_measured_or_certified_FPR':True,
 'finite_CAL_max_and_nominal_results':'uncertified diagnostics only; NOT TPR@1percentFPR'})
actual_ids={g['issue_id'] for g in gallery if g['method']!='B0'}
results=[json.loads((R/'raw'/tid/'result.json').read_text()) for tid in actual_ids]
quality={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for r in json.loads(p.read_text()).get('rows',[]):quality[r['task_id']]=r['overall']
save(D/'EVALUATION_RECEIPT.json',{'status':'SCORED_SNAPSHOT_COMPLETE_NOT_WHOLE_EXPERIMENT','queries':len(queries),'actual_registered_issues':len(gallery),
 'independent_positive_source_chapters':len({t['source_id'] for t in truth.values() if t['truth_issue_id']}),
 'independent_CAL_chapters':2,'TEST_chapters_generated':len({t['source_id'] for t in truth.values() if t['role']=='TEST' and t.get('truth_issue_id')}),'signed_records_verified':len(register['rows']),
 'knowledge_locked_before_scores':True,'generated_answers':len(results),'natural_EOS':sum(r['natural_EOS'] for r in results),'technical_truncated':sum(not r['natural_EOS'] for r in results),
 'quality_counts':dict(Counter(quality[tid] for tid in actual_ids)),'attribution_rows':len(rows),
 'new_model_or_detector_calls':0,'future_unstarted_slots_not_silently_filled':True,
 'completion_claim':'This receipt closes the named offline scoring snapshot only; generation completion and failed/never-started main slots are reported independently.',
 'unregistered_CAL_rewrites_in_queries':len({t['parent_id'] for t in truth.values() if t['role']=='CAL' and not t['parent_id'].startswith('ORIGINAL_')}),
 'earlier_receipt_flag_correction':'round01/02 retained a hardcoded not_a_completed_S2_or_S3_experiment=true; it did not describe S2 completion. Original receipts remain unchanged.'})
print(json.dumps({'status':'EVALUATED','queries':len(queries),'rows':len(rows),'calibration':'NOT_CERTIFIED'}))
