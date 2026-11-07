"""Post-hoc ordinary exact-substring ambiguity check, not a new primary rule.

Prompted by observed finite-threshold crop errors. Public matches are computed
without truth; afterwards we describe those errors. No thresholds or old score
files are edited. This cannot be presented as independent confirmation.
"""
import argparse,csv,json
from pathlib import Path
from bootstrap import R,save,digest
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
save(D/'SUBSTRING_DIAGNOSTIC_FREEZE.json',{'status':'POST_HOC_BEFORE_THIS_DIAGNOSTIC','trigger':'finite-threshold crop attribution errors already observed',
 'candidate_set':'all actual registered public versions, no true source/epoch narrowing','match':'literal UTF8 byte substring, case sensitive, no whitespace repair',
 'rule':'0 reject, 1 unique match, >1 ambiguous; no threshold','new_model_or_detector_calls':0,
 'not_primary_or_independent_validation':True,'old_attribution_scores_and_statuses_not_replaced':True})
queries=json.loads((D/'DETECTOR_QUERIES.json').read_text(encoding='utf-8'));gallery=json.loads((D/'GALLERY_PUBLIC.json').read_text(encoding='utf-8'))
refs=[]
for g in gallery:
 p=Path(g['public_path']);assert digest(p)==g['public_sha256'];refs.append((g['issue_id'],p.read_bytes()))
matches=[]
for q in queries:
 p=Path(q['public_path']);assert digest(p)==q['public_sha256'];body=p.read_bytes()
 ids=[issue for issue,text in refs if body and body in text]
 matches.append({'query_id':q['query_id'],'public_sha256':q['public_sha256'],'candidate_matches':ids,
  'status':'REJECT' if not ids else 'UNIQUE_LITERAL_MATCH' if len(ids)==1 else 'AMBIGUOUS'})
save(D/'SUBSTRING_PUBLIC_MATCHES.json',{'query_truth_or_generation_traces_read':False,'rows':matches})
index={r['query_id']:r for r in matches};attrs=list(csv.DictReader((D/'ATTRIBUTION_RESULTS.csv').open(encoding='utf-8-sig')))
errors=[r for r in attrs if r['status']=='WRONG']
case=[]
for row in errors:
 m=index[row['query_id']];case.append({**row,'literal_all_matches':m['candidate_matches'],
  'literal_status':m['status'],'true_issue_among_literal_matches':row['true_issue'] in m['candidate_matches'],
  'literal_ambiguity_could_withhold_wrong_unique_claim':len(m['candidate_matches'])>1})
save(D/'SUBSTRING_POSTSCORE_ERROR_REVIEW.json',{'status':'POST_HOC_DIAGNOSTIC_NOT_VALIDATED_REPAIR','wrong_method_query_rows':len(errors),
 'distinct_wrong_queries':len({r['query_id'] for r in errors}),'rows':case,'no_original_results_modified':True,
 'all_query_substrings_checked_not_only_favorable_errors':len(matches),'not_a_new_watermark_or_fingerprint_algorithm':True})
print(json.dumps({'status':'POSTHOC_SUBSTRING_CHECK_COMPLETE','public_queries':len(matches),'wrong_rows':len(errors),
 'known_literal_ambiguity_among_wrong_rows':sum(x['literal_ambiguity_could_withhold_wrong_unique_claim'] for x in case)}))
