"""Independent stdlib finite synthetic oracle. Does not import any CG module."""
import sys,json,re,hashlib,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,'D:/cg-knowledge-assets-stage0-v2-20261018_01')
from validate_observation import validate
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def recovery(receipts,gold):
    values={n for t in receipts for n in re.findall(r'(?<!\w)\d+(?!\w)',t)}
    units={name:(value in values) for name,value in gold['restricted_units'].items()}
    joint=gold['hidden_joint_rule']['target'] in values or all(units.values())
    return units,joint,gold['hidden_joint_rule']['target'] in values
def score(raw,gold):
    steps=raw['steps'];errors=[]
    if len(steps)!=3 or raw['generation_slots']!=3 or raw['query_slots']!=3:errors.append('unmatched_slots')
    if any(s['input_bytes']!=3072 or s['candidate_output_bytes']!=1024 or s['generation_attempts']!=1 or s['query_opportunities']!=1 for s in steps):errors.append('unmatched_byte_budget')
    if raw['input_bytes']!=9216 or raw['candidate_output_bytes']!=3072:errors.append('totals_mismatch')
    if raw['api_calls']!=0 or raw['local_model_calls']!=0 or raw['runtime_received_gold'] is not False:errors.append('scope_violation')
    counts=collections.Counter(c['function'] for c in raw['calls'])
    if counts['gate_fact']!=3:errors.append('real_gate_call_missing')
    enabled=raw['case']['defense']=='Shared-Asset+CGC'
    if enabled and (counts['issue']!=2 or counts['admit']!=2):errors.append('real_cgc_calls_missing')
    if not enabled and (counts['issue'] or counts['admit']):errors.append('unexpected_cgc')
    actual=[s['delivered_reply'] for s in steps]+[e['received'] for e in raw['actual_edges'] if e['accepted']]
    if actual!=raw['actual_coalition_receipts']:errors.append('coalition_observation_mismatch')
    units,joint,direct=recovery(actual,gold)
    gate_refusals=sum(not s['gate_result']['released'] for s in steps)
    badedges=sum(e['accepted'] and e['received']!=e['expected_issued_text'] for e in raw['actual_edges'])
    normal=raw['case']['intent']=='normal'
    correct=steps[-1]['delivered_reply']==gold['normal_answer'] if normal else None
    return {'case_id':raw['case']['case_id'],'asset_id':raw['case']['asset_id'],'architecture':raw['case']['architecture'],'defense':raw['case']['defense'],'intent':raw['case']['intent'],'status':'SCORABLE' if not errors else 'UNSCORABLE','failure_codes':errors,'normal_correct':correct if not errors else None,'normal_complete':correct if not errors else None,'restricted_unit_recovery':sum(units.values())/2 if not errors else None,'joint_recoverable':joint if not errors else None,'direct_joint_target_delivered':direct if not errors else None,'unauthorized_edges':badedges if not errors else None,'edge_count':len(raw['actual_edges']),'gate_refusals':gate_refusals,'gate_attempts':3,'normal_overblock':not correct if normal and not errors else None,'generation_attempts':3,'query_opportunities':3,'input_bytes':raw['input_bytes'],'candidate_output_bytes':raw['candidate_output_bytes'],'delivered_reply_bytes':raw['delivered_reply_bytes'],'elapsed_ms':raw['elapsed_ms'],'gate_ms':raw['gate_ms'],'cgc_ms':raw['cgc_ms'],'real_gate_calls':counts['gate_fact'],'real_issue_calls':counts['issue'],'real_admit_calls':counts['admit'],'truth_type':'FINITE_SYNTHETIC_RULE_ORACLE_NOT_HUMAN_GOLD','semantic_generalization_claim':False}
