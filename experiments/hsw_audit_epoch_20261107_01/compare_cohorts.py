"""Same-query cohorts across all views; no new scores or tuned decisions."""
import argparse,csv,json
from collections import defaultdict,Counter
from bootstrap import R,save
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
rows=list(csv.DictReader((D/'ATTRIBUTION_RESULTS.csv').open(encoding='utf-8-sig')))
groups=defaultdict(list)
for r in rows:groups[(r['role'],r['issued_method'],r['variant'],r['method'],r['rule'])].append(r)
result=[]
for key,items in sorted(groups.items()):
 counts=Counter(r['status'] for r in items)
 result.append({'role':key[0],'generating_arm':key[1],'variant':key[2],'association_method':key[3],'rule':key[4],
  'query_denominator':len(items),'parent_denominator':len({r['parent_id'] for r in items}),
  'source_chapter_clusters':len({r['source_id'] for r in items}),
  **{'raw_'+s:counts[s] for s in ['CORRECT','WRONG','AMBIGUOUS','REJECT']},
  'wrong_epoch':sum(r['wrong_epoch']=='True' for r in items),
  'source_correct_but_wrong_issue':sum(r['source_only_correct']=='True' for r in items),
  'derived_safe_unique_correct':sum(r['status']=='CORRECT' and r['safe_unique_identity_after_known_copy_collision_guard']=='True' for r in items),
  'FULL_EOS_quality_correct_joint':sum(r['variant']=='FULL' and r['quality']=='PASS' and r['natural_EOS']=='True' and r['status']=='CORRECT' and r['safe_unique_identity_after_known_copy_collision_guard']=='True' for r in items),
  'fragment_standalone_knowledge_quality':'NOT_EVALUATED_PARENT_GRADE_ONLY' if key[2]!='FULL' else 'SEE_LOCK',
  'global_FPR_1percent_certified':False,'multiple_views_not_independent_sources':True})
with (D/'COHORT_VARIANT_COMPARISON.csv').open('x',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
save(D/'COHORT_COMPARISON_SCOPE.json',{'status':'COMPLETE_DERIVED_ONLY','groups':len(result),
 'raw_query_rows':len(rows),'same_registered_version_index_all_methods':True,'new_model_or_detector_calls':0,
 'safe_identity_guard_timing':'post-generation conservative interpretation; raw outcomes kept, see IDENTITY_GUARD_TIMING_NOTE.json',
 'fragment_views_not_new_independent_sources':True,'no_TEST_threshold_or_candidate_selection':True})
print(json.dumps({'status':'COHORT_COMPARISON_WRITTEN','groups':len(result)}))
