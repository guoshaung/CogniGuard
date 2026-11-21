"""Read-only historical re-score and original-policy probes. No model transport."""
import ast, csv, hashlib, json, sys, time, sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).parent
START = time.perf_counter()
def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def lines(p): return [json.loads(s) for s in (ROOT/p).read_text(encoding='utf-8').splitlines() if s.strip()]
def write(name, obj): (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
REAL = 'experiments/results/cgc_propagation_v3_real_20261017_01'
BUNDLE = 'experiments/results/cgc_propagation_v3_bundle_20261017_01'
V2 = 'experiments/results/cgc_propagation_v2_bundle_20261017_01'
# Resolve original constant without constructing a model client.
from experiments.cgc_propagation_v3.audit import V2_BUNDLE
from experiments.cgc_propagation_v3.reviewer import judge
from experiments.cgc_propagation_v2.oracle import objective
from experiments.communication_security.evidence_protocol import EvidenceAssessor
cases = {r['case_id']:r for r in lines(str(V2_BUNDLE.relative_to(ROOT)/'public-cases.jsonl'))}
gold = {r['task_id']:r for r in lines(str(V2_BUNDLE.relative_to(ROOT)/'ground-truth.jsonl'))}
calls = lines(REAL+'/raw-model-calls.jsonl')
old = lines(REAL+'/pilot/independent-scores.jsonl')
rows, probes, audit_edges, audit_bad, db_missing = [], [], 0, [], []
manifest = read(REAL+'/evidence-manifest.json')
manifest_checks = {p: (ROOT/REAL/p).is_file() and sha(ROOT/REAL/p)==h for p,h in manifest.items()}
db = sqlite3.connect((ROOT/REAL/'teacher-audit.sqlite3').as_uri()+'?mode=ro', uri=True)
for saved in old:
    c=cases[saved['case_id']]; m=saved['method']
    raw=read(REAL+f"/pilot/raw-{c['case_id']}-{m}.json")
    cc=[r for r in calls if r['case_id']==c['case_id'] and r['method']==m]
    r=judge(raw,c,gold[c['task_id']],cc); r['method']=m; rows.append(r)
    if not db.execute('SELECT 1 FROM teacher_runs WHERE run_id=?',(raw['trace']['run_id'],)).fetchone(): db_missing.append(c['case_id']+'/'+m)
    delivered={(d['source'],d['target']):d for d in raw['receiver_inputs']}
    for e in raw['trace']['edges']:
        audit_edges+=1; d=delivered.get((e['source'],e['target']))
        if bool(d)!=e['accepted'] or (d and hashlib.sha256(d['text'].encode()).hexdigest()!=e['delivered_content_hash']):audit_bad.append(c['case_id']+'/'+m)
    if m=='FinalOnly':
        yes=EvidenceAssessor(c['task_id'],c['references'],c['choices'],handoff=True,final=True)
        off=EvidenceAssessor(c['task_id'],c['references'],c['choices'],handoff=False,final=True)
        for d in raw['receiver_inputs']:
            a=yes(d['text'],'','handoff'); b=off(d['text'],'','handoff')
            probes.append(dict(case_id=c['case_id'],condition=c['condition'],source=d['source'],target=d['target'],text_sha256=hashlib.sha256(d['text'].encode()).hexdigest(),boundary_allow=a.allow,disabled_allow=b.allow,reasons=list(a.reasons)))
db.close()
key={(r['case_id'],r['method']):r for r in rows}
for r in rows:
    if r['condition']=='attack': r['attack_success']=bool(objective(r,key[(r['case_id'].replace('-attack','-normal'),r['method'])]))
fields=['known','correct','attack_success','any_propagation','onward_any_propagation','unauthorized_read','outcome','refusal_kind']
mismatches=[{'case_id':s['case_id'],'method':s['method'],'field':f} for s in old for f in fields if s.get(f)!=key[(s['case_id'],s['method'])].get(f)]
methods=[]
for m in ('NoDefense','FinalOnly','FullCGC','SignatureOnly'):
    arm=[r for r in rows if r['method']==m]; atk=[r for r in arm if r['condition']=='attack']; normal=[r for r in arm if r['condition']=='normal']
    methods.append(dict(method=m,attack_n=len(atk),normal_n=len(normal),propagation=sum(r['any_propagation'] for r in atk),onward=sum(r['onward_any_propagation'] for r in atk),asr=sum(r['attack_success'] for r in atk),normal_correct=sum(r['correct'] for r in normal),policy_false_block=sum(r['refusal_kind']=='policy_block' for r in normal),normal_refusal=sum(r['outcome']=='refusal' for r in normal),sandbox_unauthorized=sum(r['unauthorized_read'] for r in atk),tool_attack_n=sum(r['family']=='tool_injection' for r in atk),invalid=sum(not r['known'] for r in arm),historical_trial_latency_sum_ms=round(sum(r['latency_ms'] for r in arm),3),attacks_without_observed_hazard=sum(not r['any_propagation'] and not r['polluted_generated_nodes'] for r in atk)))
write('rescored_metrics.json', methods)
write('boundary_policy_replay.json', probes)
write('rescored_cases.json', [{k:r.get(k) for k in ('case_id','method','condition','family',*fields)} for r in rows])
with (OUT/'cgc_control_ablation.csv').open('w',encoding='utf-8-sig',newline='') as f:
    names=['arm','status','evidence_type','attack_n','normal_n','unauthorized_real_calls','sandbox_unauthorized','malicious_propagation','onward_propagation','final_asr','normal_completed','policy_false_blocks','normal_refusals','historical_trial_latency_sum_ms','note']
    w=csv.DictWriter(f,fieldnames=names);w.writeheader()
    for label,m in [('A No-CGC','NoDefense'),('B FinalOnly','FinalOnly'),('C CapabilityOnly',None),('D ContextBoundaryOnly',None),('E Full-CGC','FullCGC'),('Supplement SignatureOnly','SignatureOnly')]:
        if m is None:w.writerow(dict(arm=label,status='NOT RUN',evidence_type='no equivalent existing full-chain switch',note='No surrogate implementation; boundary replay is conditional on saved messages, not end-to-end ablation'));continue
        a=next(x for x in methods if x['method']==m);n=a['attack_n']; nn=a['normal_n']
        w.writerow(dict(arm=label,status='HISTORICAL RE-SCORED',evidence_type='MiMo QASC controlled attack; synthetic tools',attack_n=n,normal_n=nn,unauthorized_real_calls='NOT MEASURED (no real tool dispatch)',sandbox_unauthorized=f"{a['sandbox_unauthorized']}/{n}",malicious_propagation=f"{a['propagation']}/{n}",onward_propagation=f"{a['onward']}/{n}",final_asr=f"{a['asr']}/{n}",normal_completed=f"{a['normal_correct']}/{nn}",policy_false_blocks=f"{a['policy_false_block']}/{nn}",normal_refusals=f"{a['normal_refusal']}/{nn}",historical_trial_latency_sum_ms=a['historical_trial_latency_sum_ms'],note='NoDefense retains shared prompt/wire gate/audit; SignatureOnly != CapabilityOnly; sum of recorded per-trial latency, not whole-run wall time'))
source_paths=['cogniguard/agents/agent_orchestrator.py','cogniguard/agents/protected_flow_graph.py','cogniguard/protection/cg/protocol.py','cogniguard/agents/copyright_aware_resource_agent.py','cogniguard/agents/pedagogical_teaching_agent.py','core/domain.py','cogniguard/governance/lifecycle.py','cogniguard/governance/capability.py','cogniguard/governance/evidence.py','cogniguard/governance/audit.py','core/langgraph_runtime/pipeline.py','core/langgraph_runtime/adapters.py','core/langgraph_runtime/teachers/chain.py','core/langgraph_runtime/teachers/dag.py','core/langgraph_runtime/teachers/store.py','experiments/evaluation/cg_v3_harness.py','experiments/evaluation/cg_v3_policy_composer.py','experiments/evaluation/cg_v3_budget.py','experiments/evaluation/cg_v3_state.py','experiments/communication_security/evidence_protocol.py','experiments/cgc_propagation_v2/live.py','experiments/cgc_propagation_v2/oracle.py','experiments/cgc_propagation_v3/reviewer.py','experiments/cgc_propagation_v3/score.py']
symbols=[]
for p in source_paths:
    tree=ast.parse((ROOT/p).read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            symbols.append(dict(path=p,symbol=node.name,line=node.lineno,end_line=node.end_lineno))
extra_paths=['protection/student_profile/src/fopd/privacy_budget.py','protection/teacher_resource/src/c2rag/exposure_budget.py','protection/audit_trace/src/hybrid_watermark.py','experiments/evaluation/cg_v3_schemas.py','experiments/evaluation/cg_v3_execution.py']
for p in extra_paths:
    source_paths.append(p)
    for node in ast.walk(ast.parse((ROOT/p).read_text(encoding='utf-8-sig'))):
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            symbols.append(dict(path=p,symbol=node.name,line=node.lineno,end_line=node.end_lineno))
write('source_symbol_index.json',symbols)
write('source_manifest.json',{p:sha(ROOT/p) for p in source_paths})
summary=dict(replay_seconds=round(time.perf_counter()-START,4),new_model_calls=0,rescored_trials=len(rows),rescore_mismatches=mismatches,historical_manifest_entries=len(manifest_checks),historical_manifest_pass=sum(manifest_checks.values()),historical_manifest_fail=[p for p,v in manifest_checks.items() if not v],audited_edges=audit_edges,delivery_hash_mismatches=audit_bad,sqlite_run_coverage=f'{len(rows)-len(db_missing)}/{len(rows)}',sqlite_missing=db_missing,boundary_probe_messages=len(probes),boundary_blocked_messages=sum(not p['boundary_allow'] for p in probes),boundary_disabled_blocked=sum(not p['disabled_allow'] for p in probes),boundary_attack_chains_blocked=sorted({p['case_id'] for p in probes if p['condition']=='attack' and not p['boundary_allow']}),boundary_normal_chains_blocked=sorted({p['case_id'] for p in probes if p['condition']=='normal' and not p['boundary_allow']}))
pilot_calls=[c for c in calls if (c['case_id'],c['method']) in key]
settings={}
for c in pilot_calls:
    body=c['request_body']; k=(c['case_id'],c['node_id'])
    settings.setdefault(k,set()).add(json.dumps({x:body[x] for x in ('model','temperature','seed','max_completion_tokens','thinking','response_format')},sort_keys=True))
summary['same_request_settings_independently_checked']=all(len(x)==1 for x in settings.values())
summary['pilot_model_calls']=len(pilot_calls)
summary['boundary_normal_messages']=sum(p['condition']=='normal' for p in probes)
summary['boundary_attack_messages']=sum(p['condition']=='attack' for p in probes)
summary['boundary_normal_rejected']=sum(p['condition']=='normal' and not p['boundary_allow'] for p in probes)
write('verification.json',summary)
print(json.dumps({'verification':summary,'metrics':methods},ensure_ascii=False,indent=2))
