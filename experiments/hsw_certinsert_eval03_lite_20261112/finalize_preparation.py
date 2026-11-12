from initialize import *
import time,collections
z=O/'prepared_batch1'
assert (z/'BACKGROUND_SCORES.json').exists(),'PREPARATION_NOT_FINISHED'
rr=[read(p) for p in sorted(z.glob('T4__*.json'))];assert len(rr)==476
put(z/'PLANS.json',[r['plan'] for r in rr if 'plan' in r]);put(z/'CAPACITY.json',[r['capacity'] for r in rr if 'capacity' in r]);put(z/'PREPARATION_FAILURES.json',[r for r in rr if 'error' in r])
for name in ['records','outputs']:(O/name).mkdir(exist_ok=True)
put(z/'COMPLETE.json',dict(n=len(rr),counts=dict(collections.Counter(r.get('capacity',{}).get('status',r.get('status')) for r in rr)),hashes={f:sha(z/f) for f in ['PLANS.json','CAPACITY.json','BACKGROUND_SCORES.json']}))
print('ready',len(rr))
