"""One non-dataset probe: actual NeMo input rail and fake LLM, no network/model."""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",LANGSMITH_TRACING="false",LANGCHAIN_TRACING_V2="false",CUDA_VISIBLE_DEVICES="")
from nemoguardrails import RailsConfig, LLMRails
from langchain_core.language_models.fake import FakeListLLM
from nemoguardrails.embeddings.providers.base import EmbeddingModel
from nemoguardrails.embeddings.providers import register_embedding_provider
import socket

original_connect = socket.socket.connect
def offline_connect(self, address):
    if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost"):
        return original_connect(self, address)
    raise OSError("external network disabled for offline probe")
socket.socket.connect = offline_connect

class FixtureEmbedding(EmbeddingModel):
    engine_name = "OfflineFixture"
    def __init__(self, *args, **kwargs): pass
    def encode(self, documents): return [[1.0, 0.0] for _ in documents]
    async def encode_async(self, documents): return self.encode(documents)

R=Path(__file__).resolve().parent
YAML="""
models:
  - type: embeddings
    engine: OfflineFixture
    model: fixed
rails:
  input:
    flows:
      - dynamic policy gate
"""
COLANG='''
define bot refuse to respond
  "REJECTED_BY_INPUT_RAIL"

define flow dynamic policy gate
  $allowed = execute check_dynamic_policy
  if not $allowed
    bot refuse to respond
    stop
'''


def main():
    import time
    from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
    from run_replay import run_case
    ids=["P1","P2","E2","E5","V2","V3"]
    cases={c["case_id"]:c for c in map(json.loads,(R/"cases.jsonl").read_text(encoding="utf-8").splitlines())}
    out=R/"runs/framework_v1";out.mkdir(exist_ok=False)
    register_embedding_provider(model=FixtureEmbedding, engine_name="OfflineFixture")
    config=RailsConfig.from_content(colang_content=COLANG,yaml_content=YAML)
    app=LLMRails(config,llm=FakeListLLM(responses=["SYNTHETIC_DELIVERY_RECEIPT"]))
    adapter=NeMoGuardrailsAdapter("fixture-only")
    state={"case":None,"action_calls":0,"decision":None,"adapter":None}
    def check_dynamic_policy(context=None):
        state["action_calls"]+=1
        state["adapter"]=adapter.check_user_input("synthetic teaching exercise",{})
        observed,_=run_case(state["case"])
        state["decision"]=observed["observed"][0]["result"]
        return state["decision"]=="ALLOW" and state["adapter"]["decision"]=="allow"
    app.register_action(check_dynamic_policy,name="check_dynamic_policy")
    results=[]
    with (out/"receiver.jsonl").open("w",encoding="utf-8") as sink:
      for cid in ids:
        case=cases[cid];state["case"]=case;state["decision"]=None;start=time.perf_counter()
        try:
          reply=app.generate(messages=[{"role":"user","content":"A simple synthetic teaching request. " + cid}])
          text=reply.get("content",""); receipt="SYNTHETIC_DELIVERY_RECEIPT" in text
          if receipt:
            sink.write(json.dumps({"case_id":cid,"content":text},ensure_ascii=False)+"\n");sink.flush()
          expected=case["expected"][0]
          ok=(state["decision"]==expected["result"] and receipt==expected["external_effect"])
          results.append({"case_id":cid,"status":"PASS" if ok else "FAIL","gate_decision":state["decision"],"expected":expected,"nemo_reply":reply,"receiver_write":receipt,"adapter_decision":state["adapter"]["decision"],"elapsed_seconds":time.perf_counter()-start})
        except Exception as e:
          results.append({"case_id":cid,"status":"ERROR","exception_type":type(e).__name__,"exception":str(e),"elapsed_seconds":time.perf_counter()-start})
    independently_read=[json.loads(x)["case_id"] for x in (out/"receiver.jsonl").read_text(encoding="utf-8").splitlines()]
    report={"scope":"real NeMo input rail + project adapter + synthetic policy replay + synthetic file receiver; not full production multi-agent integration", "results":results,"receiver_ids_independently_read":independently_read,"nemo_action_calls":state["action_calls"],"fake_llm":True,"fake_constant_embedding":True,"network_blocked":True,"gpu":False}
    (out/"results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
