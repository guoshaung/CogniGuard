"""Same generating-cohort comparisons; planned failures never disappear.

Raw detector associations, complete delivery identity, and knowledge joint
success are distinct. CAL, B0 fixtures and crop repeats are not new issuances.
"""
import argparse,csv,json
from collections import defaultdict,Counter
from bootstrap import R,save
ap=argparse.ArgumentParser();ap.add_argument('--round',required=True);a=ap.parse_args();D=R/('analysis_'+a.round)
with (D/'ATTRIBUTION_RESULTS.csv').open(encoding='utf-8-sig') as f:attrs=list(csv.DictReader(f))
full=[r for r in attrs if r['variant']=='FULL' and r['issued_method'] in {'C0','B2','B3'}]
bytask=defaultdict(dict)
for r in full:bytask[r['parent_id']][(r['method'],r['rule'])]=r
rules=sorted({(r['method'],r['rule']) for r in full})
tasks=[t for t in json.loads((R/'TASKS_FROZEN.json').read_text(encoding='utf-8')) if t['issue_id'] is not None]
rows=[]
for t in tasks:
 for method,rule in rules:
  r=bytask.get(t['task_id'],{}).get((method,rule));eos=bool(r and r['natural_EOS']=='True');quality=r['quality'] if r else 'NOT_OBSERVED'
  raw=r['status'] if r else 'NOT_RUN_AT_SNAPSHOT'
  safe=bool(r and r['safe_unique_identity_after_known_copy_collision_guard']=='True')
  rows.append({'task_id':t['task_id'],'source_id':t['source_id'],'source_split':t['source_split'],'stage':t['stage'],
   'generating_arm':t['method'],'association_method':method,'rule':rule,'observed_public_text':r is not None,
   'natural_EOS':eos,'quality':quality,'raw_association_status':raw,
   'safe_association_status':r['safe_status_with_known_copy_collision_guard'] if r else 'NOT_RUN_AT_SNAPSHOT',
   'raw_correct':bool(r and raw=='CORRECT'),
   'raw_complete_correct_identity':bool(eos and raw=='CORRECT'),
   'raw_quality_complete_correct_joint':bool(eos and quality=='PASS' and raw=='CORRECT'),
   'complete_correct_identity':bool(eos and raw=='CORRECT' and safe),
   'quality_complete_correct_identity_joint':bool(eos and quality=='PASS' and raw=='CORRECT' and safe),
   'technical_truncated':bool(r and not eos),'not_actual_external_distribution':True})
def write(path,rows):
 with path.open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write(D/'PER_PLANNED_ISSUANCE.csv',rows)
groups=defaultdict(list)
for r in rows:groups[(r['generating_arm'],r['stage'],r['association_method'],r['rule'])].append(r)
summary=[]
for key,rs in sorted(groups.items()):
 summary.append({'generating_arm':key[0],'stage':key[1],'association_method':key[2],'rule':key[3],
  'planned_issuance_denominator':len(rs),'observed_public_text_denominator':sum(r['observed_public_text'] for r in rs),
  'natural_EOS_denominator':sum(r['natural_EOS'] for r in rs),'quality_PASS_count':sum(r['quality']=='PASS' for r in rs),
  'quality_FAIL_count':sum(r['quality']=='FAIL' for r in rs),'quality_UNKNOWN_count':sum(r['quality']=='UNKNOWN' for r in rs),
  'technical_truncated_count':sum(r['technical_truncated'] for r in rs),'complete_correct_identity_count':sum(r['complete_correct_identity'] for r in rs),
  'raw_complete_correct_identity_count':sum(r['raw_complete_correct_identity'] for r in rs),
  'raw_knowledge_complete_identity_joint_count':sum(r['raw_quality_complete_correct_joint'] for r in rs),
  'knowledge_complete_identity_joint_count':sum(r['quality_complete_correct_identity_joint'] for r in rs),
  'raw_WRONG_count':sum(r['raw_association_status']=='WRONG' for r in rs),'safe_AMBIGUOUS_count':sum(r['safe_association_status']=='AMBIGUOUS' for r in rs),
  'safe_IDENTITY_CONFLICT_count':sum(r['safe_association_status']=='IDENTITY_CONFLICT' for r in rs),
  'raw_REJECT_count':sum(r['raw_association_status']=='REJECT' for r in rs),'not_run_at_snapshot':sum(not r['observed_public_text'] for r in rs),
  'independent_source_chapters_observed':len({r['source_id'] for r in rs if r['observed_public_text']}),
  'FPR_1percent_certified':False})
write(D/'PRIMARY_SUMMARY.csv',summary)
register=json.loads((D/'REGISTER_PUBLIC.json').read_text(encoding='utf-8'))
status=[]
for row in register['rows']:
 rec=row['record'];tid=rec['issue_id'];parent=next(iter(bytask.get(tid,{}).values()),None)
 status.append({'issue_id':tid,'method':rec['method'],'actual_external_delivery':False,
  'record_kind':'SIMULATED_AUTHOR_COPY' if rec['method']=='B0' else 'SIMULATED_ATTEMPT_SNAPSHOT',
  'complete_EOS':parent['natural_EOS']=='True' if parent else None,'quality':parent['quality'] if parent else 'SOURCE_PROVISIONAL_PASS',
  'production_release_ready_not_certified':True,
  'technical_prefix_not_a_successful_complete_delivery':bool(parent and parent['natural_EOS']!='True')})
save(D/'DELIVERY_COMPLETENESS_STATUS.json',{'rows':status,'signature_on_attempt_not_proof_of_actual_external_delivery':True,
 'partial_attempt_retained_in_common_gallery_for_all_methods':True,'partial_snapshot_never_counts_complete_or_joint_success':True})
print(json.dumps({'status':'PRIMARY_COHORTS_SAVED','planned_nonCAL_issuances':len(tasks),'observed_issue_queries':len(bytask),
 'all_methods_share_identical_candidate_gallery':True,'raw_results_not_overwritten':True}))
