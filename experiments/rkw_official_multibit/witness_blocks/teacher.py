import json,urllib.request,time
from pathlib import Path
p=Path("experiments/rkw_official_multibit/witness_blocks")
facts={"rectangle":["A rectangle has length 9 m and width 4 m.","Its area is 36 square meters by multiplying length and width.","Its perimeter is 26 meters, twice the sum of length and width."],"speed":["A cyclist covers 120 m in 20 seconds.","The average speed is 6 meters per second because distance is divided by elapsed time.","The speed at any particular instant cannot be inferred from distance and total elapsed time alone."]}
def generate(model,prompt,seed,max_tokens=768):
    payload=dict(model=model,prompt=prompt,stream=False,options=dict(seed=seed,temperature=0,num_predict=max_tokens,num_ctx=3072))
    started=time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"}),timeout=300) as response:
        data=json.load(response)
    return dict(text=data["response"],finish=data.get("done_reason"),tokens=data.get("eval_count"),seconds=time.perf_counter()-started)
if __name__=="__main__":
    import sys
    out=Path(sys.argv[1])
    with out.open("x",encoding="utf8") as stream:
        for topic,units in facts.items():
            for position,fact in enumerate(units):
                prompt=f"Write one standalone English teaching paragraph of exactly four sentences based on this fact: {fact} Preserve the exact quantities and units. Explain the terms without introducing other numerical results. Output only the paragraph. Do not use abbreviations with a period."
                row=dict(topic=topic,position=position,fact=fact,prompt=prompt,**generate("qwen2.5:7b-instruct",prompt,61129))
                stream.write(json.dumps(row)+"\n")
                stream.flush()

