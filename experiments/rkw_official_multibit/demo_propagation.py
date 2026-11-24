import hashlib,json,urllib.request,time
from pathlib import Path
p=Path('experiments/rkw_official_multibit/results')
rows=[r for l in (p/'official_demo_predictions.jsonl').read_bytes().splitlines() if (r:=json.loads(l))['selected']]
url='http://127.0.0.1:11434'
def api(path,data=None):
 request=urllib.request.Request(url+path,data=json.dumps(data).encode() if data else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=240) as r:return json.load(r)
model='qwen2.5:0.5b-instruct'
assert next(x for x in api('/api/tags')['models'] if x['name']==model)['digest']=='a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67'
ops={'summary':'Summarize this passage in the same language in 2 or 3 sentences. Preserve technical metrics and numbers. Return only the summary.',
'rewrite':'Rewrite this passage in the same language as a different author. Use fresh wording, retain technical metrics and numbers, and do not summarize. Return only the rewrite.',
'merge':'Fuse these two passages in English into one concise technical explanation. Keep their shared numerical claims and technical metrics. Return only the result.'}
out=Path('var/icml-multibit/demo_propagation.jsonl')
with out.open('x',encoding='utf8',newline='\n') as stream:
 for op, instruction in ops.items():
  groups=[rows] if op=='merge' else [[r] for r in rows]
  for group in groups:
   for marked in (True,False):
    text='\n\n'.join(x['text' if marked else 'original'] for x in group)
    prompt=instruction+'\n\n'+text
    start=time.perf_counter()
    output=api('/api/generate',dict(model=model,prompt=prompt,stream=False,keep_alive=0 if op=='merge' and not marked else '4m',options=dict(seed=61127,temperature=0,num_ctx=3072,num_predict=512,num_gpu=0,num_thread=3)))
    record=dict(operation=op,marked=marked,samples=[r['sample'] for r in group],input=text,text=output['response'],model_digest=next(x for x in api('/api/tags')['models'] if x['name']==model)['digest'],prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),tokens=output.get('eval_count'),finish=output.get('done_reason'),seconds=time.perf_counter()-start)
    stream.write(json.dumps(record,ensure_ascii=False)+'\n');stream.flush();print(op,marked,record['seconds'],flush=True)
