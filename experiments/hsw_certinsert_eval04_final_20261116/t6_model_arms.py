"""Run EVAL-03 rewrites on the committed T6 success union and one-shot compression."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from t6_sources import HERE, OUT, ROOT, load, rank, sha, write

EVAL = ROOT/"var/results/hsw-st/certinsert_eval_20261111_01/run01"
STUDY = OUT/"stage_d_model_arms"
KGW_SOURCE=ROOT.parents[1]/"CogniGuard/var/results/hsw_gpu0_deploy_20261102_r21"
OLD = ROOT/"var/results/hsw-st/english_replication_20261110_01/e1_guarded"
PORT=11707
LOCAL=urllib.request.build_opener(urllib.request.ProxyHandler({}))


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()


class Server:
    def __init__(self, model, path, folder, port=PORT, alias="t6-qwen"):
        self.base=f"http://127.0.0.1:{port}"
        self.log=(folder/"server.log").open("ab")
        self.worker=None
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1",port))
            env=os.environ.copy()
            env["PATH"]=str(Path(path).parent)+";C:/Users/guoshuang/AppData/Local/Programs/Ollama/lib/ollama/cuda_v12;"+env["PATH"]
            command=[str(path),"-m",str(model),"--alias",alias,"--host","127.0.0.1","--port",str(port),
                     "-ngl","20","-fa","on","--no-kv-unified","--parallel","2","--no-warmup","-b","512",
                     "-ub","128","-t","4","-c","8192"]
            self.worker=subprocess.Popen(command,env=env,stdout=self.log,stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            write(folder/f"SERVER_{self.worker.pid}.json",{"pid":self.worker.pid,"port":port,"started":time.time()})
            for _ in range(120):
                if self.worker.poll() is not None:
                    raise RuntimeError("SERVER_EXITED")
                try:
                    if self.request("/health",timeout=2)["status"]=="ok":
                        return
                except (OSError,ValueError,KeyError):
                    time.sleep(1)
            raise TimeoutError("SERVER_START_TIMEOUT")
        except BaseException:
            self.close()
            raise

    def request(self,path,payload=None,timeout=240):
        query=urllib.request.Request(self.base+path,data=json.dumps(payload,separators=(",",":")).encode() if payload else None,
                                     headers={"Content-Type":"application/json"})
        with LOCAL.open(query,timeout=timeout) as response:
            return json.load(response)

    def close(self):
        if self.worker and self.worker.poll() is None:
            self.worker.terminate()
            try:
                self.worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.worker.kill()
                self.worker.wait(timeout=10)
        self.log.close()


def prompt(prefix,text):
    return ("<|im_start|>system\nYou are a careful English science textbook editor.<|im_end|>\n"
            "<|im_start|>user\n"+prefix+"\n\n"+text+"<|im_end|>\n<|im_start|>assistant\n")


def finalize(folder, row, text, extra):
    if text:
        (folder/"outputs"/(row["id"]+".txt")).write_bytes(text.encode())
        row["output_sha256"]=sha(text.encode())
    write(folder/"records"/(row["id"]+".json"),{**row,**extra})
    return row


def tokenizer(server,text,parse=False):
    return server.request("/tokenize",{"content":text,"add_special":False,"parse_special":parse})["tokens"]


def attempt(folder, ident, seed, text, method, condition):
    existing=folder/"records"/(ident+".json")
    marker=folder/"records"/(ident+".attempt.json")
    if existing.exists():
        return load(existing)
    if marker.exists():
        return {"id":ident,"status":"INCOMPLETE_PREVIOUS_ATTEMPT","method":method,"condition":condition}
    write(marker,{"id":ident,"input_sha256":sha(text.encode()),"seed":seed,"timestamp":time.time()})
    return None


def ordinary(server, folder, ident, source_id, text, config_prompt, method, mode, green=None):
    key=ident+"__"+method if mode=="none" else ident+"__compress70"
    seed=int(rank(method+"_"+mode,key)[:8],16)&0x7fffffff
    prev=attempt(folder,key,seed,text,method,mode)
    if prev:
        return prev
    row={"id":key,"source_id":source_id,"method":method,"condition":mode,"status":"FAILED",
         "input_sha256":sha(text.encode())}
    body={"prompt":prompt(config_prompt,text),"n_predict":1024,"temperature":.7 if green is None else 0.,
          "top_p":.9,"top_k":40,"repeat_penalty":1.,"seed":seed,"cache_prompt":False,
          "stream":False,"return_tokens":True,"id_slot":1}
    if green is not None:
        body["logit_bias"]=[[i,2.] for i in green]
    output=None
    try:
        data=server.request("/completion",body)
        output=data["content"]
        row.update(status="COMPLETED" if output.strip() else "EMPTY",finish_reason=data.get("stop_type"),
                   output_tokens=data.get("tokens_predicted"))
        if green is not None:
            echo=data.get("generation_settings",{}).get("logit_bias")
            row["bias_echo_matches"]=echo==body["logit_bias"] if echo is not None else None
    except (OSError,KeyError,ValueError,TypeError) as exc:
        row["failure"]=type(exc).__name__
    return finalize(folder,row,output,{})


def kgw(server, folder, task, source, rewrite, private_key):
    from kgw_ref.kgw import Greenlist
    ident=task+"__KGW"
    cached=attempt(folder,ident,None,source,"KGW","none")
    if cached:
        return cached
    prf=Greenlist(private_key)
    row={"id":ident,"source_id":task,"method":"KGW","condition":"none","status":"FAILED",
         "input_sha256":sha(source.encode()),"key_sha256":prf.key_sha256}
    output=None
    chosen=[]
    fingerprints=hashlib.sha256()
    try:
        history=tokenizer(server,prompt(rewrite,source),True)
        for _ in range(1024):
            indices=prf.indices(history)
            fingerprints.update(indices.astype("<u4").tobytes())
            payload={"prompt":history,"n_predict":1,"temperature":0.,"repeat_penalty":1.,
                     "cache_prompt":True,"stream":False,"return_tokens":True,"id_slot":0,
                     "logit_bias":[[int(i),4.] for i in indices]}
            result=server.request("/completion",payload,90)
            tokens=result.get("tokens",[])
            if not tokens and result.get("stop_type")=="eos":
                row["finish_reason"]="eos"
                break
            if len(tokens)!=1 or not isinstance(tokens[0],int):
                raise ValueError("ONE_TOKEN_RESPONSE_INVALID")
            token=tokens[0]
            if token in (151643,151645):
                row["finish_reason"]="eos"
                break
            chosen.append(token)
            history.append(token)
            if result.get("stop_type")=="eos":
                row["finish_reason"]="eos"
                break
        else:
            row["finish_reason"]="length"
        output=server.request("/detokenize",{"tokens":chosen})["content"] if chosen else ""
        row.update(status="COMPLETED" if output.strip() else "EMPTY",output_tokens=len(chosen),
                   retokenized_equal=tokenizer(server,output)==chosen)
    except (OSError,KeyError,ValueError,TypeError) as exc:
        row.update(failure=type(exc).__name__,output_tokens=len(chosen))
    return finalize(folder,row,output,{"green_history_sha256":fingerprints.hexdigest()})


def configure():
    freeze=load(HERE/"T6_MODEL_ARMS_FREEZE.json")
    for path,digest in freeze["files_sha256"].items():
        assert file_hash(ROOT/path)==digest,path
    config=load(EVAL/"EVAL_FREEZE.json")
    for name,digest in config["model7b_parts"].items():
        assert file_hash(Path(config["model7b"]).parent/name)==digest
    assert file_hash(config["server"])==config["server_sha256"]
    return freeze,config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("baseline","compress"))
    args=parser.parse_args()
    freeze,config=configure()
    stage=args.stage
    folder=STUDY/stage
    (folder/"outputs").mkdir(exist_ok=True,parents=True)
    (folder/"records").mkdir(exist_ok=True)
    server=Server(config["model7b"],config["server"],folder)
    results=[]
    try:
        if stage=="baseline":
            sys.path.insert(0,str(KGW_SOURCE))
            key=(OLD/"frozen_comparison09/restricted/kgw_key.txt").read_text(encoding="utf-8")
            green=load(EVAL/"restricted/UNIGRAM_GREEN.json")
            assert sha(key.encode())==freeze["kgw_key_sha256"]
            union=load(HERE/"T6_BASELINE_UNION.json")["sources"]
            sources=OUT/"stage_b_generation/outputs"
            def run(method):
                ret=[]
                for task in union:
                    ident=task["id"]
                    data=(sources/(ident+".txt")).read_bytes()
                    assert sha(data)==task["source_output_sha256"]
                    text=data.decode()
                    item=(kgw(server,folder,ident,text,config["rewrite_prompt"],key) if method=="KGW"
                          else ordinary(server,folder,ident,ident,text,config["rewrite_prompt"],method,"none",green))
                    ret.append(item)
                    print(method,len(ret),len(union),item["status"],flush=True)
                return ret
            with ThreadPoolExecutor(max_workers=2) as pool:
                for group in pool.map(run,("KGW","Unigram")):
                    results.extend(group)
        else:
            brief=config["attacks"]["concise"].format(ratio=70)
            tasks=load(OUT/"score_registry.json")["items"]
            registry_hash=load(HERE/"T6_VARIANT_FREEZE.json")["registry_sha256"]
            assert file_hash(OUT/"score_registry.json")==registry_hash
            for job in tasks:
                text=(ROOT/job["path"]).read_bytes()
                assert sha(text)==job["sha256"]
                results.append(ordinary(server,folder,job["record_id"],job["id"],text.decode(),brief,
                                        job["method"],"compress70"))
                if len(results)%10==0:print("compression",len(results),len(tasks),flush=True)
    finally:
        server.close()
    write(folder/"RESULT.json",{"results":results,"statuses":dict(Counter(r["status"] for r in results)),
                                "count":len(results),"server_stopped":True})


if __name__=="__main__":
    main()
