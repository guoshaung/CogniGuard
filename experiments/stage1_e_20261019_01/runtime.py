"""Actual existing release/CGC primitive calls with equal fixed generators.
No evaluator imports or oracle input. Private source is used by trusted gate.
"""
import sys,os,json,hashlib,re,time,copy
from pathlib import Path
from dataclasses import asdict,replace
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,'D:/cg-knowledge-assets-stage0-v2-20261018_01')
def load(p):return json.loads(p.read_bytes())
def save(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def digest(t):return hashlib.sha256(t.encode()).hexdigest()
def main():
    arch,defense,out=sys.argv[1:4];out=Path(out);out.mkdir(exist_ok=False)
    from observer import Observer
    policy_path=HERE/'observer_policy.json';obs_policy=load(policy_path)
    observer=Observer(out/'observer_events.jsonl',obs_policy,obs_policy['truth_files']).install()
    def extra_guard(event,args):
        if event=='open':
            s=str(args[0]).replace('\\','/').lower()
            if any(k in s for k in ['stage1_e_20261019_01/evaluator_only','stage1_e_20261019_01/scorer.py','stage1_e_20261019_01/build_fixture.py']):raise PermissionError('runtime_forbidden_oracle_or_builder_read')
    sys.addaudithook(extra_guard)
    if arch=='TRUTH_PROBE':
        try:(HERE/'evaluator_only/oracle_truth.json').read_bytes()
        except PermissionError:save(out/'probe.json',{'result':'BLOCKED_BEFORE_READ','oracle_content_read':False,'events':observer.events});return
        raise RuntimeError('truth_access_not_blocked')
    calls=[]
    def profile(frame,event,arg):
        if event=='call':
            filename=frame.f_code.co_filename.replace('\\','/')
            if (filename.endswith('/experiments/c2rag_v3/fact_release.py') and frame.f_code.co_name=='gate_fact') or (filename.endswith('/core/langgraph_runtime/teachers/chain.py') and frame.f_code.co_name in ['issue','admit']):
                calls.append({'function':frame.f_code.co_name,'file':filename,'line':frame.f_code.co_firstlineno})
    sys.setprofile(profile)
    # Existing implementations, no local substitute or monkeypatch.
    from experiments.c2rag_v3.fact_release import gate_fact
    from core.langgraph_runtime.teachers.chain import TrustChain
    from core.langgraph_runtime.teachers.catalog import TeamSpec,TeacherNode,TeacherEdge
    assets={x['asset_id']:x for x in load(HERE/'runtime_inputs/assets.json')}
    cfg=load(HERE/'runtime_inputs/policy.json');rule=load(HERE/'runtime_inputs/generation_rule.json')
    cases=[x for x in load(HERE/'runtime_inputs/cases.json') if x['architecture']==arch and x['defense']==defense]
    prompt_hash=digest(json.dumps(rule,sort_keys=True))
    summaries=[]
    for case in cases:
        began=time.perf_counter();asset=assets[case['asset_id']];intent=case['intent'];cid=case['case_id'];start_call=len(calls)
        team=TeamSpec('fixture_team',tuple(TeacherNode('n'+str(i),'concept') for i in range(3)),(TeacherEdge('n0','n2'),TeacherEdge('n1','n2')),'n2')
        chain=TrustChain(cid,team,mode='enforce') if defense=='Shared-Asset+CGC' else None
        ledgers={};local_receipts=[];merge_receipts=[];deliveries=[];steps=[];gatemsec=0.;cgcmsec=0.
        for slot in range(3):
            prior=local_receipts[:] if arch=='Single-Agent' else []
            if slot==2:prior=local_receipts[:] if arch=='Single-Agent' else merge_receipts[:]
            fragment_key=cfg['query_schedule'][intent][slot]
            fragment=asset['fragments'][fragment_key] if fragment_key else ''
            request={'case':cid,'slot':slot+1,'fragment':fragment,'prior_delivered':prior,'public_operation':'multiply two integer replies, echo one, abstain none','intent':intent}
            request_json=json.dumps(request,sort_keys=True,ensure_ascii=True)
            if len(request_json.encode())>rule['input_bytes_per_slot']:raise RuntimeError('input_cap_exceeded')
            padded_input=request_json+' '*(rule['input_bytes_per_slot']-len(request_json.encode()))
            gen_start=time.perf_counter()
            if intent=='normal':answer='yes' if slot<2 else re.findall(r'\d+',fragment)[-1]
            elif slot<2:answer=re.findall(r'\d+',fragment)[-1]
            else:
                ns=[int(v) for v in prior if re.fullmatch(r'\d+',v)]
                answer=str(ns[0]*ns[1]) if len(ns)>=2 else str(ns[0]) if ns else ''
            quote=fragment if fragment else asset['fragments']['public']
            candidate={'abstain':not bool(answer),'answer':answer,'evidence':[{'document_id':asset['asset_id'],'quote':quote}]}
            generated_json=json.dumps(candidate,sort_keys=True,ensure_ascii=True)
            if len(generated_json.encode())>rule['candidate_output_bytes_per_slot']:raise RuntimeError('output_cap_exceeded')
            padded_generated=generated_json+' '*(rule['candidate_output_bytes_per_slot']-len(generated_json.encode()))
            gen_ms=(time.perf_counter()-gen_start)*1000
            session='same' if arch=='Single-Agent' else 'session_'+str(slot)
            key=session if defense=='Per-Agent' else cfg['delegation_root']+'/'+asset['asset_id']
            ledger=ledgers.setdefault(key,{})
            before=copy.deepcopy(ledger);tick=time.perf_counter()
            checked=gate_fact(json.loads(padded_generated),{asset['asset_id']:asset['source']},ledger,budget=cfg['ledger_budget'])
            gm=(time.perf_counter()-tick)*1000;gatemsec+=gm
            delivered=checked.get('answer','') if checked.get('released') else ''
            local_receipts.append(delivered)
            edge=None
            if slot<2:
                wire=delivered if delivered else 'REFUSED'
                if intent=='modified_relay' and slot==0:wire='999'
                tick=time.perf_counter()
                if chain:
                    issued=chain.issue('n'+str(slot),prompt_hash,delivered if delivered else 'REFUSED',data_labels=('controlled_resource',))
                    sent=replace(issued,text=wire) if wire!=issued.text else issued
                    view,record=chain.admit(sent,team.edges[slot],expected_prompt_hash=prompt_hash)
                    received=view.text if view else ''
                    edge={'source':'n'+str(slot),'target':'n2','issued':asdict(issued),'transmitted':asdict(sent),'native_record':record,'accepted':view is not None,'received':received,'expected_issued_text':issued.text,'transmitted_text':wire}
                else:
                    received=wire
                    edge={'source':'n'+str(slot),'target':'n2','accepted':True,'received':received,'expected_issued_text':delivered if delivered else 'REFUSED','transmitted_text':wire,'native_record':None,'guard':'NOT_ENABLED_IN_THIS_CONFIGURATION'}
                cgcmsec+=(time.perf_counter()-tick)*1000
                merge_receipts.append(received);deliveries.append(edge)
            steps.append({'slot':slot+1,'session':session,'ledger_key':key,'request':request,'input_bytes':len(padded_input.encode()),'generated_candidate':candidate,'candidate_output_bytes':len(padded_generated.encode()),'generation_attempts':1,'query_opportunities':1,'additional_source_returned':bool(fragment),'gate_result':checked,'ledger_before':before,'ledger_after':copy.deepcopy(ledger),'delivered_reply':delivered,'generation_ms':gen_ms,'gate_ms':gm,'relay':edge})
        raw={'case':case,'status':'COMPLETED','class':'SYNTHETIC_MECHANISM_ONLY','steps':steps,'actual_coalition_receipts':local_receipts+[d['received'] for d in deliveries if d['accepted']],'actual_edges':deliveries,'calls':calls[start_call:],'api_calls':0,'local_model_calls':0,'generation_slots':3,'query_slots':3,'input_bytes':sum(x['input_bytes'] for x in steps),'candidate_output_bytes':sum(x['candidate_output_bytes'] for x in steps),'delivered_reply_bytes':sum(len(v.encode()) for v in local_receipts),'gate_ms':gatemsec,'cgc_ms':cgcmsec,'elapsed_ms':(time.perf_counter()-began)*1000,'source_sha256':asset['source_sha256'],'budget':cfg['ledger_budget'],'accounting_unit':'UTF8_BYTES_PADDED_NOT_MODEL_TOKENS','runtime_received_gold':False}
        save(out/(cid+'.raw.json'),raw);summaries.append({'case_id':cid,'status':'COMPLETED'})
    sys.setprofile(None)
    save(out/'process_summary.json',{'architecture':arch,'defense':defense,'cases':summaries,'observer_policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest(),'observer_events':observer.events,'observer_lifecycle':observer.lifecycle(),'profile_scope':'Existing gate_fact/TrustChain issue/admit call entrypoints only; no frame locals captured'})
    print(json.dumps({'architecture':arch,'defense':defense,'completed':len(summaries)}))
if __name__=='__main__':main()
