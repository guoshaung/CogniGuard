"""Persist explicit author judgements, never infer PASS from keyword hits."""
import argparse,json
from bootstrap import R,save,digest
ap=argparse.ArgumentParser();ap.add_argument('batch');ap.add_argument('assessments');args=ap.parse_args()
batch=json.loads((R/'reviews'/(args.batch+'.json')).read_text())['rows']
mapping=json.loads((R/'private'/(args.batch+'_MAPPING.json')).read_text())
assessment=json.loads(__import__('pathlib').Path(args.assessments).read_text(encoding='utf-8'))
assert set(assessment)=={r['review_id'] for r in batch},'All delivered cards must be reviewed, including FAIL/UNKNOWN'
rows=[]
for card in batch:
 a=assessment[card['review_id']]
 for k in ['facts','coverage','task_utility']:
  assert a[k] in {'PASS','FAIL','UNKNOWN'}
 assert a.get('evidence') and all('quote' in e and 'reason' in e for e in a['evidence'])
 overall='FAIL' if 'FAIL' in [a['facts'],a['coverage'],a['task_utility']] else 'UNKNOWN' if 'UNKNOWN' in [a['facts'],a['coverage'],a['task_utility']] else 'PASS'
 if not card['natural_EOS'] and overall=='PASS':overall='UNKNOWN'
 tid=mapping[card['review_id']];assert digest(R/'raw'/tid/'public.txt')==card['public_sha256']
 rows.append({'task_id':tid,'review_id':card['review_id'],'public_sha256':card['public_sha256'],
  **a,'overall':overall,'reviewer':'current assistant author PROVISIONAL, not external gold; labels removed from review export but not claimed strictly independent blind',
  'detection_scores_seen_before_lock':False,'full_output_read':True,'natural_EOS':card['natural_EOS']})
save(R/'reviews'/(args.batch+'_QUALITY_LOCK.json'),{'status':'LOCKED_BEFORE_THESE_PUBLIC_SCORES','rows':rows})
print(json.dumps({'batch':args.batch,'rows':len(rows),'quality':{k:sum(r['overall']==k for r in rows) for k in ['PASS','FAIL','UNKNOWN']}},ensure_ascii=False))
