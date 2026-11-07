"""Export complete newly delivered text without arm/epoch/z labels. No model calls."""
import json,hashlib
from bootstrap import R,save,digest
tasks={x['task_id']:x for x in json.loads((R/'TASKS_FROZEN.json').read_text())}
for prior in (R/'reviews').glob('BATCH_[0-9][0-9][0-9].json'):
 if not (prior.parent/(prior.stem+'_QUALITY_LOCK.json')).exists() and not (prior.parent/(prior.stem+'_SUPERSEDED.json')).exists():
  raise RuntimeError('Close the existing unsubmitted review batch first: '+prior.stem)
done={}
for p in (R/'reviews').glob('*QUALITY_LOCK*.json'):
 for r in json.loads(p.read_text()).get('rows',[]):done[r['task_id']]=r
eligible=[]
for p in sorted((R/'raw').glob('*/result.json')):
 d=json.loads(p.read_text());tid=d['task_id']
 if tid in done:continue
 t=tasks[tid];opaque='REVIEW_'+hashlib.sha256(tid.encode()).hexdigest()[:12]
 eligible.append((opaque,tid,{'review_id':opaque,'source_id':t['source_id'],
  'source':__import__('pathlib').Path(t['source_path']).read_text(encoding='utf-8'),
  'output':(p.parent/'public.txt').read_text(encoding='utf-8'),
  'natural_EOS':d['natural_EOS'],'finish_reason':d['finish_reason'],'public_sha256':d['public_sha256']}))
eligible.sort()
if not eligible:print('NO_NEW_DELIVERED_OUTPUTS');raise SystemExit(0)
index=1
while (R/'reviews'/f'BATCH_{index:03}.json').exists():index+=1
name=f'BATCH_{index:03}'
save(R/'reviews'/f'{name}.json',{'status':'REVIEW_MATERIAL_ONLY_NOT_GOLD','blindness':'method/epoch/score removed in export; operator may remember execution, not independent blind human',
 'rows':[x[2] for x in eligible]})
save(R/'private'/f'{name}_MAPPING.json',{x[0]:x[1] for x in eligible})
print(name,len(eligible))
