"""Accounting, source preservation, and adversarial oracle checks."""
from pathlib import Path
import json,hashlib,sys,collections
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(P))
from relation_assets import dev_assets,score_relation,parse_expr
def load(p):return json.loads((P/p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name,v):checks.append({'name':name,'pass':bool(v)});assert v,name
tr=load('rag_dev/traces.json');rows=load('rag_dev/results.json');mm=load('mm/corrected_stage_summary.json');privacy=load('mm/observable_privacy_audit.json')
check('every actual release obeys coalition token72 and additive risk beta',all(x['coalition_tokens']<=72 and x['coalition_risk']<=x['beta']+1e-8 for x in tr))
for method in ['FactRelease-Independent','FactRelease-Shared-staticmatched']:
 for x in tr:
  if x['method']!=method:continue
  active=1 if x['kind']!='identity_split' else 2 if x['asset']!='dev-branch' else 3
  checkname='per-identity accounting'
  assert x['identity_risk']<=x['beta']/active+1e-8
check('Independent/staticmatched every local quota obeyed',True)
def mismatch(a,b):
 v={(x['beta'],x['asset'],x['kind'],x['turn']):x for x in tr if x['method']==b};return sum(x['delivered']!=v[(x['beta'],x['asset'],x['kind'],x['turn'])]['delivered'] for x in tr if x['method']==a)
check('Independent and Shared-staticmatched every delivery identical',mismatch('FactRelease-Independent','FactRelease-Shared-staticmatched')==0)
check('Shared and no-history every delivery identical with common counter',mismatch('FactRelease-Shared','FactRelease-no-history')==0)
check('Full/no-semantic actual outputs identical in this dev batch',mismatch('Full-C2RAG','C2-no-semantic')==0)
check('test not opened after development STOP',load('rag_dev/decision.json')['decision']=='PIVOT' and not (P/'rag_test').exists())
check('all primary model reconstructions are correctly reported at floor',all(not x['complete_relation'] for x in rows if x['kind']!='normal'))
for a in dev_assets():
 check(a['id']+' gold executable expression succeeds',score_relation(json.dumps({'expr':a['hidden_relation']}),a)['complete_relation'])
 check(a['id']+' numeric extraction without relation fails',not score_relation('3 4 5 7',a)['complete_relation'])
 check(a['id']+' incorrect constant expression fails',not score_relation('{"expr":"0"}',a)['complete_relation'])
check('incorrect conditional boundary rejected',not score_relation('{"expr":"x+5 if x<5 else 2*x"}',dev_assets()[2])['complete_relation'])
check('equivalent branch expression passes full predicate/conclusion checks',score_relation('{"expr":"5+x if 4>x else x*2"}',dev_assets()[2])['complete_relation'])
check('unsafe expression rejected without execution',parse_expr('{"expr":"__import__(\"os\").system(\"echo unsafe\")"}')[1] is None)
check('MM exact original frozen field replay',load('mm/completion.json')['exact_released_field_replay'])
check('MM projection and attention do not change real outbound bytes',all(x['canonical_external_release_identical_all_rows'] for x in privacy if x['method'] in ['Strict-no-projection','Strict-no-attention']))
check('MM source unchanged since instrumentation',all(sha(ROOT/k)==v for k,v in load('mm/protocol.json')['source_hashes'].items()))
old=ROOT/'experiments/strong_evidence_20261019_01';manifest=json.loads((old/'evidence_manifest.json').read_text(encoding='utf8'))
check('previous experiment all105 manifested files unchanged',all(sha(old/x['path'])==x['sha256'] for x in manifest['files']))
check('C2 driver and dependencies unchanged from pre-inference lock',all(sha(ROOT/k)==v for k,v in load('rag_dev/protocol.json')['source_sha256'].items()))
simple=load('simple_baseline_controls/traces.json');simple_done=load('simple_baseline_controls/completion.json')
check('pure simple baselines obey Token budget without hidden overlap ceiling',all(x['coalition_tokens']<=72 for x in simple) and simple_done['exact_same_deliveries_as_prior_beta1_2'])
check('no additional LLM calls or invented attacker outputs for baseline correction',simple_done['real_new_LLM_calls']==0 and simple_done['unavailable_attacker_outputs_BLOCKED']==0)
by72={(x['asset'],x['kind'],x['method'],x['turn']):x for x in tr if x['beta']==.72}
check('figure simple-baseline points equal actual pure Token-only replay',all(x['delivered']==by72[(x['asset'],x['kind'],x['method'],x['turn'])]['delivered'] for x in simple))
(P/'validation.json').write_text(json.dumps({'status':'PASS','checks':checks,'count':len(checks),'scope':'invariants and executable truth fixtures, not external validity or human double annotation'},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'status':'PASS','checks':len(checks)}))
