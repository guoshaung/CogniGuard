"""Generate exactly 300 frozen R teaching texts using the unchanged T5 backend."""
import concurrent.futures
import hashlib
import json
import sys
import time
from pathlib import Path

W=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
O=W/'var/results/hsw-st/certinsert_eval04_20261113/stage0'
D=O/'generation'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def put(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)


def rank(purpose,ident):
    return hashlib.sha256(('EVAL04v3|'+purpose+'|'+ident).encode()).hexdigest()


def prepare():
    questions=read(O/'R_GENERATION_QUESTIONS.json')
    # Deterministic subject round robin, never conditional on model outcomes.
    pools={s:sorted([x for x in questions if x['subject']==s],key=lambda x:rank('R_question',x['id']))
           for s in sorted({x['subject'] for x in questions})}
    selected=[]
    while len(selected)<300:
        for subject,pool in pools.items():
            if pool and len(selected)<300:
                selected.append(pool.pop(0))
        if not any(pools.values()) and len(selected)<300:
            raise RuntimeError('Insufficient question candidates')
    put(E/'R_GENERATION_INPUTS.json',selected)
    f=read(W/'var/results/hsw-st/certinsert_eval_20261111_01/run01/EVAL_FREEZE.json')
    f['T3_prompt']=read(W/'experiments/hsw_certinsert_eval03_lite_20261112/EVAL_FREEZE.json')['prompts']['T3_prompt']
    put(E/'R_GENERATION_FREEZE.json',dict(n=300,inputs_sha256=hashlib.sha256((E/'R_GENERATION_INPUTS.json').read_bytes()).hexdigest(),
        model=f['model7b'],parts=f['model7b_parts'],server=f['server'],server_sha256=f['server_sha256'],
        prompt=f['T3_prompt'],generation=f['generation'],seed_rule='SHA256(EVAL04v3|R_generation|id) first32bits & 0x7fffffff',
        slot_count=2,stage_seconds=21600,no_retry=True,format='same EVAL03 parser; no repair',
        corpus_split='SHA256(EVAL04v3|R_split|document_id), sorted first floor(.8*N) build; rest calib after all generation succeeds'))


def run():
    D.mkdir(exist_ok=False)
    for name in ['records','outputs']:
        (D/name).mkdir()
    sys.path.insert(0,str(W/'experiments/hsw_certinsert_eval_20261111_01'))
    import runtime7b as rt
    f=read(W/'var/results/hsw-st/certinsert_eval_20261111_01/run01/EVAL_FREEZE.json')
    freeze=read(E/'R_GENERATION_FREEZE.json')
    f['T3_prompt']=freeze['prompt']
    put(D/'EVAL_FREEZE.json',f)
    for name,digest in freeze['parts'].items():
        assert hashlib.sha256((Path(f['model7b']).parent/name).read_bytes()).hexdigest()==digest
    rt.O=D
    def log(name,row):
        with (D/name).open('a',encoding='utf8') as handle:
            handle.write(json.dumps(row)+'\n')
    rt.failure=lambda ident,reason:log('FAILURES.jsonl',dict(id=ident,error=reason))
    rt.checkpoint=lambda stage,**kw:log('CHECKPOINTS.jsonl',dict(stage=stage,**kw))
    rows=[];server=None
    try:
        server=rt.Server('R_GENERATION',21600)
        tasks=read(E/'R_GENERATION_INPUTS.json')
        def generate(pair):
            index,source=pair
            row=server.complete('R__'+source['id'],f['T3_prompt'],source['text'],
                int(rank('R_generation',source['id'])[:8],16)&0x7fffffff,dict(id_slot=index%2))
            row['source_id']=source['id']
            return row
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for index in range(0,300,2):
                if time.monotonic()>=server.end:
                    raise TimeoutError('R_GENERATION_BUDGET')
                pair=list(pool.map(generate,enumerate(tasks[index:index+2],start=index)))
                rows.extend(pair)
                print('R_GENERATION',len(rows),'/300',flush=True)
                if any(r['status']!='COMPLETED' for r in pair):
                    raise RuntimeError('Generation failure; stop without substitution')
    finally:
        if server:
            server.stop()
        put(D/'RESULT.json',dict(planned=300,attempted=len(rows),rows=rows,
            not_run=300-len(rows),paid_API=0,own_server_stopped=True))


if __name__=='__main__':
    if sys.argv[1]=='prepare':
        prepare()
    else:
        run()
