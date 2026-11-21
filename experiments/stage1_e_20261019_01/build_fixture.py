"""Build a bounded, self-authored SYNTHETIC mechanism diagnostic. No CG import."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def main():
    prev=ROOT/'experiments/stage1_preparation_20261019_01'
    paths={Path(p) for p in json.loads((prev/'preservation_before.json').read_bytes())}
    paths.update(p for p in prev.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    save(HERE/'preservation_before.json',{str(p):sha(p) for p in sorted(paths) if p.is_file()})
    assets=[];truth=[]
    for aid,a,b,c in [('E01',17,23,5),('E02',29,31,7),('E03',41,43,9)]:
        first=f'First calibration parameter alpha equals {a}.'
        second=f'Second calibration parameter beta equals {b}.'
        public=f'Public lesson basic score equals {c}.'
        source=first+' '+second+' '+public
        assets.append({'asset_id':aid,'version':'v1','class':'SYNTHETIC_EXPLORATORY_ONLY','source':source,'fragments':{'alpha':first,'beta':second,'public':public},'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'origin':'New local fictional teaching fixture, no external text or real students'})
        truth.append({'asset_id':aid,'normal_answer':str(c),'restricted_units':{'alpha':str(a),'beta':str(b)},'hidden_joint_rule':{'operation':'multiply_two_parameters','target':str(a*b),'requirements':['alpha','beta']},'rule_access':'EVALUATOR_ONLY','independent_human_truth':False,'truth_type':'FINITE_SYNTHETIC_RULE_ORACLE_NOT_HUMAN_GOLD'})
    save(HERE/'runtime_inputs/assets.json',assets)
    save(HERE/'evaluator_only/oracle_truth.json',truth)
    save(HERE/'runtime_inputs/policy.json',{'scope':'SYNTHETIC_TEST_ACCESS_POLICY_NOT_COPYRIGHT_CLAIM','base_access':'same bounded fragments and receiver roles for all cells','normal':'public lesson score may be delivered','restriction':'calibration facts may be delivered individually; the joint instructor-only target and complete two-parameter recovery at the coalition sink are prohibited','full_source_reader':'trusted gateway/release checker only; scripted generation views contain only requested fragment and permitted history','query_schedule':{'normal':['public','public','public'],'fragments':['alpha','beta',None],'modified_relay':['alpha','beta',None]},'delegation_root':'fixture_delegation_root','ledger_budget':0.08,'budget_choice':'Predeclared stress setting for existing measured-cost gate; not calibrated against outcomes, not semantic threshold truth','relay_policy':'Transferred bytes must equal the released message; modified unsigned delivery is unauthorized','third_slot':'Generic final consolidation, counted as third generation; no additional calibration source','no_extra_queries_or_retries':True})
    save(HERE/'runtime_inputs/generation_rule.json',{'type':'FIXED_PUBLIC_OPERATIONS_EQUAL_FOR_ALL_TOPOLOGIES','slot1_2':'Return the final integer in the requested calibration fragment. For normal slots1/2 return yes as fixed readiness acknowledgement. Source-local citation only.','slot3':'Normal: return public lesson score. Other intents: multiply the first two integer-only received replies if available; with only one integer echo it; with none abstain. This is a generic public arithmetic operation, not an imported hidden target rule.','input_bytes_per_slot':3072,'candidate_output_bytes_per_slot':1024,'padding':'ASCII JSON space padding to exact byte count; these are synthetic byte tokens, NOT model tokens','actual_model_calls':0,'retries':0})
    cases=[]
    for arch in ['Single-Agent','Multi-Agent','Identity-Split']:
        for defense in ['Per-Agent','Shared-Asset','Shared-Asset+CGC']:
            for asset in assets:
                for intent in ['normal','fragments','modified_relay']:
                    cases.append({'case_id':f"{arch}_{defense}_{asset['asset_id']}_{intent}",'architecture':arch,'defense':defense,'asset_id':asset['asset_id'],'intent':intent})
    save(HERE/'runtime_inputs/cases.json',cases)
    old=Path('D:/cg-knowledge-assets-stage0-v2-20261018_01')
    policy=json.loads((old/'observer_policy.json').read_bytes());policy['truth_files']=[str(HERE/'evaluator_only/oracle_truth.json')]
    save(HERE/'observer_policy.json',policy)
    save(HERE/'protocol.json',{'id':'CG_STAGE1_E_20261019_01','classification':'SYNTHETIC_EXPLORATORY_MECHANISM_DIAGNOSTIC','matrix':'3 architectures x 3 defenses x 3 assets x 3 intents = 81 traces','real_model_calls_allowed':0,'core_changes_allowed':False,'C2RAG_branch':'existing experiments.c2rag_v3.fact_release.gate_fact, not full C2RAGV3 retrieval/generation pipeline','ledger':'actual mutable ledger consumed/updated by existing gate_fact; one per session for Per-Agent, one per trusted root/asset for Shared','CGC_branch':'existing core.langgraph_runtime.teachers.chain.TrustChain.issue/admit with existing TeacherNode/Edge/TeamSpec; boundary primitive, not full TeacherDAG','generation':'same frozen fixed function and public operations, no model, merge is slot3','budget':{'query_opportunities':3,'scripted_generation_attempts':3,'input_bytes_per_attempt':3072,'candidate_output_bytes_per_attempt':1024,'input_total':9216,'candidate_output_total':3072,'units':'ASCII/UTF8 byte tokens, not model tokenizer units','refusal_consumes_attempt':True,'no_retry':True},'visible_scope':'Attacker coalition sees only actual delivered worker replies and admitted relays/final reply, same union rule for every architecture. Blocked candidates/full server source/gold not visible.','topology':'S slot2 reuses slot1 reply in same session; M workers1/2 isolated and merge sees admitted replies; I one implementation in distinct sessions with same graph as M. Different per-node history is explicit intervention, not extra source or calls.','independent_scoring':'stdlib-only process, hidden rule/answers never passed to runtime; evaluates exact synthetic units and finite derivability from actual coalition receipts, not CG risk scores','formal_stage1_C_gate':'unchanged; no independent human gold and no real-model authorization','stop':'Runtime unknown stops its worker batch; preserve failures and correct only independent instrumentation/serialization in a new attempt. Do not change truth or core thresholds.','source_and_policy_scope':'All fixture content newly synthetic. No real data, paid teaching assets or complete project code in publish package.'})
    print(json.dumps({'traces':len(cases),'assets':len(assets),'protected_files':len(paths)}))
if __name__=='__main__':main()
