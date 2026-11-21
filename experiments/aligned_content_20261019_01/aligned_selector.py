"""Experiment-only aligned coordinate projection, attention and budgeted selector.

No grade labels, attribute targets, or record positions enter this encoder.
The projection is an orthogonal coordinate mask, NOT sensitive disentanglement.
"""
import re,itertools,math
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROLE_ALIASES={
 'prior_assessment':['G1','prior_test','earlier assessment','previous grades','prior score'],
 'recent_assessment':['G2','recent_test','latest assessment','previous grades','recent score'],
 'practice_effort':['studytime','practice_minutes','practice effort','study duration'],
 'attendance':['absences','absence_count','attendance','missed sessions'],
 'learning_difficulty':['failures','error_rate','learning difficulty','error frequency'],
 'school_support':['schoolsup','school_support','school help'],
 'family_support':['famsup','home_support','home learning support'],
 'paid_support':['paid','hint_usage','hint frequency'],
 'activity_context':['activities','interest_topic','interest context'],
 'learning_intent':['nursery','higher','learning aspiration'],
 'access':['internet','traveltime','device_access','device access','travel duration'],
 'misconception':['concept_error','concept misconception','misconception'],
 'format':['format_preference','presentation format','format preference'],
 'background':['school','sex','age','address','reason','freetime','goout','background context']}
ROLES=tuple(ROLE_ALIASES)
FIELD_ROLE={name:role for role,names in ROLE_ALIASES.items() for name in names if ' ' not in name}
def mention(alias,text):return re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text,re.I) is not None
def role(record):return FIELD_ROLE.get(record.record_id,'background')
def embedding(record):
 z=np.zeros(len(ROLES));z[ROLES.index(role(record))]=1.;return z
def task_mask(task):return np.array([float(any(mention(a,task.question) for a in ROLE_ALIASES[r])) for r in ROLES])
def metadata(record):return ' '.join([record.record_id,record.type,record.knowledge,*ROLE_ALIASES[role(record)]])
def attention_values(records,task,temperature):
 texts=[metadata(r) for r in records]+[task.text()];v=TfidfVectorizer(token_pattern=r'(?u)\b\w+\b').fit_transform(texts);q=v[-1];cos=np.asarray((v[:-1]@q.T).todense()).ravel();w=np.exp((cos-cos.max())/temperature);w=w/w.sum()
 return cos,w,w/w.max()

def choose(records,task,token_count,config,variant='Repaired-Full'):
 # Candidates were gated by the common adapter before this function.
 mask=task_mask(task);projected=np.stack([embedding(r)*mask for r in records]);proj=np.linalg.norm(projected,axis=1);cos,w,unit=attention_values(records,task,config['temperature'])
 use_proj=variant!='Repaired-no-projection';use_att=variant!='Repaired-no-attention';use_bn=variant!='Repaired-no-bottleneck';use_slot=variant!='Repaired-no-taskslot'
 utility=config['projection_weight']*(proj if use_proj else 0.)+(1-config['projection_weight'])*(unit if use_att else np.ones(len(records)))
 privacy=np.array([r.sensitivity for r in records])*config['privacy_lambda'];net=utility-privacy
 slot=np.array([config['slot_bonus'] if use_slot and r.type=='mastery' and mention(r.record_id,task.question) else 0. for r in records]);score=net+slot
 ordered=sorted(range(len(records)),key=lambda i:(-float(score[i]),records[i].record_id))
 if use_bn:
  best=None;bestids=[]
  # Prefer max feasible field count, then utility minus duplicated-role penalty.
  # This is budgeted subset selection, not an information-theoretic bottleneck.
  for size in range(min(3,len(records)),0,-1):
   for ids in itertools.combinations(range(len(records)),size):
    if token_count([records[i].record_id for i in ids])>config['token_cap']:continue
    duplicate=sum(role(records[i])==role(records[j]) for i,j in itertools.combinations(ids,2));value=sum(float(score[i]) for i in ids)-config['redundancy_penalty']*duplicate
    key=(value,tuple(-ordered.index(i) for i in sorted(ids,key=lambda x:ordered.index(x))))
    if best is None or key>best:best=key;bestids=list(ids)
   if best is not None:break
  chosen=bestids
 else:
  chosen=[]
  for i in ordered:
   if len(chosen)==3:break
   if token_count([records[j].record_id for j in chosen+[i]])<=config['token_cap']:chosen.append(i)
 trace={'projection_nonzero':bool(np.any(proj>1e-12)) if use_proj else False,'projection_values':proj.tolist() if use_proj else [0.]*len(records),'attention_probabilities':w.tolist() if use_att else None,'attention_unit_scale':unit.tolist() if use_att else None,'utility_before_cost':np.broadcast_to(utility,len(records)).tolist(),'privacy_cost':privacy.tolist(),'net_positive_count':int(np.sum(net>0)),'rank':[records[i].record_id for i in ordered],'pre_slot_rank':[records[i].record_id for i in sorted(range(len(records)),key=lambda i:(-float(net[i]),records[i].record_id))],'final_fields':sorted(records[i].record_id for i in chosen),'task_mask':mask.tolist(),'coordinate_names':ROLES}
 return set(trace['final_fields']),trace

DEFAULT={'projection_weight':.5,'temperature':.5,'privacy_lambda':.25,'slot_bonus':.08,'redundancy_penalty':.15,'token_cap':32}
