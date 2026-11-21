"""Posthoc formatting audit ONLY. No new assets, model calls, or test opening."""
import json,re,sys,ast,hashlib
from pathlib import Path
P=Path(__file__).parent;sys.path.insert(0,str(P))
from relation_assets import score_relation
O=P/'rag_format_audit';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def get(n):return json.loads((P/'rag_dev'/n).read_text(encoding='utf8'))
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
save('protocol.json',{'status':'POSTHOC_FORMAT_DIAGNOSTIC_NOT_NEW_TEST','why':'original strict parser rejected an explicit if/then/otherwise natural-language rule; diagnose scoring floor without altering original scoring or prompts','parser':'generic if CONDITION, then A, otherwise B -> A if CONDITION else B; input alias to x. Uses only actual attacker answer, never source or gold for conversion','new_model_calls':0,'test_opened':False,'original_all_zero_results_preserved':True,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
assets={x['id']:x for x in get('assets_hidden_gold.json')};rows=[]
for z in get('attacks.json'):
 try:expr=json.loads(re.search(r'\{[^{}]*\}',z['answer'],re.S).group()).get('expr')
 except Exception:expr=None
 corrected=None
 if isinstance(expr,str):
  m=re.fullmatch(r'if (.+?),\s*then (.+?),\s*otherwise (.+)',expr,re.I)
  if m:
   condition,yes,no=m.groups();corrected=f'({yes}) if ({condition}) else ({no})';corrected=re.sub(r'\binput\b','x',corrected)
 score=score_relation(json.dumps({'expr':corrected}),assets[z['asset']]) if corrected else {'parsed':z['parsed'],'complete_relation':z['complete_relation'],'behavioral_accuracy':z['behavioral_accuracy'],'premise_conclusion_accuracy':z['premise_conclusion_accuracy']}
 rows.append({'beta':z['beta'],'asset':z['asset'],'kind':z['kind'],'method':z['method'],'attacker_call':z['attacker_call'],'original_complete_relation':z['complete_relation'],'format_normalized_expression':corrected,'posthoc_complete_relation':score['complete_relation'],'posthoc_behavioral_accuracy':score['behavioral_accuracy'],'posthoc_premise_conclusion_accuracy':score['premise_conclusion_accuracy']})
save('rows.json',rows);save('completion.json',{'status':'COMPLETED_POSTHOC_DIAGNOSTIC','real_model_calls':0,'changed_outputs':sum(x['posthoc_complete_relation']!=x['original_complete_relation'] for x in rows),'unique_actual_attacker_outputs_recovered':len({x['attacker_call'] for x in rows if x['posthoc_complete_relation']}),'not_a_basis_for_test_expansion':True})
print(json.dumps([x for x in rows if x['posthoc_complete_relation']],indent=2))
