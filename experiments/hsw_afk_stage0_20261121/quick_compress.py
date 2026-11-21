"""Two sequential local compressors, exact frozen C1 adapter, no relay calls."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'var/results/hsw-st/afk_stage0_20261121'
sys.path.insert(0,str(ROOT/'experiments/hsw_certinsert_eval04_final_20261116'))
from t6_model_arms import Server, ordinary, file_hash


def read(p):return json.loads(p.read_bytes())
def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf8') as handle:json.dump(data,handle,ensure_ascii=False,indent=2)


def jobs():
    rows=read(OUT/'QUICK_SCENARIOS.json');tasks=[]
    for row in rows:
        for scenario in row['scenarios']:
            if scenario['kind']!='variant' and scenario['status']!='READY':continue
            tasks.append(dict(id=row['id']+'__'+scenario['kind'],source_id=row['id'],
                              text=scenario['text'],kind=scenario['kind']))
    return tasks


def freeze():
    f=read(ROOT/'var/results/hsw-st/certinsert_eval_20261111_01/run01/EVAL_FREEZE.json')
    for n,h in f['model7b_parts'].items():assert file_hash(Path(f['model7b']).parent/n)==h
    assert file_hash(f['server'])==f['server_sha256']
    tags=requests.get('http://127.0.0.1:11434/api/tags',timeout=20).json()['models']
    c2=next(m for m in tags if m['name']=='llama3.1:8b')
    show=requests.post('http://127.0.0.1:11434/api/show',json={'model':'llama3.1:8b'},timeout=20).json()
    assert show['details']['family']=='llama'
    prompt=f['attacks']['concise'].format(ratio=70)
    tasks=jobs()
    write(HERE/'COMPRESSOR_FREEZE.json',dict(status='BEFORE_QUICK_COMPRESSION',C1=dict(
        model=f['model7b'],parts=f['model7b_parts'],server=f['server'],server_sha256=f['server_sha256'],
        imported_adapter='experiments/hsw_certinsert_eval04_final_20261116/t6_model_arms.py',
        adapter_sha256=file_hash(ROOT/'experiments/hsw_certinsert_eval04_final_20261116/t6_model_arms.py')),
        C2=dict(model='llama3.1:8b',digest=c2['digest'],details=c2['details'],
            ollama_version=requests.get('http://127.0.0.1:11434/api/version',timeout=20).json()),
        prompt=prompt,temperature=.7,top_p=.9,top_k=40,repeat_penalty=1,max_new_tokens=1024,
        tasks=len(tasks),planned_per_compressor=len(tasks),paid_API=0,
        scenarios_sha256=file_hash(OUT/'QUICK_SCENARIOS.json'),
        code_sha256={p.name:file_hash(p) for p in HERE.glob('*.py')}))
    print('Frozen compressors and',len(tasks),'tasks each',flush=True)


def run():
    f=read(HERE/'COMPRESSOR_FREEZE.json')
    assert file_hash(OUT/'QUICK_SCENARIOS.json')==f['scenarios_sha256']
    for n,h in f['code_sha256'].items():assert file_hash(HERE/n)==h,n
    for n in ['A0_PREREG.md','VARIANT_TABLE.md']:
        import subprocess
        content=subprocess.check_output(['git','-C',str(ROOT),'show','HEAD:experiments/'+HERE.name+'/'+n])
        assert content== (HERE/n).read_bytes(),n
    tasks=jobs()
    for compressor in ['C1','C2']:
        folder=OUT/'quick_compression'/compressor
        if (folder/'RESULT.json').exists():continue
        for d in ['records','outputs']:(folder/d).mkdir(parents=True,exist_ok=True)
        results=[];server=None
        if compressor=='C1':
            server=Server(f['C1']['model'],f['C1']['server'],folder,port=11717,alias='afk-local-c1')
        try:
            for i,task in enumerate(tasks,1):
                if compressor=='C1':
                    row=ordinary(server,folder,task['id'],task['source_id'],task['text'],
                                 f['prompt'],'AFK_A0','compress70')
                else:
                    path=folder/'records'/(task['id']+'.json')
                    if path.exists():row=read(path)
                    else:
                        marker=folder/'records'/(task['id']+'.started.json')
                        if marker.exists():
                            row=dict(id=task['id'],status='INCOMPLETE_PREVIOUS_ATTEMPT')
                        else:
                            sd=int(hashlib.sha256(('AFK-A0-20261121|C2|'+task['id']).encode()).hexdigest()[:8],16)&0x7fffffff
                            write(marker,dict(seed=sd,input_sha256=hashlib.sha256(task['text'].encode()).hexdigest()))
                            tick=time.monotonic()
                            try:
                                response=requests.post('http://127.0.0.1:11434/api/chat',json=dict(
                                    model='llama3.1:8b',stream=False,keep_alive='10m',messages=[
                                      dict(role='system',content='You are a careful English science textbook editor.'),
                                      dict(role='user',content=f['prompt']+'\n\n'+task['text'])],
                                    options=dict(temperature=.7,top_p=.9,top_k=40,repeat_penalty=1.,
                                                 num_predict=1024,seed=sd)),timeout=300)
                                response.raise_for_status();body=response.json();text=body['message']['content']
                                output=folder/'outputs'/(task['id']+'.txt');output.write_text(text,encoding='utf8')
                                row=dict(id=task['id'],status='COMPLETED' if text.strip() else 'EMPTY',
                                    seed=sd,seconds=time.monotonic()-tick,model=body.get('model'),
                                    finish_reason=body.get('done_reason'),output_tokens=body.get('eval_count'),
                                    output_sha256=file_hash(output))
                            except Exception as error:row=dict(id=task['id'],status='FAILED',error=type(error).__name__)
                            write(path,row)
                results.append(dict(**row,scenario_id=task['id'],kind=task['kind']))
                print(compressor,i,'/',len(tasks),task['kind'],row['status'],flush=True)
                if row['status']!='COMPLETED':raise RuntimeError('Compression failed; no substitute/retry')
        finally:
            if server:server.close()
            elif compressor=='C2':requests.post('http://127.0.0.1:11434/api/generate',
                json=dict(model='llama3.1:8b',keep_alive=0),timeout=60)
        write(folder/'RESULT.json',dict(planned=len(tasks),results=results,paid_API=0))


if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    else:run()
