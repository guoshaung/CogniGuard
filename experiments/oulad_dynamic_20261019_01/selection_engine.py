"""Same public metadata/candidate/cost interface for every experimental arm."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
from pathlib import Path
import sys,json,copy,itertools,importlib.util,time
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(P)]
import design as d
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from experiments.mmfopd_uci.runner import CONFIG
from transformers import AutoTokenizer
spec=importlib.util.spec_from_file_location('oulad_frozen_aligned',P/'frozen/aligned_selector.py');alg=importlib.util.module_from_spec(spec);spec.loader.exec_module(alg)
# This domain adapter is public and frozen in design.py before seeing outcomes.
alg.ROLE_ALIASES=d.ROLE_ALIASES;alg.ROLES=tuple(d.ROLE_ALIASES);alg.FIELD_ROLE={key:definition[2] for key,definition in d.FIELDS.items()}
ns={};exec(compile((P/'frozen/strict_select_enhanced.py.txt').read_text(encoding='utf8'),'frozen_StrictSelector','exec'),ProfileSelector.select_enhanced.__globals__,ns);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':ns['select_enhanced']})
tokenizer=None;result_cache={}
def text_value(v):return 'NA' if v is None else (str(int(v)) if float(v).is_integer() else f'{v:.3f}'.rstrip('0').rstrip('.'))
def payload(row,fields):return '\n'.join(f'{k}={text_value(row["values"][k])}' for k in sorted(fields))
class Counter:
 def __init__(self,row):
  global tokenizer
  if tokenizer is None:tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
  self.row=row;keys=list(d.FIELDS);combos=[z for size in [1,2,3] for z in itertools.combinations(keys,size)];self.count={frozenset(z):len(v) for z,v in zip(combos,tokenizer([payload(row,z) for z in combos],add_special_tokens=False)['input_ids'])};self.count[frozenset()]=0;self.all_fit=max(self.count.values())<=64
 def __call__(self,fields):return self.count[frozenset(fields)]
def select(method,row,intent,wording,counter,mi):
 records=[ProfileRecord(k,typ,'oulad',f'{k}={text_value(row["values"][k])}',1.,sensitivity,'') for k,(typ,sensitivity,role,description) in d.FIELDS.items()];eligible=[r for r in records if r.sensitivity<=.7];assert len(eligible)==13;task=Task('oulad',str(row['student']),f'Task purpose {intent}. '+d.question(intent,wording,row['cutoff']),'oulad','development',False);trace={};start=time.perf_counter()
 if method.startswith('Repaired'):
  key=(method,intent,wording,row['cutoff']) if counter.all_fit else None
  if key is not None and key in result_cache:s,trace=result_cache[key]
  else:
   s,trace=alg.choose(eligible,task,counter,d.CFG,method)
   if key is not None:result_cache[key]=(s,trace)
 elif method in ['TrainMI','StageRoleRule','SafeTaskTopK']:
  if method=='TrainMI':order=mi
  elif method=='StageRoleRule':order=d.INTENTS[intent]['required']+[x for x in d.FIELDS if x not in d.INTENTS[intent]['required']]
  else:
   cos,_,_=alg.attention_values(eligible,task,d.CFG['temperature']);order=[eligible[i].record_id for i in sorted(range(len(eligible)),key=lambda i:(-float(cos[i]),eligible[i].record_id))]
  s=set()
  for k in order:
   if len(s)<3 and counter(s|{k})<=64:s.add(k)
 else:
  assert method in ['Original','TaskSlot'];config=copy.deepcopy(CONFIG);config['fopd']['attention']={'top_k_dimensions':len(eligible)};config['fopd']['unit_budget']['allowed']=sorted({r.type for r in eligible});config['fopd']['unit_budget']['distinct_requested_types']=['mastery'] if method=='TaskSlot' else [];s=set()
  for item in Frozen(config).select(StudentProfile(str(row['student']),{},eligible),task):
   k=item.record.record_id
   if len(s)<3 and counter(s|{k})<=64:s.add(k)
 elapsed=1000*(time.perf_counter()-start);assert s<=set(d.FIELDS) and len(s)<=3 and counter(s)<=64
 wire=payload(row,s);assert len(tokenizer.encode(wire,add_special_tokens=False))==counter(s)
 return sorted(s),trace,counter(s),elapsed,wire
def view(row,fields):
 # Public task/module/stage calendar is common context, not an extra private field.
 out={f'public:module={row["module"]}':1.,'public:cutoff':float(row['cutoff']),'public:days_to_due':float(row['target_due']-row['cutoff'])}
 for k in d.FIELDS:
  present=k in fields;out['present:'+k]=float(present)
  if present:
   out['available:'+k]=float(row['values'][k] is not None)
   if row['values'][k] is not None:out['value:'+k]=float(row['values'][k])
 return out
