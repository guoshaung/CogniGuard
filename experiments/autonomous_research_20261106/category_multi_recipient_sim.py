import itertools,json
from pathlib import Path
old=json.loads(Path('experiments/autonomous_research_20261106/graph_summary_accounting_output.json').read_text(encoding='utf-8-sig'))['results']
for a in ('raw_exact','derived_band'):
 assert len(old[a])==2
 assert all(x['selected_ids']==['preference'] and x['selection_cost']==.5 and x['category_received'] and x['session_privacy']['limit']==10 and not x['watermark_enabled'] for x in old[a])
assert all(x['released_exposure']==.5 and x['raw_present_at_receiver'] for x in old['raw_exact'])
assert all(x['released_exposure']==0 and not x['raw_present_at_receiver'] for x in old['derived_band'])
scenarios={
 'repeat_same_state': [('r1',0,'V')]*3,
 'change_state': [('r1',0,'V'),('r1',1,'G'),('r1',2,'W')],
 'three_colluding_recipients': [('r1',0,'V'),('r2',0,'V'),('r3',0,'V')],
}
out={}
for scenario,events in scenarios.items():
 nstates=3 if scenario=='change_state' else 1
 worlds=set(itertools.product('VGW',repeat=nstates))
 for method in ('per_read','per_recipient_state','joint_worlds','deny_all'):
  possible=worlds.copy();seen=set();spent=0;allowed=0;denied=0;steps=[]
  for receiver,state,value in events:
   filtered={w for w in possible if w[state]==value}
   assert filtered
   if method=='per_read': cost=.5
   elif method=='per_recipient_state': cost=0 if (receiver,state) in seen else .5
   elif method=='joint_worlds': cost=.5 if len(filtered)<len(possible) else 0
   else: cost=0
   accepted=method!='deny_all' and spent+cost<=1.0+1e-9
   if accepted:
    spent+=cost;allowed+=1;possible=filtered;seen.add((receiver,state))
   else: denied+=1
   steps.append({'receiver':receiver,'state':state,'allowed':accepted,'cost':cost if accepted else 0,'worlds_remaining':len(possible)})
  out[scenario+' / '+method]={'accepted':allowed,'denied':denied,'completion_fraction':allowed/3,
                              'heuristic_charge':spent,'worlds_remaining':len(possible),'steps':steps}
 for method in ('per_read','per_recipient_state','joint_worlds'):
  k=scenario+' / '+method
  best=min(out[scenario+' / '+m]['denied'] for m in ('per_read','per_recipient_state','joint_worlds'))
  out[k]['extra_denials_vs_best_same_scenario']=out[k]['denied']-best
print(json.dumps({'previous_graph_comparison_verified':True,'simulation':out},indent=2))
