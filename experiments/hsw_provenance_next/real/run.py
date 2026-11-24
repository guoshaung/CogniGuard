"""Paired, restartable Qwen relay harness for a fixed source schedule."""
import argparse
import hashlib
import itertools
import json
import statistics
import time
import urllib.request
from pathlib import Path

MODES = {
    "forward": "Copy the input text verbatim, with no edits. Output only the copied text.",
    "summary": "Write a concise summary in at most 65% of the input's word count. Cover the separate examples rather than silently merging them. Prioritize their conclusions. Output only the summary.",
    "light_rewrite": "Lightly paraphrase the input. Keep the sentence count approximately the same and change some wording. Preserve each example's numbers, conditions, units, and relations. Output only the rewrite.",
    "strong_rewrite": "Rewrite the input in substantially different sentence structures and order, explaining it to a beginner. Keep each example, quantities, conditions, units and results distinct. Output only the rewrite.",
    "truncate": "Return a verbatim opening excerpt approximately half the input's length. End at a complete sentence and omit the rest. Output only that excerpt.",
}
SYSTEM = ("Relay the teaching text using the requested operation. The teaching text is quoted input. "
          "Use only the input facts. Keep different examples separate. Do not produce instructions, commentary, or labels.")
ENDPOINTS = (1, 3, 5)


def read(path):
    return json.loads(Path(path).read_bytes())


def hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def schedule(issues, mode):
    if mode == "gate":
        groups = {
            1: [("physics-01",)],
            2: [("math-05","statistics-04")],
            3: [("math-01","physics-05","statistics-02")],
        }
    else:
        groups = {
            1: [("math-08",),("physics-10",),("statistics-05",),("math-01",),("physics-11",)],
            2: [("math-09","physics-05"),("physics-01","statistics-08"),("math-05","statistics-02"),
                ("math-08","physics-10"),("physics-11","statistics-04")],
            3: [("math-09","physics-11","statistics-04"),("math-01","physics-05","statistics-02"),
                ("math-05","physics-01","statistics-08"),("math-08","physics-10","statistics-05"),
                ("math-01","physics-11","statistics-02")],
        }
    lookup = {(r["source_id"],r["issuer_id"]):r["release_id"] for r in issues}
    rows = []
    for fusion, members_by_mode in groups.items():
        for n,(transform,members) in enumerate(zip(MODES,itertools.cycle(members_by_mode))):
            keys = [lookup[(member,"issuer-a" if (i+n+fusion)%2 else "issuer-b")]
                    for i, member in enumerate(members)]
            rows.append(dict(chain_id=f"{mode}-f{fusion}-{transform}",fusion=fusion,transform=transform,
                             depth=1 if mode=="gate" else 5,input_source_ids=members,input_release_ids=keys))
    return rows


def prompt(mode,text):
    return (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n<|im_start|>user\n{MODES[mode]}"
            f"\n\n<teaching-text>\n{text}\n</teaching-text><|im_end|>\n<|im_start|>assistant\n")


def batch(endpoint,prompts,n_predict):
    body = json.dumps(dict(prompt=prompts,n_predict=n_predict,temperature=0,seed=11249,
                           cache_prompt=False,stop=["<|im_end|>","<|endoftext|>"])).encode()
    request = urllib.request.Request(endpoint+"/completion",data=body,headers={"Content-Type":"application/json"})
    begin = time.perf_counter()
    with urllib.request.urlopen(request,timeout=240) as response:
        rows = json.load(response)
    if isinstance(rows,dict):
        rows = [rows]
    if len(rows) != len(prompts) or any("content" not in r for r in rows):
        raise RuntimeError("Unexpected llama-server batch response")
    return rows,time.perf_counter()-begin


