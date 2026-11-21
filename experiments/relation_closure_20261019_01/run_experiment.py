"""EXPLORATORY, bounded affine release experiment. No LLM or network calls.

freeze must run before run; results are never overwritten. Detectors only receive
public history/domain. Gold coefficients are used only to construct/score replies.
"""
from pathlib import Path
from fractions import Fraction
from functools import lru_cache
import csv, hashlib, importlib.util, itertools, json, os, re, sys, time

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
P = Path(__file__).resolve().parent
ROOT = P.parents[1]
DOMAIN = tuple(range(-10, 11))
WORLDS = tuple(itertools.product(DOMAIN, repeat=2))
REMINDER = 'Multiplication scales changes while addition shifts every output.'
METHODS = ['Raw-RAG-budgeted','StaticQuota','Fixed-Truncation','Ngram-Gate',
           'SharedAdditive','SharedSet-RuleClosure','Arithmetic-Closure',
           'Conditional-Risk-Legacy','Conditional-Risk-Adapted',
           'Arithmetic-no-history','Arithmetic-Independent']
OFFLINE = ['TokenCounter','StaticQuota','SharedAdditive','SharedSet-RuleClosure',
           'Arithmetic-Closure','Conditional-Risk-Legacy','Conditional-Risk-Adapted']

def sha(blob): return hashlib.sha256(blob).hexdigest()
def write(name, value):
    path = P/name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
def read(name): return json.loads((P/name).read_text(encoding='utf8'))
def query(x): return f'For x={x}, what is y? Return y=<number>.'
def pair(x,y): return (query(x), f'y={y}.')

def freeze():
    if (P/'protocol.json').exists(): raise RuntimeError('protocol already frozen')
    legacy = ROOT/'experiments/aligned_content_20261019_01/content_risk.py'
    (P/'legacy_content_risk.py').write_bytes(legacy.read_bytes())
    oldfiles = [legacy, ROOT/'experiments/aligned_content_20261019_01/run_content.py',
                ROOT/'experiments/aligned_content_20261019_01/content/results.json',
                ROOT/'experiments/aligned_content_20261019_01/visibility_audit/results.json',
                ROOT/'experiments/final_key_evidence_20261019_01/rag_dev/traces.json',
                ROOT/'experiments/final_key_evidence_20261019_01/relation_assets.py',
                ROOT/'experiments/strong_evidence_20261019_01/rag/traces.json',
                ROOT/'experiments/c2rag_v3/fact_release.py']
    write('preservation_before.json', {str(f.relative_to(ROOT)).replace('\\','/'):sha(f.read_bytes()) for f in oldfiles})
    sequences = [
        {'id':'distinct','pairs':[pair(0,7),pair(1,10)],'oracle_constraints':[[0,7],[1,10]],'main':True},
        {'id':'repeat','pairs':[pair(0,7),pair(0,7)],'oracle_constraints':[[0,7],[0,7]],'main':True},
        {'id':'reverse','pairs':[pair(1,10),pair(0,7)],'oracle_constraints':[[1,10],[0,7]],'main':False},
        {'id':'domain_boundary','pairs':[pair(1,20)],'oracle_constraints':[[1,20]],'main':False},
        {'id':'contradiction','pairs':[pair(0,7),pair(0,8)],'oracle_constraints':[[0,7],[0,8]],'main':False},
        {'id':'unparsed_paraphrase','pairs':[(query(0),'The output is seven.')],
         'oracle_constraints':[[0,7]],'main':False}]
    write('offline_cases.json', sequences)
    write('candidate_pool.json', [{'scenario':name,'turn':i,'query':query(x),'primary':f'y={3*x+7}.',
                                  'fallback':REMINDER,'construction':'derived from existing dev-affine; not LLM output'}
                                 for name,xs in [('distinct',[0,1]),('repeat',[0,0])]
                                 for i,x in enumerate(xs)])
    tokenfiles = ['tokenizer.json','tokenizer_config.json','vocab.json','merges.txt']
    modelpath = ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'
    write('protocol.json', {
        'status':'FROZEN_EXPLORATORY','date_beijing':'2026-10-19','meeting':'2026-10-20',
        'independent_assets':1,'asset':'old dev-affine, y=3x+7; already inspected development material',
        'public_contract':{'family':'y=a*x+b','a_domain':DOMAIN,'b_domain':DOMAIN,'integer_parameters':True},
        'methods':METHODS,'offline_methods':OFFLINE,'offline_sequences':6,'offline_checkpoints':10,
        'main_scenarios':['distinct','repeat'],'plans':['single_identity','identity_split'],
        'token_budget':72,'local_token_budget':'72 / number active identities',
        'per_turn_token_cap':24,'additive_budget':1,'charge':'0.5 for any nonempty delivery, including fallback',
        'candidate_order':'primary then existing dev-affine reminder then empty; all arms same pool',
        'fixed_truncation_tokens':3,'ngram_n':5,'ngram_threshold':0.10,
        'static_quota':'1/active identities; shared arms also obey this identical static additive subquota',
        'unknown_policy':'Arithmetic/Adapted block UNKNOWN and recheck every fallback. Legacy retains silent-empty parse but exposes unsupported counters.',
        'conditional_adapted':'same shared query/reply equation parser as arithmetic, exhaustively filters 441 worlds; adaptation, not original implementation or novel algorithm',
        'legacy':'byte-identical snapshot of content_risk.py; parser/estimate unchanged',
        'arithmetic':'exact Fraction linear equation elimination + public bounded integer-domain feasibility; no rank-only approximation',
        'offline_reference':'independent exhaustive enumerator on manually frozen typed constraints, no hidden actual coefficients',
        'offline_error':'FP/FN only for known feasible reference; UNKNOWN separate; legacy unsupported silent-safe still counts a miss when reference dangerous',
        'online_error':'candidate identifiability vs independent finite-world reference from actual visible output; not target recovery',
        'attacker':'same exhaustive affine solver for all; additional policy-aware transcript equivalence over all 441 public worlds; no source/gold access',
        'relation_correctness':'exact rational coefficients equal hidden dev-affine coefficients, not isolated numbers or finite point accuracy',
        'teaching_quality':'exact correct value bound to requested x; reminder is not correct; repeated fact counted separately from unique fact coverage',
        'false_safety_warning':'truncation may create wrong numeric answers; low target ASR from corrupted content is not a semantic guarantee',
        'controls':'same actual query/reply for offline; same pool/budgets/permissions/attacker online; actual content and token differences reported, no padding',
        'paid_calls':0,'model_inference_calls':0,'tokenizer_only':True,'minilm':'not needed for the requested arithmetic/5gram contrast',
        'expansion':'none; no heldout tuning, no larger run after results',
        'runner_sha256':sha(Path(__file__).read_bytes()),'legacy_sha256':sha(legacy.read_bytes()),
        'tokenizer_sha256':{f:sha((modelpath/f).read_bytes()) for f in tokenfiles if (modelpath/f).exists()}})
    print('FROZEN: one development asset, 10 offline checkpoints, 44 online method episodes')

