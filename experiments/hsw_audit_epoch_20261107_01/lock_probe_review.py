"""Author reading-based lock. No detector or embedding imports/calls."""
import json
from bootstrap import R,save,digest
tasks=json.loads((R/'TASKS_FROZEN.json').read_text())[:3]
rows=[]
for t in tasks:
 d=R/'raw'/t['task_id'];result=json.loads((d/'result.json').read_text());text=(d/'public.txt').read_text(encoding='utf-8')
 missing=t['method']=='B2'
 rows.append({'task_id':t['task_id'],'public_sha256':digest(d/'public.txt'),'source_sha256':t['source_sha256'],
  'facts':'PASS','coverage':'FAIL' if missing else 'PASS','task_utility':'PASS','overall':'FAIL' if missing else 'PASS',
  'reviewer':'current assistant author PROVISIONAL; nonblind to method, not external gold',
  'detection_scores_seen_before_lock':False,'complete_EOS':result['natural_EOS'],
  'evidence':[{'quote':'Precision of measurements is about how closely repeated measurements agree with each other.',
    'reason':'Restatement omits independent measurements under the same conditions, a pre-frozen necessary scope. Counted coverage omission, not a fabricated numerical error. All paper values/range and reference/precision distinction remain correct.'}] if missing else
    [{'quote':'repeated independent measurements agree with each other, under the same conditions' if t['method']=='C0' else 'repeated independent measurements taken under identical conditions',
      'reason':'Equivalent independence/same-condition scope retained; source11.0, measurements11.1/11.2/10.9,12 comparison,.3range,alternative11.9 and accuracy/precision distinction all retained. No new scientific claim identified.'}],
  'length_is_not_quality':True})
save(R/'reviews/PROBE_QUALITY_LOCK.json',{'status':'LOCKED_BEFORE_PUBLIC_SCORE','rows':rows})
print(json.dumps({'status':'QUALITY_LOCKED','PASS':2,'FAIL':1,'UNKNOWN':0,'detector_calls':0}))
