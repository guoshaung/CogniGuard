"""Posthoc mechanism explanation on the existing1000 DEVELOPMENT cases only."""
import engine as e
from evaluate import read
import json,numpy as np
P=e.P
if (P/'component_trace_audit.json').exists():raise RuntimeError('No overwrite')
old=e.att.InformationBottleneck.compress;calls=[];projections=[]
def observe(self,records,weights):
    result=old(self,records,weights);calls.append({'returned':len(result),'candidates':len(records),'max_weight':max(weights,default=0.),'min_privacy_cost':min([x.sensitivity*self.privacy_lambda for x in records],default=0.)});return result
e.att.InformationBottleneck.compress=observe
oldproj=e.orth.OrthogonalDecoder.project_to_task
def observe_p(self,representation,task_embedding):
    v=oldproj(self,representation,task_embedding);projections.append(float(np.linalg.norm(v)));return v
e.orth.OrthogonalDecoder.project_to_task=observe_p
full_equal=0;proxy_selected=0
for t in read(P/'data/dev/tasks.jsonl'):
    profile,task=e.begin(t);v=e.values(profile);items=e.choose('MM-FOPD',profile,task,3);ids,wire,nt,parsed=e.release(items,v,3)
    proxy_selected+=int(any(k in ids for k in ['device_proxy','schedule_proxy','access_rate']))
    # No extra selection needed: paired test outputs already provide intervention results.
result={'scope':'posthoc1000_development_cases_no_new_test_model','n':1000,'bottleneck_nonempty_cases':sum(x['returned']>0 for x in calls),'bottleneck_candidate_count_range':[min(x['candidates'] for x in calls),max(x['candidates'] for x in calls)],'max_attention_weight_observed':max(x['max_weight'] for x in calls),'min_privacy_cost_observed':min(x['min_privacy_cost'] for x in calls),'projection_nonzero_cases':sum(x>1e-10 for x in projections),'proxy_selected_cases':proxy_selected,'production_files_modified':False,'no_parameter_change':True}
(P/'component_trace_audit.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(result)
