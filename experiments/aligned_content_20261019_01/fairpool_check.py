"""Post-run candidate ingress audit; fixed config, no retuning or new blind claim."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import ast,sys,json,hashlib,copy,itertools,time
P=Path(__file__).parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(P)]
import numpy as np
from transformers import AutoTokenizer
from protection.common.schemas import ProfileRecord,StudentProfile,Task
from protection.student_profile.src.fopd.profile_selector import ProfileSelector
from experiments.mmfopd_uci import runner as r
from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
import aligned_selector as alg
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
O=P/'fairpool';O.mkdir(exist_ok=True)
def save(n,z):(O/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if (O/'protocol.json').exists():raise RuntimeError('no overwrite')
save('protocol.json',{'status':'FROZEN_FIXED_CONFIG_INGRESS_CORRECTION','reason':'v2 legacy attention read full profile before output safety gate; enforce identical eligible input records at ingress too','config_lock_sha256':sha(P/'mm_v2/selected_config_lock.json'),'driver_sha256':sha(Path(__file__)),'old_outputs_retained':True,'no_retuning':True,'scope':'all old rows and all authored synthetic rows; post-run engineering recheck, no independent test claim'})
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'),local_files_only=True)
namespace={};src=(ROOT/'experiments/strong_evidence_20261019_01/mm/strict_select_enhanced.py.txt').read_text(encoding='utf8');exec(compile(src,'frozen_strict','exec'),ProfileSelector.select_enhanced.__globals__,namespace);Frozen=type('Frozen',(ProfileSelector,),{'select_enhanced':namespace['select_enhanced']})
cfg=load(P/'mm_v2/selected_config_lock.json')['selected'];tree=ast.parse((P/'run_mm_v2.py').read_text(encoding='utf8'))
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in ['canonical','Counter']:exec(compile(ast.Module(body=[node],type_ignores=[]),'same_counter','exec'))
def fair(method,row,p,t):
 eligible=[x for x in p.profile_records if x.sensitivity<=.7];safe=StudentProfile(p.student_id,{},eligible)
 c=copy.deepcopy(r.CONFIG);c['fopd']['attention']={'top_k_dimensions':len(eligible)};c['fopd']['unit_budget']['allowed']=sorted({x.type for x in eligible});c['fopd']['unit_budget']['distinct_requested_types']=['mastery'] if method=='TaskSlot-commonpool' else []
 # This is the only ingress supplied to the frozen implementation.
 picked=Frozen(c).select(safe,t);tc=Counter(row,eligible);s=set()
 for item in picked:
  k=item.record.record_id
  if len(s)<3 and tc(s|{k})<=32:s.add(k)
 assert len(s)==3 and s<={x.record_id for x in eligible} and tc(s)<=32
 return sorted(s),tc(s)
out=[]
for subject,file,n,maker in [('Math','student-mat.csv',395,r.make_profile),('Portuguese','student-por.csv',649,make_portuguese_profile)]:
 rows=r.parse_csv((ROOT/'.cache/uci-student-performance-v1'/file).read_bytes(),n)
 for method in ['Original-commonpool','TaskSlot-commonpool']:
  old=load(P/'mm_v2'/f'{subject}_{method}_LOCAL.json');changed=0
  for i,row in enumerate(rows):
   s,nt=fair(method,row,*maker(row,i));changed+=s!=old['selection_all'][i];assert nt==old['tokens'][i] if s==old['selection_all'][i] else True
  out.append({'dataset':subject,'method':method,'n_all_rows':n,'fieldsets_changed':changed,'identical_canonical_outputs':changed==0})
data=load(P/'new_families/authored_data.json');oldrows={(x['id'],x['method']):x for x in load(P/'new_families/rows.json')};fields={k:v for k,v in [('prior_test','mastery'),('recent_test','mastery'),('practice_minutes','behavior_aggregate'),('absence_count','behavior_aggregate'),('error_rate','learning_state'),('school_support','educational_context'),('home_support','educational_context'),('hint_usage','educational_context'),('device_access','access_context'),('concept_error','error_pattern'),('format_preference','preference'),('interest_topic','educational_context')]}
for method in ['Original-commonpool','TaskSlot-commonpool']:
 changed=0
 for item in data:
  row=item['values'];records=[ProfileRecord(k,v,'new_lesson',f'{k}={row[k]}',1.,.3,'') for k,v in fields.items()];p=StudentProfile(item['id'],{},records);expr=' + '.join(f'{c}*{k}' for c,k in zip(item['coefficients'],item['necessary']));t=Task(item['id'],item['id'],'Compute the learning index '+expr+' using these observations.','new_lesson','arithmetic',False)
  s,nt=fair(method,row,p,t);old=oldrows[item['id'],method];changed+=s!=old['selected_fields'];assert nt==old['tokens'] if s==old['selected_fields'] else True
 out.append({'dataset':'new_synthetic_families','method':method,'n_all_rows':len(data),'fieldsets_changed':changed,'identical_canonical_outputs':changed==0})
save('comparison.json',out)
save('completion.json',{'status':'COMPLETED','calls':sum(x['n_all_rows'] for x in out),'all_deliveries_identical':all(x['identical_canonical_outputs'] for x in out),'consequence':'Identical train/dev/test releases imply same fixed-fit predictions and attack inputs; do not refit identical data or claim a new test.'})
print(json.dumps(out,indent=2))