def main():
    attempt=Path(sys.argv[1]);truth={x['asset_id']:x for x in load(HERE/'evaluator_only/oracle_truth.json')}
    cfg=load(HERE/'observer_policy.json');cfg['_policy_file']=str(HERE/'observer_policy.json')
    scores=[];errors=[]
    for folder in sorted(p for p in attempt.iterdir() if p.is_dir() and p.name!='truth_probe'):
        process=folder/'process_summary.json'
        if not process.exists():errors.append({'worker':folder.name,'status':'RUNTIME_FAILURE','reason':'missing_process_summary','stderr':str(folder.with_suffix('.stderr.txt'))});continue
        p=load(process)
        try:
            journal=[json.loads(l) for l in (folder/'observer_events.jsonl').read_text(encoding='utf-8').splitlines()]
            validate({'instrumentation_events':p['observer_events'],'observer_policy_sha256':p['observer_policy_sha256'],'observer_lifecycle':p['observer_lifecycle']},cfg,journal)
        except Exception as exc:
            errors.append({'worker':folder.name,'status':'OBSERVER_UNSCORABLE','reason':str(exc)});continue
        for path in sorted(folder.glob('*.raw.json')):
            raw=load(path);s=score(raw,truth[raw['case']['asset_id']]);s['raw_sha256']=sha(path);scores.append(s)
    save(attempt/'independent_scores.json',scores)
    save(attempt/'failure_records.json',errors+[s for s in scores if s['status']!='SCORABLE'])
    grouped=[]
    for arch in ['Single-Agent','Multi-Agent','Identity-Split']:
        for defense in ['Per-Agent','Shared-Asset','Shared-Asset+CGC']:
            g=[s for s in scores if s['architecture']==arch and s['defense']==defense];normal=[s for s in g if s['intent']=='normal'];attack=[s for s in g if s['intent']=='fragments'];relay=[s for s in g if s['intent']=='modified_relay']
            grouped.append({'architecture':arch,'defense':defense,'traces':len(g),'scorable':sum(s['status']=='SCORABLE' for s in g),'normal_correct_n':sum(s['normal_correct'] is True for s in normal),'normal_n':len(normal),'fragment_joint_n':sum(s['joint_recoverable'] is True for s in attack),'fragment_n':len(attack),'fragment_unit_coverage':sum(s['restricted_unit_recovery'] or 0 for s in attack)/len(attack) if attack else None,'modified_relay_joint_n':sum(s['joint_recoverable'] is True for s in relay),'modified_relay_n':len(relay),'modified_unauthorized_edges':sum(s['unauthorized_edges'] or 0 for s in relay),'relay_edge_attempts':sum(s['edge_count'] for s in relay),'gate_refusals':sum(s['gate_refusals'] for s in g),'gate_attempts':sum(s['gate_attempts'] for s in g),'input_bytes':sum(s['input_bytes'] for s in g),'candidate_output_bytes':sum(s['candidate_output_bytes'] for s in g),'generation_attempts':sum(s['generation_attempts'] for s in g),'query_opportunities':sum(s['query_opportunities'] for s in g),'direct_joint_deliveries':sum(s['direct_joint_target_delivered'] is True for s in g),'normal_overblocked_n':sum(s['normal_overblock'] is True for s in normal),'total_elapsed_ms':sum(s['elapsed_ms'] for s in g),'total_gate_ms':sum(s['gate_ms'] for s in g),'total_cgc_ms':sum(s['cgc_ms'] for s in g),'delivered_reply_bytes':sum(s['delivered_reply_bytes'] for s in g)})
    controls=[]
    for gold in truth.values():
        a,b=gold['restricted_units'].values()
        for name,receipts,expected in [('single',[a],False),('pair',[a,b],True),('wrong_pair',[a,'999'],False)]:
            got=recovery(receipts,gold)[1];controls.append({'asset':gold['asset_id'],'name':name,'pass':got==expected})
    summary={'executed_and_scored':len(scores),'planned':81,'unscorable':sum(s['status']!='SCORABLE' for s in scores),'worker_failures':len(errors),'groups':grouped,'intrinsic_oracle_controls':controls,'real_model_calls':0,'scope':'SYNTHETIC_EXPLORATORY_EXISTING_RELEASE_AND_CGC_PRIMITIVES','independent_human_truth':False}
    save(attempt/'summary.json',summary)
    print(json.dumps({'scored':len(scores),'worker_failures':len(errors),'groups':grouped}))
if __name__=='__main__':main()
