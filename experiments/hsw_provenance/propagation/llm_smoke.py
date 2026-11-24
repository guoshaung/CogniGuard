"""Run two real local-LLM relay chains with source identities hidden from the model."""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from build import HERE, write

MODEL = "qwen2.5:7b-instruct"
HOP_PLAN = ("forward", "summary", "light_rewrite", "strong_rewrite", "truncate")
PROMPTS = {
    "forward": "Return the supplied text verbatim. Preserve each line and order. Give only the text.",
    "summary": "Summarize the supplied instructional text concisely. Keep representative findings from the different examples. Give only the summary.",
    "light_rewrite": "Lightly paraphrase the supplied instructional text. Keep its conditions, calculations and outcomes. Give only the rewritten text.",
    "strong_rewrite": "Rewrite the supplied instructional text for a beginner, with substantially different wording and order. Use only facts given in the text.",
    "truncate": "Retain only the opening half of the supplied text, stopping after a complete sentence. Return only that excerpt.",
}
GROUPS = (("physics-01",), ("math-01","physics-05","statistics-04"))
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(endpoint, route, payload=None):
    envelope = urllib.request.Request(
        f"{endpoint.rstrip('/')}{route}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type":"application/json"},
    )
    with OPENER.open(envelope, timeout=180) as response:
        return json.load(response)


def run(endpoint, model, out, layers):
    rows = json.loads((HERE/"releases.json").read_bytes())
    catalog = {row["source_id"]:row for row in rows if row["issuer_id"] == "issuer-a"}
    for row in rows:
        if row["issuer_id"] == "issuer-b" and row["source_id"] == "physics-05":
            catalog[row["source_id"]] = row
    available = call(endpoint,"/api/tags")["models"]
    model_row = next(row for row in available if row["name"] == model)
    config = dict(model=model,digest=model_row["digest"],steps=HOP_PLAN, groups=GROUPS,
                  sampling=dict(temperature=0, num_ctx=2048,num_predict=192), layers=layers,
                  paid_api_calls=0)
    write(out/"config.json",config)
    target = out/"hops.jsonl"
    cached = {}
    if target.exists():
        cached = {(row["chain_id"],row["hop"]):row for row in map(json.loads,target.read_text(encoding="utf8").splitlines())}
    for chain, batch in enumerate(GROUPS,1):
        text = "\n\n".join(catalog[sid]["text"] for sid in batch)
        releases = [catalog[sid]["release_id"] for sid in batch]
        for hop, action in enumerate(HOP_PLAN,1):
            if (chain,hop) in cached:
                text = cached[chain,hop]["text"]
                continue
            if action == "forward":
                result = dict(text=text, seconds=0.0, output_tokens=0,input_tokens=0,finish_reason="exact_relay")
            elif action == "truncate":
                # Actual character truncation followed by the previous complete line/sentence.
                cut = text[:len(text)//2]
                last = max(cut.rfind(". "),cut.rfind(".\n"))
                result = dict(text=text[:last+1] if last>=0 else cut, seconds=0.0, output_tokens=0,input_tokens=0,
                              finish_reason="deterministic_prefix_cut")
            else:
                start = time.perf_counter()
                result = call(endpoint, "/api/chat", dict(model=model,
                              messages=[dict(role="system",content=PROMPTS[action]),
                                        dict(role="user",content=text)],
                              stream=False,keep_alive="5m",
                              options=dict(**config["sampling"],num_gpu=layers,seed=112400+chain*10+hop)))
                result = dict(text=result["message"]["content"],seconds=time.perf_counter()-start,
                              output_tokens=result.get("eval_count"),input_tokens=result.get("prompt_eval_count"),
                              model_duration_seconds=(result.get("total_duration") or 0)/1e9,
                              model_load_seconds=(result.get("load_duration") or 0)/1e9,
                              finish_reason=result.get("done_reason"))
            row = dict(chain_id=chain,hop=hop,agent_id=f"relay-{hop}",transform=action,
                       input_source_ids=batch,input_release_ids=releases,
                       input_sha256=hashlib.sha256(text.encode()).hexdigest(),**result)
            with target.open("a",encoding="utf8",newline="\n") as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            text = result["text"]
            print(chain,hop,action,result["finish_reason"],round(result["seconds"],3),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint",default="http://127.0.0.1:11434")
    parser.add_argument("--model",default=MODEL)
    parser.add_argument("--out",type=Path,default=HERE/"model_smoke")
    parser.add_argument("--layers",type=int,default=0)
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    run(args.endpoint,args.model,args.out,args.layers)


if __name__ == "__main__":
    main()
