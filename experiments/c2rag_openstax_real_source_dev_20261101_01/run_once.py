"""One bounded local RAG generation and existing-schema incremental baseline run."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false")
from core.paths import RESULTS_DIR
from protection.common.schemas import TeacherResource
from protection.teacher_resource.src.c2rag.resource_index import ResourceIndex

R = RESULTS_DIR / "c2rag_openstax_real_source_dev_20261101_01"


def read(name):
    return json.loads((R/name).read_text(encoding="utf-8"))


def save(name, obj):
    p = R/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def shaf(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(8*1024**2), b""):
            h.update(block)
    return h.hexdigest()


def parsed(content):
    # No content repair or retries; only accept a JSON value with optional Markdown fence.
    s = content.strip()
    if s.startswith("```json") and s.endswith("```"):
        s = s[7:-3].strip()
    elif s.startswith("```") and s.endswith("```"):
        s = s[3:-3].strip()
    try:
        value = json.loads(s)
        return value if isinstance(value, dict) else None
    except (ValueError, TypeError):
        return None


def main():
    assert not (R/"RUN_STARTED.json").exists(), "NO_SECOND_MAIN_RUN"
    entry = time.time()
    config, prompts = read("RUNTIME.json"), read("PROMPTS.json")
    model_deadline = config["deadline_epoch"]-300
    assert time.time() < model_deadline
    for row in read("FREEZE_MANIFEST.json")["files"]:
        expected = row["sha256"]
        if Path(row["path"]).resolve() == Path(__file__).resolve() and (R/"ENGINEERING_CODE_LOCK.json").exists():
            repair = read("ENGINEERING_CODE_LOCK.json")
            assert repair["generation_calls_before_repair"] == 0
            assert expected == repair["original_sha256"]
            expected = repair["repaired_sha256"]
        assert shaf(row["path"]) == expected, ("FREEZE_CHANGED", row["path"])
    save("RUN_STARTED.json", {"epoch":entry,"model_deadline_epoch":model_deadline,"max_calls":24,"retries":0})
    controls, calls, transcript, evaluations = [], [], [], []
    server = None
    error = None
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    port = config["port"]

    def request(route, body=None, timeout=15):
        req = urllib.request.Request("http://127.0.0.1:"+str(port)+route,
                                     data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
                                     headers={"Content-Type":"application/json"})
        try:
            with http.open(req, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as ex:
            save("HTTP_CONTROL_FAILURE.json",{"route":route,"status":ex.code,"body":ex.read().decode("utf-8",errors="replace")})
            raise

    def call(name, messages, max_tokens):
        if time.time() >= model_deadline or len(calls) >= 24:
            raise TimeoutError("FROZEN_GENERATION_WINDOW_OR_CALL_CAP")
        request("/slots/0?action=erase", {})
        surface = request("/apply-template", {"messages":messages})["prompt"]
        tokenized = request("/tokenize", {"content":surface,"add_special":False,"parse_special":True})["tokens"]
        assert len(tokenized)+max_tokens <= config["context_tokens"], ("UNSUPPORTED_LENGTH",name,len(tokenized))
        payload = {"prompt":surface,"n_predict":max_tokens,"return_tokens":True,"stream":False,
                   "temperature":0.0,"seed":0,"samplers":["temperature"],"dynatemp_range":0.0,
                   "mirostat":0,"top_k":0,"top_p":1.0,"min_p":0.0,"repeat_penalty":1.0,
                   "frequency_penalty":0.0,"presence_penalty":0.0,"n_probs":0,
                   "cache_prompt":False,"id_slot":0,"ignore_eos":False}
        row = {"id":name,"messages":messages,"request":payload,"input_tokens_tokenizer":len(tokenized),"start_epoch":time.time()}
        calls.append({"id":name,"status":"STARTED"})
        save("CALL_LEDGER.json", calls)
        t = time.perf_counter()
        try:
            res = request("/completion", payload, timeout=max(0.1,min(config["per_call_seconds"],model_deadline-time.time())))
            row.update(response=res,elapsed_seconds=time.perf_counter()-t)
            assert not res.get("truncated"), "CONTEXT_TRUNCATION"
            output = res.get("content", "")
            actual_tokens = res.get("tokens_predicted", res.get("timings",{}).get("predicted_n"))
            calls[-1].update(status="COMPLETED",input_tokens=len(tokenized),output_tokens=actual_tokens,
                             seconds=row["elapsed_seconds"],stop_type=res.get("stop_type"),max_new_tokens=max_tokens)
            save("raw/"+name+".json",row)
            save("CALL_LEDGER.json",calls)
            print(json.dumps({"event":"MODEL_COMPLETED",**calls[-1]},ensure_ascii=False),flush=True)
            return {"content":output,"parsed":parsed(output),"call_id":name,"input_tokens":len(tokenized),
                    "output_tokens":actual_tokens,"seconds":row["elapsed_seconds"],"stop_type":res.get("stop_type"),
                    "complete":res.get("stop_type")=="eos"}
        except Exception as ex:
            row.update(error_type=type(ex).__name__,error=str(ex),elapsed_seconds=time.perf_counter()-t)
            calls[-1].update(status="ERROR",error_type=type(ex).__name__)
            save("raw/"+name+".json",row);save("CALL_LEDGER.json",calls)
            raise

    def evaluate(name, evidence):
        return call(name,[{"role":"system","content":prompts["judge_system"]},
                          {"role":"user","content":json.dumps({"public_context":prompts["public_context"],
                          "target_question":prompts["target"],"visible_evidence":evidence},ensure_ascii=False)}],config["judge_new_tokens"])

    try:
        for asset, expected in config["asset_expected_hashes"].items():
            assert shaf(asset) == expected, ("ASSET_CHANGED",asset)
        backend = next(p for p in config["asset_expected_hashes"] if p.endswith("llama-server.exe"))
        model = next(p for p in config["asset_expected_hashes"] if "00001-of-00002.gguf" in p)
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1",port)) != 0, "OWN_PORT_BUSY"
        argv = [backend,"-m",model,"--alias","c2rag-openstax-dev","--host","127.0.0.1","--port",str(port),
                "-c",str(config["context_tokens"]),"-np","1","-ngl","0","-t","4","-b","128","-ub","128",
                "--no-warmup","--no-webui","--temp","0","--samplers","temperature","--dynatemp-range","0","--mirostat","0","--seed","0"]
        (R/"backend").mkdir(exist_ok=True)
        (R/"backend/slot_cache").mkdir(exist_ok=True)
        argv.extend(["--slot-save-path",str(R/"backend/slot_cache")])
        with (R/"backend/backend.log").open("wb") as log:
            server = subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        save("backend/service.json",{"pid":server.pid,"argv":argv,"owned":True,"gpu_layers":0})
        load_start = time.time()
        while time.time()-load_start < 120:
            assert server.poll() is None, "BACKEND_LOAD_EXIT"
            try:
                if request("/health", timeout=2).get("status") == "ok":
                    break
            except Exception:
                time.sleep(0.5)
        else:
            raise TimeoutError("BACKEND_LOAD_TIMEOUT")
        save("backend/props.json",request("/props"))
        print(json.dumps({"event":"MODEL_LOADED","load_seconds":time.time()-load_start},ensure_ascii=False),flush=True)
        role_sources = read("ROLE_SOURCES.json")
        indexes = {}
        for role, chunks in role_sources.items():
            resources = [TeacherResource.from_dict({"resource_id":"OpenStax-UP2-8.4-Ex8.10","chunk_id":c["id"],"content":c["text"],"knowledge":"电容 电介质 能量 隔离 断电 完全填充","difficulty":"大学基础"}) for c in chunks]
            indexes[role] = ResourceIndex(resources)
        for q in read("QUESTIONS.json"):
            idx = indexes[q["role"]]
            scores = idx.similarities(q["question"])
            order = sorted(range(len(scores)),key=lambda i:(-scores[i],idx.resources[i].chunk_id))[:3]
            retrieved = [{**role_sources[q["role"]][i],"retrieval_score":scores[i]} for i in order]
            visible = [{"turn":x["turn"],"role":x["role"],"question":x["question"],"answer":x["answer"]} for x in transcript]
            messages = [{"role":"system","content":prompts["teacher_system"]+"\n职责："+q["role"]},
                        {"role":"user","content":json.dumps({"role_source_retrieval":retrieved,"visible_history":visible,"current_student_question":q["question"]},ensure_ascii=False)}]
            result = call("T%02d"%q["turn"],messages,config["teacher_new_tokens"])
            record = {**q,"answer":result["content"],"retrieved":retrieved,"model_call":{k:v for k,v in result.items() if k not in {"content","parsed"}}}
            transcript.append(record)
            with (R/"TRANSCRIPT.jsonl").open("a",encoding="utf-8") as f:
                f.write(json.dumps(record,ensure_ascii=False)+"\n")
        save("OBSERVATION_LOCK.json",{"transcript_sha256":shaf(R/"TRANSCRIPT.jsonl"),"turns":len(transcript),"locked_before_judgment":True})
        state = {"facts":[],"rules":[],"unresolved":[]}
        for turn in range(1,7):
            history = [{"turn":x["turn"],"role":x["role"],"question":x["question"],"answer":x["answer"]} for x in transcript[:turn]]
            save("prefixes/P%02d.json"%turn,{"public_context":prompts["public_context"],"target_question":prompts["target"],"visible_history":history})
            full = evaluate("B1L_P%02d"%turn,history)
            evaluations.append({"prefix":turn,"method":"B1-L",**full})
            save("EVALUATIONS_RAW.json",evaluations)
            update = call("B3_UPDATE_P%02d"%turn,[{"role":"system","content":prompts["state_update_system"]},
                          {"role":"user","content":json.dumps({"public_context":prompts["public_context"],"previous_state":state,"current_turn":history[-1]},ensure_ascii=False)}],config["update_new_tokens"])
            delta = update["parsed"]
            valid = bool(update["complete"] and isinstance(delta,dict) and all(isinstance(delta.get(k),list) for k in state))
            quote_checks=[]
            if valid:
                for kind in state:
                    for item in delta[kind]:
                        if isinstance(item,dict):
                            quote=item.get("source_span")
                            quote_checks.append({"kind":kind,"quote":quote,"exact_in_current_turn":isinstance(quote,str) and bool(quote) and (quote in history[-1]["question"] or quote in history[-1]["answer"]),"turn_matches":item.get("source_turn")==turn})
                    state[kind].extend(delta[kind])
            else:
                state["unresolved"].append({"status":"TECHNICAL_UPDATE_FAILURE","source_turn":turn,"reason":"Invalid or incomplete JSON update; current text not represented reliably"})
            save("states/P%02d.json"%turn,{"state":state,"update":update,"update_valid":valid,"quote_checks":quote_checks})
            inc = evaluate("B3_P%02d"%turn,state)
            evaluations.append({"prefix":turn,"method":"B3",**inc,"update_valid":valid,
                                "update_seconds":update["seconds"],"update_input_tokens":update["input_tokens"],"update_output_tokens":update["output_tokens"],
                                "source_quote_checks":quote_checks})
            save("EVALUATIONS_RAW.json",evaluations)
    except Exception as ex:
        error={"type":type(ex).__name__,"message":str(ex)}
        save("RUN_FAILURE.json",error)
        print(json.dumps({"event":"RUN_STOPPED","error":error},ensure_ascii=False),flush=True)
    finally:
        if server and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill();server.wait(timeout=5)
        save("backend/shutdown.json",{"pid":server.pid if server else None,"owned_process_closed":server.poll() is not None if server else True})
        save("EXECUTION_SUMMARY.json",{"status":"EXECUTED_EXPLORATORY" if len(transcript)==6 and len(evaluations)==12 and error is None else "PARTIAL_BLOCKED", "teacher_rounds":len(transcript),"prefix_predictions":len(evaluations),"generation_calls":len(calls),"error":error,"execution_seconds":time.time()-entry,"gpu_layers":0,"paid_api_calls":0,"training":0,"no_second_run":True})
        print(json.dumps(read("EXECUTION_SUMMARY.json"),ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
