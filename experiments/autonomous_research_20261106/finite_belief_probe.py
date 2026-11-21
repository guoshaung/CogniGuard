import json
from collections import defaultdict
WORLD=range(4)
scenarios={'transform':[('A','band')], 'repeat':[('A','band')]*3,
 'refinement':[('A','band'),('A','parity')], 'coalition':[('A','band'),('B','parity')],
 'constant':[('A','constant')], 'denial':[('A','singleton')]}
methods=('literal','provenance','repeated_charge','naive_actual','exact_uniform','no_disclosure')
def query(name,s):
 if name=='band':return 'high' if s>=2 else 'low'
 if name=='parity':return 'even' if s%2==0 else 'odd'
 if name=='constant':return 'fixed'
 if name=='singleton':return 'yes' if s==0 else 'no'
 raise ValueError(name)
def execute(events,method,secret):
 budget=1.;tagged=False;belief=set(WORLD); transcript=[];n=0
 for receiver,query_name in events:
  result=query(query_name,secret);allow=True;cost=0.
  if method=='literal':cost=.5 if str(secret) in result else 0.
  elif method=='provenance':cost=0. if tagged else .5
  elif method=='repeated_charge':cost=.5
  elif method=='naive_actual':allow=sum(query(query_name,s)==result for s in belief)>=2
  elif method=='exact_uniform':
   branches=defaultdict(set)
   for s in belief:branches[query(query_name,s)].add(s)
   allow=all(len(v)>=2 for v in branches.values())
  elif method=='no_disclosure':allow=False
  else:raise ValueError(method)
  if cost>budget+1e-9:allow=False
  if allow:
   budget-=cost;tagged=True;n+=1;obs=result
   if method in ('naive_actual','exact_uniform'):belief={s for s in belief if query(query_name,s)==result}
  else:obs='REFUSED'
  transcript.append((receiver,obs))
 return {'transcript':transcript,'completed':n,'balance':budget}
output={}
for case,events in scenarios.items():
 for method in methods:
  runs={s:execute(events,method,s) for s in WORLD}
  def view(run,coalition):
   return tuple((who,obs) for who,obs in run['transcript'] if coalition or who=='A')
  def statistics(coalition):
   unique=0;posteriors={}
   for s,r in runs.items():
    members=[t for t in WORLD if view(r,coalition)==view(runs[t],coalition)]
    posteriors[str(s)]=members
    unique+=len(members)==1
   return {'unique_worlds':unique,'uniquely_identified_fraction':unique/4,'posteriors':posteriors}
  output[case+' / '+method]={'mean_completed':sum(r['completed'] for r in runs.values())/4,
    'requests':len(events),'coalition':statistics(True),'receiver_A':statistics(False),
    'per_world':{str(s):r for s,r in runs.items()}}
assert all(output[c+' / exact_uniform']['coalition']['unique_worlds']==0 for c in scenarios)
assert output['denial / naive_actual']['coalition']['posteriors']['0']==[0]
assert output['coalition / literal']['coalition']['unique_worlds']==4
assert output['coalition / literal']['receiver_A']['unique_worlds']==0
print(json.dumps({'prior':'uniform over 0..3','output':output},indent=2))