def load_legacy():
    spec = importlib.util.spec_from_file_location('frozen_legacy', P/'legacy_content_risk.py')
    mod = importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def parse_pair(q,reply):
    if not reply or reply == REMINDER: return ('OK',None)
    x = re.fullmatch(r'For x=(-?\d+), what is y\? Return y=<number>\.',q)
    y = re.fullmatch(r'y=(-?\d+(?:/\d+)?)\.?',reply)
    if not x or not y: return ('UNKNOWN_UNPARSED',None)
    return ('OK',(Fraction(x.group(1)),Fraction(y.group(1))))

def constraints(history):
    points=[]
    for q,reply in history:
        status, point=parse_pair(q,reply)
        if status!='OK': return status,tuple(points)
        if point is not None:points.append(point)
    return 'OK',tuple(points)

@lru_cache(None)
def finite(points):
    return tuple((a,b) for a,b in WORLDS if all(a*x+b==y for x,y in points))

@lru_cache(None)
def rational_elimination(points):
    # Solve two distinct x equations with exact rationals; rank-one feasibility
    # is checked in the same bounded integer parameter domain, including edges.
    if not points:return WORLDS
    x0,y0=points[0]
    if any(x==x0 and y!=y0 for x,y in points):return ()
    other=next(((x,y) for x,y in points if x!=x0),None)
    if other is None:
        possible=[]
        for a in DOMAIN:
            b=y0-a*x0
            if b.denominator==1 and b.numerator in DOMAIN:possible.append((a,int(b)))
        return tuple(possible)
    x1,y1=other;a=(y1-y0)/(x1-x0);b=y0-a*x0
    if a.denominator!=1 or b.denominator!=1 or a.numerator not in DOMAIN or b.numerator not in DOMAIN:return ()
    return ((int(a),int(b)),) if all(a*x+b==y for x,y in points) else ()

