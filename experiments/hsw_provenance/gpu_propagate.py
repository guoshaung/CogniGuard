"""Paired, batched model propagation smoke. Outputs are retained for review."""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path


TRANSFORMS = {
    "forward": "Copy this text verbatim.",
    "summary": "Summarize the main facts concisely.",
    "light": "Change wording lightly. Preserve calculations, units and assumptions.",
    "strong": "Rewrite the explanation using different sentence structure and vocabulary. Preserve factual meaning.",
    "truncate": "Return only roughly the first half of the explanation."
}


def standard_run(model, tokenizer, batch, count):
    import torch
    encoded = tokenizer(batch, return_tensors="pt", padding=True).to("cuda")
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(**encoded, max_new_tokens=count, do_sample=False,
                                pad_token_id=tokenizer.pad_token_id)
    torch.cuda.synchronize()
    suffix = output[:, encoded.input_ids.shape[1]:]
    valid = suffix.ne(tokenizer.pad_token_id).sum(dim=1).tolist()
    return tokenizer.batch_decode(suffix, skip_special_tokens=True), valid, time.perf_counter() - start


def server_run(endpoint, batch, count):
    body = json.dumps(dict(prompt=batch,n_predict=count,temperature=0,seed=1124,cache_prompt=False)).encode()
    request = urllib.request.Request(endpoint+"/completion",data=body,headers={"Content-Type":"application/json"})
    begin = time.perf_counter()
    with urllib.request.urlopen(request,timeout=180) as connection:
        rows = json.load(connection)
    if isinstance(rows,dict):
        rows = [rows]
    return [r["content"] for r in rows],[r["tokens_predicted"] for r in rows],time.perf_counter()-begin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path)
    parser.add_argument("--endpoint")
    parser.add_argument("--marked", type=Path, required=True)
    parser.add_argument("--plain", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=("smoke", "pilot"), required=True)
    args = parser.parse_args()
    issues = json.loads(args.plain.read_bytes())
    marked = {r["release_id"]:r["text"] for r in json.loads(args.marked.read_bytes())}
    started = time.perf_counter()
    if not args.endpoint:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.manual_seed(1124)
        torch.cuda.reset_peak_memory_stats()
        tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True, padding_side="left")
        tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
                                                     torch_dtype=torch.bfloat16).eval().to("cuda")
    run_seconds = 0.
    rows = []
    transforms = ("light",) if args.mode=="smoke" else tuple(TRANSFORMS)
    enabled_fusions = (2,) if args.mode=="smoke" else (1,2,3)
    depth = 1 if args.mode=="smoke" else 5
    for fusion in enabled_fusions:
        # Pair adjacent issuer variants; use distinct sources in each fusion.
        members = [issues[2*i+(i+fusion)%2] for i in range(fusion)]
        for transform in transforms:
            current = ["\n".join(member["text"] if variant=="plain" else marked[member["release_id"]]
                                  for member in members) for variant in ("plain","marked")]
            for hop in range(1,depth+1):
                if args.endpoint:
                    prompts = ["<|im_start|>system\nYou relay teaching material. Output only the requested text."
                               "<|im_end|>\n<|im_start|>user\n"+TRANSFORMS[transform]+"\n\n"+content+
                               "<|im_end|>\n<|im_start|>assistant\n" for content in current]
                    outputs, counts, seconds = server_run(args.endpoint,prompts,320)
                else:
                    prompts = [tokenizer.apply_chat_template([
                    {"role":"system","content":"You relay teaching material to another agent. Output only the requested text."},
                    {"role":"user","content":TRANSFORMS[transform]+"\n\n"+content}],
                    tokenize=False,add_generation_prompt=True) for content in current]
                    outputs, counts, seconds = standard_run(model,tokenizer,prompts,320)
                run_seconds += seconds
                for variant,prev,result,tokens in zip(("plain","marked"),current,outputs,counts,strict=True):
                    rows.append(dict(fusion=fusion,transform=transform,hop=hop,variant=variant,text=result,
                                     input_sha256=hashlib.sha256(prev.encode()).hexdigest(),tokens=tokens,
                                     batch_seconds=seconds,batch_size=2,input_source_ids=[m["source_id"] for m in members],
                                     input_release_ids=[m["release_id"] for m in members]))
                current = outputs
    receipt = dict(mode=args.mode, device=torch.cuda.get_device_name() if not args.endpoint else None,
                   backend="llama.cpp" if args.endpoint else str(torch.__version__),
                   generation_seconds=run_seconds, gpu_hours_generation=run_seconds/3600,
                   process_wall_seconds=time.perf_counter()-started,
                   peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20 if not args.endpoint else None,
                   tokens=sum(row["tokens"] for row in rows), samples=len(rows),
                   paid_api_calls=0, rows=rows)
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print({k:v for k,v in receipt.items() if k!="rows"},flush=True)


if __name__=="__main__":
    main()
