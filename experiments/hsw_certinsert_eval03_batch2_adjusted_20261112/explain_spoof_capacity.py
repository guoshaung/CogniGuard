from common_adjusted import *
import collections
rows=[read(p) for p in (O/'P1/scores').glob('*.json')];out={}
for method in ['CertInsert','RC']:
 rr=[r for r in rows if r['method']==method and r['attack']=='spoofing' and r['m']==4];groups={}
 for k in sorted({len(r['insertions']) for r in rr}):
  xx=[r for r in rr if len(r['insertions'])==k];groups[str(k)]=dict(k=sum(r['detected'] for r in xx),n=len(xx),mean_inserted_words=sum(r['inserted_words'] for r in xx)/len(xx))
 out[method]=groups
put(O/'P1/POSTHOC_CAPACITY_BREAKDOWN.json',dict(status='EXPLORATORY_POSTHOC_EXPLANATION_NOT_NEW_TEST',groups_by_actual_insertion_count=out,warning='Methods have different learned phrase lengths and feasible slots; raw spoof-rate difference is not an isolated causal effect of anchor-key protection.'))
print(json.dumps(out))
