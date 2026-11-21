"""Scripted protocol rehearsal only; never imports CG or reads source/gold."""
import json,sys,time
from pathlib import Path
def main():
    here=Path(__file__).resolve().parent;mode,architecture,defense,out=sys.argv[1:5]
    out=Path(out).resolve();started=time.perf_counter()
    def guard(event,args):
        if event=='open':
            value=str(args[0]).replace('\\','/').lower()
            if any(k in value for k in ['evaluator_only','annotation_packet','source_assets']):raise PermissionError('runtime_forbidden_source_or_truth_open')
        if event.startswith('socket.') or event.startswith('subprocess.'):raise PermissionError('runtime_network_and_subprocess_denied')
    sys.addaudithook(guard)
    if mode=='truth_probe':
        try:(here/'evaluator_only/AI_DRAFTS_NOT_GOLD/D01.json').read_text(encoding='utf-8')
        except PermissionError:
            out.write_text(json.dumps({'truth_open':'BLOCKED_BEFORE_READ','model_calls':0}),encoding='utf-8');return
        raise RuntimeError('truth_read_not_blocked')
    public=json.loads((here/'runtime_views/D01.json').read_bytes())
    records=[];past=[]
    for slot in (1,2,3):
        actor='single' if architecture in ('Single-Agent','Identity-Split') else ('worker_1' if slot==1 else 'worker_2' if slot==2 else 'merge')
        session='same_session' if architecture=='Single-Agent' else f'session_{slot}'
        visible=list(past) if architecture=='Single-Agent' or slot==3 else []
        query=public['query_slots'][slot-1]
        request={'slot':slot,'actor':actor,'session':session,'task':public['task'],'asset_id':'D01','query_receipt':query['receipt'],'upstream':visible,'intent_prompt':mode,'trusted_root':'fixture_delegation_01'}
        # No semantic material, reconstruction labels or independent gold in stub.
        reply=f'SCRIPTED_REPLY_{slot}'
        scope=f'{actor}/{session}' if defense=='Per-Agent' else 'fixture_delegation_01/D01' if defense in ('Shared-Asset','Shared-Asset+CGC') else 'none'
        records.append({'request':request,'output':reply,'refused':False,'query_attempts':1,'generation_attempts':1,'retry_attempts':0,'input_byte_units':len(json.dumps(request,sort_keys=True).encode()),'output_byte_units':len(reply.encode()),'ledger_scope':scope,'cgc_scheduled':defense=='Shared-Asset+CGC','executed_core_guard':False})
        past.append(reply)
    result={'architecture':architecture,'defense':defense,'mode':mode,'records':records,'attacker_delivered_union':past,'accounting':'DRYRUN_UTF8_BYTES_NOT_MODEL_TOKENS','model_calls':0,'semantic_risk_measured':False,'core_imports':False,'elapsed_ms':(time.perf_counter()-started)*1000}
    with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2)
if __name__=='__main__':main()
