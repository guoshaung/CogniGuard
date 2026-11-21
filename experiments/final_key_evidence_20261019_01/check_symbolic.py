"""Posthoc same-dev attacker diagnostic. No new LLM calls or test assets."""
import json,hashlib,subprocess,sys,ast
from pathlib import Path
P=Path(__file__).parent;sys.path.insert(0,str(P));from relation_assets import score_relation
O=P/'symbolic_audit';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def load(n):return json.loads((P/'rag_dev'/n).read_text(encoding='utf8'))
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
worker=P/'symbolic_attacker.py';worker_hash=hashlib.sha256(worker.read_bytes()).hexdigest()
save('protocol.json',{'status':'FROZEN_POSTHOC_SAME_DEV_SYMBOLIC_DIAGNOSTIC','not_a_LLM':True,'why':'LLM produced null despite visible affine coefficients and an explicit power relation; a restricted symbolic algorithm tests whether lack of recovered relation means lack of disclosed information','allowed_grammar':'affine public schema and bound multiplier/offset; explicit resistance*current_squared equation; complete if/then/otherwise','no_hidden_inputs':True,'new_model_calls':0,'new_assets':0,'test_opened':False,'no_restart_of_stopped_test_expansion':True,'worker_sha256':worker_hash})
source=ast.parse(worker.read_text(encoding='utf8'));assert all(node.module in [None] for node in ast.walk(source) if isinstance(node,ast.ImportFrom));assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ['open','eval','exec','__import__'] for node in ast.walk(source))
attacks=load('attacks.json');inputs=[x['public_input'] for x in attacks];save('visible_inputs.json',inputs)
proc=subprocess.run([sys.executable,'-I',str(worker)],input=json.dumps(inputs),text=True,capture_output=True,check=True);outputs=json.loads(proc.stdout);save('actual_attacker_outputs.json',outputs)
gold={a['id']:a for a in load('assets_hidden_gold.json')};rows=[]
for a,out in zip(attacks,outputs):
 score=score_relation(json.dumps({'expr':out['expr']}),gold[a['asset']]);rows.append({'beta':a['beta'],'asset':a['asset'],'kind':a['kind'],'method':a['method'],'symbolic_expression':out['expr'],'evidence':out['evidence'],**score})
save('results.json',rows);assert hashlib.sha256(worker.read_bytes()).hexdigest()==worker_hash
save('completion.json',{'status':'COMPLETED_RESTRICTED_SYMBOLIC_DIAGNOSTIC','real_algorithm_evaluations':len(rows),'real_model_calls':0,'test_evaluations':0,'input_has_source_or_gold':False,'worker_static_audit':'stdlib json/re/sys, no open/eval/exec or gold import','scope':'posthoc developer-authored grammar on same3 dev assets; not general NLI or independent test'})
print(json.dumps([{'method':m,'complete_assets_at_beta1_2':len({x['asset'] for x in rows if x['beta']==1.2 and x['kind']=='identity_split' and x['method']==m and x['complete_relation']})} for m in dict.fromkeys(x['method'] for x in rows)],indent=2))
