"""One source-only completion per frozen T6 question using the local GGUF."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, rank, sha, verify_prereg, write

PORT=11706
BASE=f"http://127.0.0.1:{PORT}"
MODEL=ROOT/"assets/models/hsw-t6-mistral-v03/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
SERVER=ROOT/"var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime/llama-server.exe"
LOCAL=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def hash_file(path):
    import hashlib
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


def request(path, payload=None, timeout=3):
    body=json.dumps(payload).encode() if payload is not None else None
    query=urllib.request.Request(BASE+path,data=body,headers={"Content-Type":"application/json"})
    with LOCAL.open(query,timeout=timeout) as response:
        return json.load(response)


def generate(source, prompt, records, outputs):
    identifier=source["id"]
    question=source["question"]
    assert sha(question.encode())==source["question_sha256"]
    attempt=records/(identifier+".attempt.json")
    assert not attempt.exists(),"Frozen no-repeat request already exists"
    body={
        "model":"t6-mistral",
        "messages":[{"role":"user","content":prompt+question}],
        "max_tokens":1024,"temperature":.7,"top_p":.9,"top_k":40,
        "repeat_penalty":1.,"seed":int(rank("generate",identifier)[:8],16)&0x7fffffff,
        "cache_prompt":False,"stream":False,
    }
    write(attempt,{"id":identifier,"input_sha256":source["question_sha256"],
                   "request_sha256":sha(json.dumps(body,ensure_ascii=False).encode()),
                   "seed":body["seed"],"timestamp":time.time()})
    start=time.monotonic()
    row={"id":identifier,"subject":source["subject"]}
    try:
        data=request("/v1/chat/completions",body,timeout=300)
        reply=data["choices"][0]
        text=reply["message"]["content"]
        (outputs/(identifier+".txt")).write_bytes(text.encode())
        row.update(status="COMPLETED",finish_reason=reply["finish_reason"],
                   format_pass=bool(text.strip()),output_sha256=sha(text.encode()),
                   output_tokens=data.get("usage",{}).get("completion_tokens"))
    except (OSError,ValueError,KeyError,IndexError,TypeError) as exc:
        row.update(status="FAILED",error=type(exc).__name__,http_status=getattr(exc,"code",None))
    row["seconds"]=time.monotonic()-start
    write(records/(identifier+".json"),row)
    return row


def main():
    freeze=verify_prereg()
    manifest_path=HERE/"T6_INPUT_MANIFEST.json"
    admission=load(HERE/"T6_GENERATION_FREEZE.json")
    assert admission["input_manifest_sha256"]==hash_file(manifest_path)
    raw=OUT/"sources.local.json"
    manifest=load(manifest_path)
    assert hash_file(raw)==manifest["local_input_sha256"]
    tasks=load(raw)
    assert len(tasks)==len(manifest["sources"])==200
    assert {row["id"]:row["question_sha256"] for row in tasks}=={
        row["id"]:row["question_sha256"] for row in manifest["sources"]}
    assert hash_file(MODEL)==freeze["gguf_sha256"]
    assert hash_file(SERVER)==admission["server_sha256"]
    work=OUT/"stage_b_generation"
    work.mkdir(exist_ok=False)
    records=work/"records"
    outputs=work/"outputs"
    records.mkdir()
    outputs.mkdir()
    env=os.environ.copy()
    env["PATH"]=str(SERVER.parent)+";C:/Users/guoshuang/AppData/Local/Programs/Ollama/lib/ollama/cuda_v12;"+env["PATH"]
    args=[str(SERVER),"-m",str(MODEL),"--alias","t6-mistral",
          "--host","127.0.0.1","--port",str(PORT),"-ngl","20","-fa","on",
          "--no-kv-unified","--parallel","2","--no-warmup","-b","512","-ub","128","-t","4","-c","6144"]
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",PORT))
    spawned=None
    results=[]
    with (work/"server.log").open("xb") as log:
        try:
            spawned=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            write(work/"START.json",{"server_pid":spawned.pid,"runner_pid":os.getpid(),"port":PORT,
                                     "timestamp":time.time(),"tasks":len(tasks),
                                     "generation_freeze_sha256":hash_file(HERE/"T6_GENERATION_FREEZE.json")})
            for _ in range(120):
                if spawned.poll() is not None:
                    raise RuntimeError("SERVER_EXITED")
                try:
                    if request("/health",timeout=1).get("status")=="ok":
                        break
                except (OSError,ValueError):
                    time.sleep(1)
            else:
                raise RuntimeError("SERVER_LOAD_TIMEOUT")
            write(work/"READY.json",{"server_pid":spawned.pid,"health":"ok","port":PORT})
            with ThreadPoolExecutor(max_workers=2) as pool:
                for i in range(0,len(tasks),2):
                    results.extend(pool.map(lambda row:generate(row,admission["prompt"],records,outputs),
                                            tasks[i:i+2]))
                    print("T6 source generation",len(results),"/",len(tasks),flush=True)
        finally:
            if spawned and spawned.poll() is None:
                spawned.terminate()
                try:
                    spawned.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    spawned.kill()
                    spawned.wait(timeout=10)
            write(work/"RESULT.json",{"planned":len(tasks),"attempted":len(results),"rows":results,
                                     "own_server_stopped":spawned is None or spawned.poll() is not None})


if __name__=="__main__":
    main()