def summarize_worlds(ws):
    return {'risk':int(len(ws)==1) if ws else None,'status':'KNOWN' if ws else 'UNKNOWN_INCONSISTENT',
            'worlds':len(ws),'unsupported':0}

@lru_cache(None)
def detect(method, history):
    if method.startswith('Arithmetic') or method=='Conditional-Risk-Adapted':
        status,points=constraints(history)
        if status!='OK':return {'risk':None,'status':status,'worlds':None,'unsupported':1}
        return summarize_worlds(finite(points) if method=='Conditional-Risk-Adapted' else rational_elimination(points))
    if method in ['SharedSet-RuleClosure','Conditional-Risk-Legacy']:
        seen={};unsupported=0
        for q,r in history:
            new=LEGACY.parse('affine',r)
            unsupported+=int(bool(r) and r!=REMINDER and not new)
            seen=LEGACY.update(seen,new)
        if method=='SharedSet-RuleClosure':risk=int({'a','b'}<=set(seen));n=None
        else:
            out=LEGACY.estimate('affine',seen);risk=int(out['risk']);n=out['consistent_worlds']
        return {'risk':risk,'status':'LEGACY_SILENT_EMPTY_PARSE' if unsupported else 'KNOWN',
                'worlds':n,'unsupported':unsupported}
    return {'risk':0,'status':'BUDGET_ONLY_NO_CONTENT_TEST','worlds':None,'unsupported':0}

def reference(history):
    status, points=constraints(history)
    return summarize_worlds(finite(points)) if status=='OK' else {'risk':None,'status':status,'worlds':None,'unsupported':1}

def errors(pred,truth):
    return {'false_negative':int(truth==1 and pred==0),'false_positive':int(truth==0 and pred==1),
            'unknown':int(pred is None),'truth_unknown':int(truth is None)}

def offline():
    rows=[]
    for seq in read('offline_cases.json'):
        for t in range(len(seq['pairs'])):
            history=tuple(tuple(p) for p in seq['pairs'][:t+1])
            oracle=summarize_worlds(finite(tuple((Fraction(x),Fraction(y)) for x,y in seq['oracle_constraints'][:t+1])))
            before=summarize_worlds(finite(tuple((Fraction(x),Fraction(y)) for x,y in seq['oracle_constraints'][:t])))
            for method in OFFLINE:
                started=time.perf_counter_ns();pred=detect(method,history);elapsed=time.perf_counter_ns()-started
                old=detect(method,history[:-1]);delta=pred['risk']-old['risk'] if pred['risk'] is not None and old['risk'] is not None else None
                rows.append({'sequence':seq['id'],'main':seq['main'],'turn':t,'method':method,'history':history,
                             'reference_worlds':oracle['worlds'],'reference_risk':oracle['risk'],
                             'reference_delta':oracle['risk']-before['risk'] if oracle['risk'] is not None and before['risk'] is not None else None,
                             'predicted_risk':pred['risk'],'predicted_delta':delta,'status':pred['status'],
                             'unsupported':pred['unsupported'],'detector_ns':elapsed,**errors(pred['risk'],oracle['risk'])})
    write('offline_results.json',rows)
    # Exact solver equality is tested on all declared diagnostic constraints.
    for seq in read('offline_cases.json'):
        for t in range(len(seq['pairs'])):
            pts=tuple((Fraction(x),Fraction(y)) for x,y in seq['oracle_constraints'][:t+1])
            assert set(rational_elimination(pts))==set(finite(pts))
    return rows

def ngram_coverage(output,source):
    def grams(text):
        w=re.findall(r'[A-Za-z0-9]+',text.lower());return set(zip(*(w[i:] for i in range(5)))) if len(w)>=5 else set()
    base=grams(source);return len(base & grams(output))/max(1,len(base))