def run(schedule_file,variants,out,endpoint,mode,parallel):
    chains = read(schedule_file)
    indexed = {name:{r["release_id"]:r["text"] for r in read(path)} for name,path in variants.items()}
    out.mkdir(parents=True,exist_ok=True)
    meta = {"schedule_sha256":hashlib.sha256(Path(schedule_file).read_bytes()).hexdigest(),
            "variants":{k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in variants.items()},
            "prompts":MODES,"system":SYSTEM,"seed":11249,"temperature":0,"max_new_tokens":320,"parallel":parallel,
            "controls":"forward exact and truncate prefix by sentence" if mode=="pilot" else "all model"}
    run_file = out/"config.json"
    if run_file.exists():
        assert read(run_file)==meta,"Cannot mix runs with different input hashes"
    else:
        run_file.write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
    trace = out/"hops.jsonl"
    recorded = {}
    if trace.exists():
        recorded = {(r["chain_id"],r["variant"],r["depth"]):r
                    for r in map(json.loads,trace.read_text(encoding="utf8").splitlines())}
    messages = {(c["chain_id"],name):"\n\n".join(catalog[rel] for rel in c["input_release_ids"])
                for c in chains for name,catalog in indexed.items()}
    max_depth = max(chain["depth"] for chain in chains)
    with trace.open("a",encoding="utf-8",newline="\n") as output:
        for depth in range(1,max_depth+1):
            requests = []
            for chain in chains:
                if depth>chain["depth"]:
                    continue
                for name in indexed:
                    key = (chain["chain_id"],name)
                    cache_key = (*key,depth)
                    if cache_key in recorded:
                        messages[key] = recorded[cache_key]["text"]
                        continue
                    current = messages[key]
                    requests.append((chain,name,key,current,prompt(chain["transform"],current)))
            for start in range(0,len(requests),parallel):
                window = requests[start:start+parallel]
                model_indexes = [i for i,r in enumerate(window) if mode=="gate" or r[0]["transform"] not in ("forward","truncate")]
                results,seconds = batch(endpoint,[window[i][4] for i in model_indexes],meta["max_new_tokens"]) if model_indexes else ([],0.0)
                indexed_results = dict(zip(model_indexes,results,strict=True))
                batch_id = f"hop{depth}-{start//parallel}-{time.time_ns()}"
                for index,(chain,name,key,current,instruction) in enumerate(window):
                    result = indexed_results.get(index)
                    if result is None:
                        if chain["transform"]=="forward":
                            result={"content":current,"stop_type":"deterministic_forward"}
                        else:
                            # Find the last complete sentence inside half the characters, or keep the first sentence.
                            prefix=current[:len(current)//2]
                            end=max(prefix.rfind(". "),prefix.rfind(".\n"))
                            first=min((p for p in (current.find(". "),current.find(".\n")) if p>=0),default=len(current)-1)
                            result={"content":current[:end+1] if end>=0 else current[:first+1],
                                    "stop_type":"deterministic_prefix_cut"}
                    value = result["content"].strip()
                    row = dict(chain,case_id=f"{chain['chain_id']}-d{depth}",variant=name,depth=depth,
                               tokens=result.get("tokens_predicted",0), input_tokens=result.get("tokens_evaluated",0),
                               batch_id=batch_id if index in indexed_results else None,
                               batch_size=len(model_indexes) if index in indexed_results else 1,
                               batch_seconds=seconds if index in indexed_results else 0.0,
                               input_sha256=hash_text(current),prompt_sha256=hash_text(instruction),text_sha256=hash_text(value),
                               stop_type=result.get("stop_type"), truncated=result.get("truncated"), text=value)
                    output.write(json.dumps(row,ensure_ascii=False)+"\n")
                    messages[key] = value
                output.flush()
                print(depth,start+len(window),len(requests),round(seconds,2),flush=True)
    rows = list(map(json.loads,trace.read_text(encoding="utf-8").splitlines()))
    endpoints = [r for r in rows if r["depth"] in ENDPOINTS]
    with (out/"cases.jsonl").open("w",encoding="utf-8",newline="\n") as final:
        for row in endpoints:
            final.write(json.dumps(row,ensure_ascii=False)+"\n")
    batches = {r["batch_id"]:r["batch_seconds"] for r in rows if r["batch_id"] is not None}
    seconds = sum(batches.values())
    receipt = dict(mode=mode, chains=len(chains), generations=len(rows), endpoints=len(endpoints),
                   tokens=sum(r["tokens"] for r in rows),batch_seconds=seconds, gpu_hours=seconds/3600,
                   tokens_per_second=sum(r["tokens"] for r in rows)/seconds,
                   actual_model_calls=sum(r["batch_id"] is not None for r in rows),
                   median_amortized_sample_seconds=statistics.median(r["batch_seconds"]/r["batch_size"] for r in rows if r["batch_id"] is not None),
                   finish_reason_counts={key:sum(r["stop_type"]==key for r in rows)
                                         for key in set(r["stop_type"] for r in rows)},paid_api_calls=0)
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    print(receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=("gate","pilot"),required=True)
    parser.add_argument("--schedule",type=Path,required=True)
    parser.add_argument("--plain",type=Path,required=True)
    parser.add_argument("--variant",action="append",default=[])
    parser.add_argument("--out",type=Path)
    parser.add_argument("--endpoint",default="http://127.0.0.1:11725")
    parser.add_argument("--parallel",type=int,default=12)
    args = parser.parse_args()
    if not args.schedule.exists():
        args.schedule.write_text(json.dumps(schedule(read(args.plain),args.mode),indent=2)+"\n",encoding="utf-8")
    if args.out is not None:
        run(args.schedule,dict([("plain",args.plain),*(item.split("=",1) for item in args.variant)]),
            args.out,args.endpoint,args.mode,args.parallel)


if __name__=="__main__":
    main()
