import itertools, json
from fractions import Fraction as F
answer=F(1,2)*30*F(1,2)**2
assert answer==F(15,4)
values=(F(15,4),F(19,4))
tasks=('A_current_correct','B_changed_to_correct','C_wrong_after_three')
def evaluate(task,p):
 if task==tasks[0]: return p['current']==answer
 if task==tasks[1]: return p['first']!=answer and p['current']==answer
 if task==tasks[2]: return p['current']!=answer and p['attempts']>=3
 raise ValueError(task)
rows=[]
for first,current,attempts in itertools.product(values,values,(2,3)):
 profile={'first':first,'current':current,'attempts':attempts,'marker':'SYNTHETIC_PRIVATE_MARKER'}
 for task in tasks:
  truth=evaluate(task,profile)
  # Exact completion oracle for fixed current-only disclosure; no guesses.
  candidates={evaluate(task,dict(profile,first=f,attempts=n)) for f,n in itertools.product(values,(2,3))}
  static=next(iter(candidates)) if len(candidates)==1 else None
  outputs={'full':truth,'static_current_only':static,'local_task_boolean':truth}
  for method,result in outputs.items():
   rows.append({'task':task,'method':method,'decision':'ABSTAIN' if result is None else result,
                'correct':result is not None and result==truth,'abstained':result is None,
                'marker_transmitted':method=='full'})
summary={}
for task in tasks:
 for method in ('full','static_current_only','local_task_boolean'):
  rr=[r for r in rows if r['task']==task and r['method']==method]
  summary[task+' / '+method]={'cases':len(rr),'correct':sum(r['correct'] for r in rr),
    'abstain':sum(r['abstained'] for r in rr),'incorrect':sum(not r['correct'] and not r['abstained'] for r in rr),
    'marker_sent':sum(r['marker_transmitted'] for r in rr)}
assert len(rows)==72 and all(v['incorrect']==0 for v in summary.values())
print(json.dumps({'answer_joules':str(answer),'summary':summary,'rows':rows},indent=2))
