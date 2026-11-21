"""One non-dataset probe: actual NeMo input rail and fake LLM, no network/model."""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
os.environ.update(HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",LANGSMITH_TRACING="false",LANGCHAIN_TRACING_V2="false",CUDA_VISIBLE_DEVICES="")
from nemoguardrails import RailsConfig, LLMRails
from langchain_core.language_models.fake import FakeListLLM

R=Path(__file__).resolve().parent
YAML="""
models: []
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
    out=R/"runs/framework_preflight_01.json"
    assert not out.exists()
    state={"allowed":False,"calls":0}
    def check_dynamic_policy(context=None):
        state["calls"]+=1
        return state["allowed"]
    try:
        config=RailsConfig.from_content(colang_content=COLANG,yaml_content=YAML)
        app=LLMRails(config,llm=FakeListLLM(responses=["fixed offline response"]))
        app.register_action(check_dynamic_policy,name="check_dynamic_policy")
        blocked=app.generate(messages=[{"role":"user","content":"A simple synthetic teaching request."}])
        state["allowed"]=True
        allowed=app.generate(messages=[{"role":"user","content":"A simple synthetic teaching request."}])
        result={"status":"PASS" if state["calls"]==2 and "REJECTED_BY_INPUT_RAIL" in str(blocked) and "REJECTED_BY_INPUT_RAIL" not in str(allowed) else "FAIL","actual_nemo_action_calls":state["calls"],"blocked_output":blocked,"allowed_output":allowed,"dataset_cases":0,"fake_llm":True,"remote_calls":0}
    except Exception as e:
        result={"status":"FAIL","exception_type":type(e).__name__,"exception":str(e),"actual_nemo_action_calls":state["calls"],"dataset_cases":0,"fake_llm":True,"remote_calls":0}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