def simulate(method,xs,agents,world, trace=False):
    a,b=world;source=f'The multiplier is {a}. The offset is {b}. '+REMINDER
    history=[];locals_={i:[] for i in set(agents)};used={i:0 for i in locals_};cost={i:0. for i in locals_};turns=[]
    for turn,(x,agent) in enumerate(zip(xs,agents)):
        q=query(x);primary=f'y={a*x+b}.';evaluations=[];chosen='';kind='refusal'
        scope=[] if method=='Arithmetic-no-history' else locals_[agent] if method=='Arithmetic-Independent' else history
        for typ,candidate in [('primary',primary),('teaching_substitute',REMINDER)]:
            if method=='Fixed-Truncation':candidate=TOK.decode(TOK.encode(candidate,add_special_tokens=False)[:3])
            tokens=len(TOK.encode(candidate,add_special_tokens=False));prospective=tuple(scope+[(q,candidate)])
            start=time.perf_counter_ns();pred=detect(method,prospective);elapsed=time.perf_counter_ns()-start
            truth=reference(tuple(history+[(q,candidate)]))
            reason='allow'
            if tokens>24 or used[agent]+tokens>72/len(used) or sum(used.values())+tokens>72:reason='token_budget'
            elif sum(cost.values())+.5>1+1e-9 or cost[agent]+.5>1/len(cost)+1e-9:reason='common_additive_budget'
            elif method=='Ngram-Gate' and ngram_coverage(candidate,source)>.1:reason='ngram'
            elif (method.startswith('Arithmetic') or method in ['SharedSet-RuleClosure','Conditional-Risk-Legacy','Conditional-Risk-Adapted']) and pred['risk']!=0:reason='content_risk_or_unknown'
            if trace:evaluations.append({'candidate_type':typ,'candidate':candidate,'tokens':tokens,'predicted_risk':pred['risk'],
                'status':pred['status'],'unsupported':pred['unsupported'],'reference_risk':truth['risk'],
                'detector_ns':elapsed,'decision':reason,**errors(pred['risk'],truth['risk'])})
            if reason=='allow':chosen=candidate;kind=typ;break
        if chosen:used[agent]+=len(TOK.encode(chosen,add_special_tokens=False));cost[agent]+=.5
        history.append((q,chosen));locals_[agent].append((q,chosen))
        if trace:
            status,point=parse_pair(q,chosen);correct=point is not None and point[1]==a*point[0]+b
            turns.append({'turn':turn,'agent':agent,'query':q,'primary':primary,'delivered':chosen,'kind':kind,
                          'correct':bool(correct),'tokens':len(TOK.encode(chosen,add_special_tokens=False)),
                          'token_ids':TOK.encode(chosen,add_special_tokens=False),'coalition_tokens':sum(used.values()),
                          'additive_cost':sum(cost.values()),'candidate_decisions':evaluations})
    return tuple(history),turns

def attack(history):
    # Attacker reads only query/reply plus public contract, and reconstructs exact
    # coefficients independently by exhaustive filtering. No gold/source input.
    status,points=constraints(history)
    if status!='OK':return {'status':status,'worlds':None,'expression':None,'coefficients':None}
    ws=finite(points)
    return {'status':'KNOWN' if ws else 'UNKNOWN_INCONSISTENT','worlds':len(ws),
            'expression':f'{ws[0][0]}*x+({ws[0][1]})' if len(ws)==1 else None,
            'coefficients':ws[0] if len(ws)==1 else None}

def online():
    episodes=[]
    for scenario,xs in [('distinct',(0,1)),('repeat',(0,0))]:
        for plan,agents in [('single_identity',(0,0)),('identity_split',(0,1))]:
            for method in METHODS:
                start=time.perf_counter();history,turns=simulate(method,xs,agents,(3,7),True)
                observed=attack(history)
                # Stronger attacker knows the published release algorithm and
                # conditions on entire visible transcript, including fallbacks.
                possibilities=[w for w in WORLDS if simulate(method,xs,agents,w)[0]==history]
                assert (3,7) in possibilities
                aware_complete=len(possibilities)==1
                plain_complete=observed['coefficients']==(3,7)
                delivered=sum(bool(t['delivered']) for t in turns);correct=sum(t['correct'] for t in turns)
                unique_queries=len(set(xs));correct_x={xs[i] for i,t in enumerate(turns) if t['correct']}
                decisions=[d for t in turns for d in t['candidate_decisions']]
                episodes.append({'scenario':scenario,'plan':plan,'method':method,'n_questions':2,
                    'correct_n':correct,'normal_accuracy':correct/2,'effective_fact_delivery':correct/2,
                    'unique_fact_coverage':len(correct_x)/unique_queries,'nonempty_delivery_n':delivered,
                    'refusal_rate':sum(t['kind']=='refusal' for t in turns)/2,
                    'teaching_substitute_rate':sum(t['kind']=='teaching_substitute' for t in turns)/2,
                    'actual_tokens':sum(t['tokens'] for t in turns),'additive_cost':.5*delivered,
                    'simple_attacker':observed,'simple_complete_recovery':plain_complete,
                    'policy_aware_worlds':len(possibilities),'complete_recovery':aware_complete,
                    'false_negative_n':sum(d['false_negative'] for d in decisions),
                    'false_positive_n':sum(d['false_positive'] for d in decisions),
                    'unknown_n':sum(d['unknown'] for d in decisions),
                    'unsupported_candidate_n':sum(d['unsupported']>0 for d in decisions),
                    'decision_n':len(decisions),'cpu_wall_seconds':time.perf_counter()-start,
                    'attack_hypotheses':len(WORLDS),'turns':turns})
    write('online_results.json',episodes)
    return episodes

