"""Post-hoc ordinary registry readiness sensitivity, not primary re-scoring.

The original signed attempt register and every failure stay unchanged. All arms
use the same complete-EOS candidate view. Quality FAILs are NOT filtered out.
No raw score, threshold, calibration maximum, seed or generation is changed.
"""
import argparse,csv,json
from collections import Counter,defaultdict
from bootstrap import R,save
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
gallery=json.loads((D/'GALLERY_PUBLIC.json').read_text(encoding='utf-8'))
excluded=[]
for g in gallery:
 p=R/'raw'/g['issue_id']/'result.json'
 if p.exists() and not json.loads(p.read_text(encoding='utf-8'))['natural_EOS']:excluded.append(g['issue_id'])
allowed={g['issue_id'] for g in gallery}-set(excluded)
save(D/'ELIGIBLE_INDEX_SENSITIVITY_FREEZE.json',{'status':'POST_HOC_ENGINEERING_SENSITIVITY','trigger':'observed crop errors often name an incomplete attempt snapshot',
 'exclude_only_nonEOS_actual_attempt_snapshots':excluded,'quality_FAILs_not_filtered':True,
 'candidate_set_same_for_all_methods':True,'calibration_maxima':'original 116-candidate values retained, never lowered',
 'margin':.03,'primary_1percent_threshold':'INFINITY, unchanged','no_model_or_detector_calls':True,
 'original_signed_attempt_records_and_primary_results_retained':True,'not_independent_validation':True})
save(D/'ELIGIBLE_CANDIDATE_VIEW_PUBLIC.json',{'issue_ids':sorted(allowed),'not_a_new_signature_or_a_reissued_body':True})
fp=defaultdict(list)
with (D/'FP_SCORES.csv').open(encoding='utf-8-sig') as f:
 for r in csv.DictReader(f):
  if r['candidate_id'] in allowed:fp[r['query_id']].append(r)
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text(encoding='utf-8'))
cal=json.loads((D/'CALIBRATION_RESULT.json').read_text(encoding='utf-8'))['CAL_source_maxima']
literal={r['query_id']:r for r in json.loads((D/'SUBSTRING_PUBLIC_MATCHES.json').read_text(encoding='utf-8'))['rows']}
methods=['MINHASH128_CHAR3','LEXICAL_CHAR3_COSINE','MINILM_EN_WINDOWS','HYBRID_EQUAL']
pred=[]
for q in queries:
 qid=q['query_id']
 matches=[x for x in literal[qid]['candidate_matches'] if x in allowed]
 pred.append({'query_id':qid,'method':'EXACT_SUBSTRING_POSTHOC','selected':matches})
 for method in methods:
  scores=sorted([(float(x[method]),x['candidate_id']) for x in fp[qid]],reverse=True)
  best=scores[0][0];top=[i for v,i in scores if abs(v-best)<1e-9]
  second=max((v for v,i in scores if i not in top),default=best);margin=best-second if len(top)==1 else 0
  selected=top if best>max(cal[method].values()) and margin>=.03 else []
  pred.append({'query_id':qid,'method':method,'selected':selected})
save(D/'ELIGIBLE_INDEX_PUBLIC_PREDICTIONS.json',{'query_truth_read':False,'rows':pred})
# Join sealed truth only after the new public matching pass has completed.
truth={x['query_id']:x for x in json.loads((R/'private'/(a.round+'_QUERY_TRUTH.json')).read_text(encoding='utf-8')) if x['status']=='SCORABLE'}
rows=[]
for x in pred:
 t=truth[x['query_id']];ls=x['selected'];true=t.get('truth_issue_id')
 status='REJECT' if not ls else 'AMBIGUOUS' if len(ls)>1 else 'CORRECT' if ls[0]==true else 'WRONG'
 rows.append({**x,'role':t['role'],'parent_id':t['parent_id'],'source_id':t['source_id'],'variant':t['variant'],
  'status':status,'true_issue':true,'query_of_incomplete_unissued_snapshot':true in excluded})
groups=defaultdict(list)
for x in rows:groups[(x['role'],x['method'],x['variant'])].append(x)
summary=[]
for key,rs in sorted(groups.items()):
 observed=[r for r in rs if not r['query_of_incomplete_unissued_snapshot']];c=Counter(x['status'] for x in observed)
 summary.append({'role':key[0],'method':key[1],'variant':key[2],'query_denominator':len(observed),
  'source_chapter_clusters':len({x['source_id'] for x in observed}),'incomplete_queries_separately_excluded_from_issue_accuracy':len(rs)-len(observed),
  **{s:c[s] for s in ['CORRECT','WRONG','AMBIGUOUS','REJECT']},'posthoc_not_independent':True,'FPR_1percent_certified':False})
save(D/'ELIGIBLE_INDEX_POSTSCORE_RESULTS.json',{'rows':rows,'original_primary_results_not_changed':True})
with (D/'ELIGIBLE_INDEX_SENSITIVITY.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
print(json.dumps({'status':'POSTHOC_ELIGIBILITY_SENSITIVITY_COMPLETE','candidates_before':len(gallery),'candidates_after':len(allowed),
 'excluded_nonEOS_snapshots':len(excluded),'new_calls':0}))
