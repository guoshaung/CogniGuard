import json
from pathlib import Path
p=Path(__file__).with_name('graph_summary_accounting_output.json')
source=json.loads(p.read_text(encoding='utf-8-sig'))['results']
out={}
for arm,rounds in source.items():
 for policy in ('literal_observed','per_read_upper','same_recipient_band_dedup'):
  used=0.;seen=set();delivered=0;refused=0;costs=[]
  for r in rounds:
   keys={(x,'visual_support') for x in r['selected_ids']} if r['category_received'] else set()
   if policy=='literal_observed': cost=r['released_exposure']
   elif policy=='per_read_upper': cost=r['selection_cost']
   else: cost=.5*len(keys-seen)
   if used+cost>1.0+1e-9:
    refused+=1;costs.append(0);continue
   used+=cost;costs.append(cost);seen|=keys
   delivered+=int(r['category_received'])
  out[arm+' / '+policy]={'charged_per_round':costs,'charged_total':used,'category_deliveries':delivered,'refusals':refused,'fixed_budget':1.0}
print(json.dumps(out,indent=2))