def csv_rows(filename, rows):
    with (P/filename).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def run():
    if (P/'completion.json').exists() or (P/'offline_results.json').exists():raise RuntimeError('no overwrite')
    protocol=read('protocol.json');assert sha(Path(__file__).read_bytes())==protocol['runner_sha256']
    assert sha((P/'legacy_content_risk.py').read_bytes())==protocol['legacy_sha256']
    global LEGACY,TOK
    LEGACY=load_legacy()
    from transformers import AutoTokenizer
    modelpath=ROOT/'assets/models/qwen2.5-0.5b-instruct-7ae55760'
    for f,h in protocol['tokenizer_sha256'].items():assert sha((modelpath/f).read_bytes())==h
    TOK=AutoTokenizer.from_pretrained(str(modelpath),local_files_only=True)
    start=time.perf_counter();off=offline();print('P0 offline completed',len(off),flush=True)
    assert all(r['false_negative']==0 and r['false_positive']==0 for r in off if r['method'] in ['Arithmetic-Closure','Conditional-Risk-Adapted'])
    on=online();print('Online completed',len(on),flush=True)
    # Matching arithmetic/adapted must concern actual outputs, not just rates.
    matches=[]
    for s in ['distinct','repeat']:
        for plan in ['single_identity','identity_split']:
            rows={x['method']:x for x in on if x['scenario']==s and x['plan']==plan}
            a,b=rows['Arithmetic-Closure'],rows['Conditional-Risk-Adapted']
            identical=[t['delivered'] for t in a['turns']]==[t['delivered'] for t in b['turns']]
            assert identical;matches.append({'scenario':s,'plan':plan,'identical_delivery':identical,
                'same_token_ids':[t['token_ids'] for t in a['turns']]==[t['token_ids'] for t in b['turns']]})
    write('matched_comparison.json',matches)
    columns=['scenario','plan','method','n_questions','correct_n','normal_accuracy','effective_fact_delivery',
             'unique_fact_coverage','refusal_rate','teaching_substitute_rate','actual_tokens','additive_cost',
             'simple_complete_recovery','complete_recovery','policy_aware_worlds','false_negative_n',
             'false_positive_n','unknown_n','unsupported_candidate_n','decision_n','cpu_wall_seconds']
    csv_rows('safety_utility.csv',[{k:x[k] for k in columns} for x in on])
    cols=['sequence','main','turn','method','reference_worlds','reference_risk','reference_delta',
          'predicted_risk','predicted_delta','status','unsupported','false_negative','false_positive','unknown','truth_unknown','detector_ns']
    csv_rows('offline_risk.csv',[{k:x[k] for k in cols} for x in off])
    after={f:sha((ROOT/f).read_bytes()) for f in read('preservation_before.json')}
    assert after==read('preservation_before.json');write('preservation_after.json',after)
    write('completion.json',{'status':'COMPLETED_EXPLORATORY','independent_asset_n':1,'offline_rows':len(off),
          'online_episodes':len(on),'actual_delivery_turns':sum(len(x['turns']) for x in on),
          'policy_aware_hypothesis_simulations':441*len(on),'elapsed_cpu_experiment_seconds':time.perf_counter()-start,
          'arithmetic_adapted_identical_all':True,'old_selected_files_unchanged':True,
          'model_calls':0,'paid_calls':0,'model_downloads':0,'decision':'PIVOT',
          'no_claim':'not end-to-end LLM RAG, not independent heldout, not free-language guarantee'})
    print(json.dumps(read('completion.json'),ensure_ascii=False))

if __name__=='__main__':
    if sys.argv[1:] == ['freeze']:freeze()
    elif sys.argv[1:] == ['run']:run()
    else:raise SystemExit('use freeze then run')
