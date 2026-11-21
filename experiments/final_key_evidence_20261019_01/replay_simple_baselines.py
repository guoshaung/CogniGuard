"""Same-candidate baseline purity correction. Token-only common budget, no risk cap."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
from pathlib import Path
import sys,json,re,time,collections,hashlib
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(P))
import numpy as np
import torch
from transformers import AutoTokenizer,AutoModel
from relation_assets import score_relation
from experiments.c2rag_v3.core import disclosure_measurement
from experiments.c2rag_v3.evidence_release import measured_cost
O=P/'simple_baseline_controls';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def load(n):return json.loads((P/'rag_dev'/n).read_text(encoding='utf8'))
if (O/'protocol.json').exists():raise RuntimeError('refuse overwrite')
save('protocol.json',{'status':'POSTHOC_BASELINE_PURITY_CORRECTION_SAME_DEV','why':'primary driver applied weighted disclosure cost ceiling even to Raw/Fixed/Ngram/Semantic. Preserve it as common-risk-control, and execute requested pure Token-only baseline variants.','token_B':72,'per_turn_tokens':24,'per_identity_tokens':'72/active identities','additive_risk':'measured only, NOT gated for these four baselines','new_model_calls':0,'semantic_encoder':'actual same MiniLM forward, threshold .85','attacker':'reuse actual prior model answer only if visible query/reply input exactly identical; otherwise BLOCKED by no further LLM expansion','frozen_decision_stays_STOP':True,'no_new_assets':True,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
M=ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760';E=ROOT/'assets/models/hf_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
tok=AutoTokenizer.from_pretrained(str(M),local_files_only=True);etok=AutoTokenizer.from_pretrained(str(E),local_files_only=True);torch.set_num_threads(4);enc=AutoModel.from_pretrained(str(E),local_files_only=True).to('cuda').eval();encache={};enc_cost=[]
def vec(s):
 if s in encache:return encache[s]
 start=time.perf_counter();inp=etok(s,return_tensors='pt',truncation=True,max_length=384).to('cuda')
 with torch.inference_mode():h=enc(**inp).last_hidden_state;m=inp.attention_mask.unsqueeze(-1);v=torch.nn.functional.normalize((h*m).sum(1)/m.sum(1),dim=-1)
 torch.cuda.synchronize();encache[s]=v[0].cpu().numpy();enc_cost.append({'seconds':time.perf_counter()-start,'tokens':inp.input_ids.numel()});return encache[s]
def nt(s):return len(tok.encode(s,add_special_tokens=False))
def norm(s):return ' '.join(re.findall(r'[a-z0-9]+',s.lower()))
def quality(d,gold):
 if norm(d)==norm(gold):return 1.
 ns=re.findall(r'(?<!\w)-?\d+(?:\.\d+)?',d)
 try:return float(len(ns)==1 and float(ns[0])==float(gold))
 except ValueError:return 0.
def f1(a,b):
 x=norm(a).split();y=norm(b).split();n=sum((collections.Counter(x)&collections.Counter(y)).values());return 2*n/(len(x)+len(y)) if len(x)+len(y) else 0.
from symbolic_attacker import attack as symbolic_attack
pools={(x['asset'],x['query']):x for x in load('candidate_pool.json')};old=load('attacks.json');available={json.dumps(x['public_input'],sort_keys=True):x for x in old};traces=[];results=[]
for a in load('assets_hidden_gold.json'):
 for kind,questions,agents in [('normal',a['normal'],[0]*2)]+[(k,[{'query':f['query']} for f in a['facts']],v) for k,v in a['plans'].items()]:
  for method in ['Raw-RAG-budgeted','Fixed-Truncation','Ngram-Gate','Semantic-Gate']:
   used={i:0 for i in agents};risk=0.;visible=[];normal=[];delivered=[];fallbacks=0
   for turn,(q,agent) in enumerate(zip(questions,agents)):
    if kind=='normal':used={0:0};risk=0.
    pool=pools[(a['id'],q['query'])];d='';reason='no_candidate_fits';cid=None;ctype='refusal'
    for idx,candidate in enumerate(pool['candidates']):
     if method=='Fixed-Truncation':candidate=tok.decode(tok.encode(candidate,add_special_tokens=False)[:8])
     measure=disclosure_measurement(candidate,a['source'],(),5)
     if nt(candidate)>24 or used[agent]+nt(candidate)>72/len(used) or sum(used.values())+nt(candidate)>72:reason='token_budget';continue
     if method=='Ngram-Gate' and measure['ngram_coverage']>.10:reason='ngram_gate';continue
     if method=='Semantic-Gate' and float(vec(candidate)@vec(a['source']))>.85:reason='semantic_gate';continue
     d=candidate;reason='released';cid=pool['candidate_ids'][idx];ctype='primary' if idx==0 else 'substantive_reminder';fallbacks+=int(idx==1);break
    used[agent]+=nt(d);risk+=measured_cost(disclosure_measurement(d,a['source'],(),5));visible.append({'query':q['query'],'reply':d});delivered.append(d)
    traces.append({'asset':a['id'],'kind':kind,'method':method,'turn':turn,'agent':agent,'delivered':d,'actual_tokens':nt(d),'coalition_tokens':sum(used.values()),'measured_risk_NOT_capped':risk,'reason':reason,'candidate_call':cid,'content_type':ctype})
    if kind=='normal':normal.append({'correct':quality(d,q['answer']),'F1':f1(d,q['answer'])})
   row={'asset':a['id'],'kind':kind,'method':method,'tokens':sum(nt(d) for d in delivered),'refusal_rate':sum(not d for d in delivered)/len(delivered),'fallback_rate':fallbacks/len(delivered),'risk_measured_NOT_capped':sum(measured_cost(disclosure_measurement(d,a['source'],(),5)) for d in delivered)}
   if kind=='normal':row.update({'normal_correct':float(np.mean([x['correct'] for x in normal])),'normal_F1':float(np.mean([x['F1'] for x in normal]))})
   else:
    public={'known_task_schema':a['attacker_public_schema'],'observed_query_reply_pairs':visible};prior=available.get(json.dumps(public,sort_keys=True));s=symbolic_attack(public);symbolic=score_relation(json.dumps({'expr':s['expr']}),a);row.update({'public_input':public,'prior_actual_attacker_call':prior['attacker_call'] if prior else None,'primary_LLM_relation_ASR':int(prior['complete_relation']) if prior else None,'attacker_reuse_validated_exact_input':prior is not None,'symbolic_relation_ASR':int(symbolic['complete_relation']),'symbolic_expr':s['expr']})
   results.append(row)
save('traces.json',traces);save('results.json',results);save('encoder_cost.json',enc_cost)
oldtr=load('traces.json');comparisons=[]
for x in traces:
 oldrow=next(z for z in oldtr if z['beta']==1.2 and z['asset']==x['asset'] and z['kind']==x['kind'] and z['method']==x['method'] and z['turn']==x['turn']);comparisons.append(oldrow['delivered']==x['delivered'])
save('completion.json',{'status':'COMPLETED_SAME_DEV_BASELINE_PURITY_REPLAY','real_new_LLM_calls':0,'new_assets':0,'semantic_encoder_forwards':len(enc_cost),'encoder_seconds':sum(x['seconds'] for x in enc_cost),'exact_same_deliveries_as_prior_beta1_2':all(comparisons),'reused_real_attacker_outputs':sum(x.get('attacker_reuse_validated_exact_input',False) for x in results),'unavailable_attacker_outputs_BLOCKED':sum(x.get('attacker_reuse_validated_exact_input') is False for x in results),'old_results_unchanged':True})
print(json.dumps(load('completion.json') if False else {'status':'done','exact_same_deliveries_as_prior_beta1_2':all(comparisons),'new_LLM_calls':0}))
