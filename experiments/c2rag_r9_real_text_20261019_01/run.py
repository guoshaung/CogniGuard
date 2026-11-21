"""E1 first, then only supported contracts E2/E3. No model inference or network."""
from pathlib import Path
import csv,hashlib,json,os,sys,time
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.stdout.reconfigure(encoding='utf8')
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
import engine as E
def read(n):return json.loads((P/n).read_text(encoding='utf8'))
def write(n,x):
    with (P/n).open('x',encoding='utf8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def csvout(n,rows,columns):
    with (P/n).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows({k:r.get(k) for k in columns} for r in rows)
def checked():
    protocol=read('protocol.json')
    for f,h in protocol['hashes'].items():assert hashlib.sha256((P/f).read_bytes()).hexdigest()==h,f
    return protocol
def atomset(x):return {tuple(a) for a in x}
def extraction():
    checked();contracts={c['id']:c for c in read('public_contracts.json')};rows=[]
    for item in read('e1_author_annotations.json'):
        gold=atomset(item['gold_atoms']);contract=contracts[item['asset']]
        for name,fn in E.EXTRACTORS.items():
            pred,unknown=fn(item['text'],item['query'],contract)
            tp=len(gold&pred);fp=len(pred-gold);miss=len(gold-pred)
            status='PASS' if pred==gold and not unknown else 'FAIL' if pred else 'UNKNOWN'
            precision=tp/(tp+fp) if tp+fp else None;recall=tp/len(gold) if gold else None
            f1=2*tp/(2*tp+fp+miss) if 2*tp+fp+miss else None
            rows.append({'asset':item['asset'],'item':item['id'],'text_kind':item['text_kind'],'method':name,
                         'status':status,'tp':tp,'fp':fp,'fn':miss,'precision':precision,'recall':recall,'f1':f1,
                         'unknown':status=='UNKNOWN','unresolved_relations':unknown,
                         'predicted_atoms':sorted(pred),'gold_atoms':sorted(gold),'text':item['text'],
                         'query':item['query'],'source_locator':item['source_locator']})
    write('e1_raw_results.json',rows)
    csvout('c2rag_r9_relation_extraction.csv',rows,['asset','item','text_kind','method','status','tp','fp','fn','precision','recall','f1','unknown','source_locator','text'])
    summaries=[]
    for name in E.EXTRACTORS:
        for scope in ['all','raw_paragraph','source_subspan']:
            selected=[r for r in rows if r['method']==name and (scope=='all' or r['text_kind']==scope)]
            tp=sum(r['tp'] for r in selected);fp=sum(r['fp'] for r in selected);fn=sum(r['fn'] for r in selected)
            summaries.append({'method':name,'scope':scope,'items':len(selected),'pass_n':sum(r['status']=='PASS' for r in selected),
                              'fail_n':sum(r['status']=='FAIL' for r in selected),'unknown_n':sum(r['unknown'] for r in selected),
                              'unknown_rate':sum(r['unknown'] for r in selected)/len(selected),'tp':tp,'fp':fp,'fn':fn,
                              'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
                              'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None})
    write('e1_summary.json',summaries)
    eligibility=[]
    for c in contracts.values():
        selected=[r for r in rows if r['asset']==c['id'] and r['text_kind']=='source_subspan' and r['method']=='Arithmetic-Logical-Representation']
        eligibility.append({'asset':c['id'],'required_candidate_n':2,'passed':sum(r['status']=='PASS' for r in selected),
                            'eligible':len(selected)==2 and all(r['status']=='PASS' for r in selected),
                            'scope':'source numeric/unit sub-contract only; not full causal/process comprehension'})
    write('e1_to_e2_gate.json',eligibility)
    print(json.dumps({'E1_items':len(rows)//4,'method_rows':len(rows),'eligible_assets':eligibility},ensure_ascii=False))

def partial(attack,contract):
    if attack['parameters'] is not None:return 1.
    if contract['kind']=='affine':return .5 if attack['constraints'] else 0.
    if contract['kind']=='hotcold':return len(attack['parts'])/2
    return 0.

def run_e23():
    protocol=checked();gate={x['asset']:x['eligible'] for x in read('e1_to_e2_gate.json')}
    from transformers import AutoTokenizer
    tokenizer_path=ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'
    tok=AutoTokenizer.from_pretrained(str(tokenizer_path),local_files_only=True)
    def tids(s):return tok.encode(s,add_special_tokens=False)
    contracts={x['id']:x for x in read('public_contracts.json')}
    gold={x['id']:tuple(x['target_parameters']) for x in read('author_gold_contracts.json')}
    rows=[];start=time.perf_counter()
    for plan in read('e2_frozen_plans.json'):
        if not gate[plan['asset']]:
            rows.append({'asset':plan['asset'],'scenario':plan['scenario'],'status':'NOT_RUN_E1_GATE'});continue
        c=contracts[plan['asset']]
        for method in protocol['e2_methods']:
            active=len(set(plan['agents']));used={i:0 for i in set(plan['agents'])};cost={i:0. for i in used}
            history=[];locals_={i:[] for i in used};turns=[]
            for i,(candidate,agent) in enumerate(zip(plan['candidates'],plan['agents'])):
                q,r=candidate['q'],candidate['r'];scope=locals_[agent] if method=='Ablation-Independent-Closure' else history
                detector='B4-Closure' if method in ['Diagnostic-Conditional-Contract','Ablation-Independent-Closure'] else method
                if method in ['B0-Raw-RAG-budgeted','B1-StaticQuota','B2-SharedAdditive']:
                    check={'risk':0,'unknown':False,'unsupported':['budget only, no content inference']}
                else:check=E.assess(scope+[(q,r)],c,detector)
                source_check=E.typed(r,q,c);expected=candidate.get('atoms')
                candidate_status='UNSUPPORTED' if expected is None or source_check[1] else 'PASS' if source_check[0]==atomset(expected) else 'FAIL'
                delivered=r;reason='allow'
                if len(tids(r))>64 or used[agent]+len(tids(r))>128/active or sum(used.values())+len(tids(r))>128:
                    delivered='';reason='token_budget'
                elif cost[agent]+.5>1/active+1e-9 or sum(cost.values())+.5>1+1e-9:delivered='';reason='opportunity_budget'
                elif method not in ['B0-Raw-RAG-budgeted','B1-StaticQuota','B2-SharedAdditive','B3-SharedSet-RuleClosure'] and check['risk']!=0:
                    delivered='';reason='risk_or_unknown'
                elif method=='B3-SharedSet-RuleClosure' and check['risk']==1:delivered='';reason='slots_complete'
                if delivered:used[agent]+=len(tids(delivered));cost[agent]+=.5
                # Visible queries always retained, including on an empty refusal.
                history.append((q,delivered));locals_[agent].append((q,delivered))
                actual,unknown=E.typed(delivered,q,c)
                correct=atomset(expected)<=actual and not unknown if expected is not None else None
                turns.append({'turn':i,'agent':agent,'query':q,'candidate':r,'delivered':delivered,
                              'candidate_status':candidate_status,'candidate_kind':candidate.get('kind','exact_source'),
                              'risk':check['risk'],'detector_unknown':check['unknown'],'detector_detail':check,
                              'correct':correct,'reason':reason,'tokens':len(tids(delivered)),'token_ids':tids(delivered),
                              'coalition_tokens':sum(used.values()),'additive_cost':sum(cost.values())})
            # Common attacker does not use each defense's parser or hidden gold.
            recovered=E.attacker(history,c)
            known_questions=[t for t in turns if t['correct'] is not None]
            complete=(recovered['complete'] and tuple(recovered['parameters'])==gold[c['id']]) if recovered['complete'] is not None else None
            scorable=plan['scorable'] and not recovered['unknown']
            if not scorable:complete=None
            pf=partial(recovered,c)
            rows.append({'asset':c['id'],'scenario':plan['scenario'],'method':method,
                         'status':'SCORED' if scorable else 'UNSUPPORTED',
                         'complete_recovery':complete,'partial_relation_fraction_lower_bound':pf,
                         'partial_only':(0<pf<1) if scorable else None,
                         'correct_n':sum(t['correct'] is True for t in known_questions),'scorable_questions':len(known_questions),
                         'unknown_questions':sum(t['correct'] is None for t in turns),
                         'normal_accuracy':sum(t['correct'] is True for t in known_questions)/len(known_questions) if known_questions else None,
                         'actual_tokens':sum(used.values()),'refusal_n':sum(not t['delivered'] for t in turns),'substitution_n':0,
                         'detector_unknown_n':sum(t['detector_unknown'] for t in turns),'candidate_n':len(turns),
                         'attacker_unknown':recovered['unknown'],'attacker':recovered,'turns':turns})
    write('e2_raw_results.json',rows)
    csvout('c2rag_r9_multiagent_reconstruction.csv',rows,['asset','scenario','method','status','complete_recovery',
        'partial_relation_fraction_lower_bound','partial_only','correct_n','scorable_questions','unknown_questions',
        'normal_accuracy','actual_tokens','refusal_n','substitution_n','detector_unknown_n','candidate_n','attacker_unknown'])
    e3=[]
    for case in read('e3_frozen_candidates.json'):
        asset=case['asset'];c=contracts[asset]
        if not gate[asset]:e3.append({'asset':asset,'status':'NOT_RUN_E1_GATE'});continue
        prefix=[(case['prefix']['q'],case['prefix']['r'])];q=case['query'];required=atomset(case['required_task_atoms'])
        for strategy,key in [('Original-Full','full'),('Simple-Refusal','refuse'),('Fixed-Reminder','fixed_reminder'),('Knowledge-Local','knowledge_local')]:
            proposed=case[key];check=E.assess(prefix+[(q,proposed)],c)
            # The original is the deliberately unsafe control; score its risk too.
            delivered=proposed if strategy=='Original-Full' or check['risk']==0 else ''
            known,unresolved=E.typed(delivered,q,c);coverage=len(known&required)/len(required)
            outcome=E.attacker(prefix+[(q,delivered)],c)
            complete=(outcome['complete'] and tuple(outcome['parameters'])==gold[asset]) if outcome['complete'] is not None else None
            tokens=len(tids(delivered));prefix_tokens=len(tids(case['prefix']['r']))
            assert tokens<=64 and prefix_tokens<=64 and tokens+prefix_tokens<=128
            e3.append({'asset':asset,'strategy':strategy,'status':'SCORED' if not unresolved and not outcome['unknown'] else 'UNSUPPORTED',
                       'normal_correct':required<=known and not unresolved,'teaching_fact_coverage':coverage,
                       'complete_recovery':complete,'reply_tokens':tokens,'total_history_reply_tokens':tokens+prefix_tokens,
                       'reply_characters':len(delivered),'empty_refusal':not bool(delivered),
                       'substitution':bool(delivered) and strategy in ['Fixed-Reminder','Knowledge-Local'],
                       'meaningless_reminder':False,
                       'meaningless_basis':'fixed reminder supplies a relevant procedure, local supplies source facts; neither is counted fully correct without required facts',
                       'risk_checked':True,'proposed_risk':check['risk'],'risk_unknown':check['unknown'],
                       'source_construction':case['candidate_construction'],'query':q,'proposed':proposed,'delivered':delivered,
                       'token_ids':tids(delivered),'required_atoms':sorted(required),'delivered_atoms':sorted(known),
                       'prefix_visible':prefix,'attacker':outcome})
    write('e3_raw_results.json',e3)
    csvout('c2rag_r9_safety_utility.csv',e3,['asset','strategy','status','normal_correct','teaching_fact_coverage',
        'complete_recovery','reply_tokens','total_history_reply_tokens','reply_characters','empty_refusal','substitution',
        'meaningless_reminder','risk_checked','proposed_risk','risk_unknown'])
    # Matched-input diagnostic: representation/closure identical, not new risk method.
    matches=[]
    for plan in read('e2_frozen_plans.json'):
        z={r['method']:r for r in rows if r.get('asset')==plan['asset'] and r.get('scenario')==plan['scenario'] and 'method' in r}
        if not z:continue
        aa=z['B4-Closure'];bb=z['Diagnostic-Conditional-Contract']
        identical=[(t['delivered'],t['token_ids']) for t in aa['turns']]==[(t['delivered'],t['token_ids']) for t in bb['turns']]
        assert identical;matches.append({'asset':plan['asset'],'scenario':plan['scenario'],'identical_delivery_and_tokens':identical})
    write('matched_representation_checks.json',matches)
    old=read('preservation_before.json');after={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in old}
    assert old==after;write('preservation_after.json',after)
    write('completion.json',{'status':'COMPLETED_EXPLORATORY_R9','source_pages':4,'source_books':2,'knowledge_assets':4,
        'eligible_numeric_subcontracts':sum(gate.values()),'new_independent_blind_assets':0,
        'e1_method_rows':len(read('e1_raw_results.json')),'e2_method_episode_rows':len(rows),'e3_strategy_asset_rows':len(e3),
        'model_inference_calls':0,'paid_api_calls':0,'new_large_model_downloads':0,
        'runtime_after_tokenizer_seconds':time.perf_counter()-start,'decision':'PIVOT',
        'scope':'real source-linked development text; deterministic extraction/release/reconstruction, no end-to-end RAG model test'})
    print(json.dumps(read('completion.json'),ensure_ascii=False))

if __name__=='__main__':
    if sys.argv[1:]==['e1']:extraction()
    elif sys.argv[1:]==['e23']:run_e23()
    else:raise SystemExit('run e1, inspect eligibility, then e23')
