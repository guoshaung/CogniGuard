from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import json
import re

import pytest
from core.langgraph_runtime.benchmarks.corpus import (wild_records,injec_records,benign_records,
    partition,text_sha,normalized_sha,load_corpus,cached_download,validate_download_url,HF_REV,HF_PARQUET_SHA)
from core.langgraph_runtime.benchmarks.plan import build_plan,load_plan,choose_cases
from core.langgraph_runtime.benchmarks.runner import (run_benchmark,BudgetedModel,CallBudgetExceeded,
    terminal_marker,summarize,ProducerContextBackend)
from core.langgraph_runtime.experiments import ROOT,sha256,run_matrix


@pytest.fixture
def corpus(tmp_path):
    directory=tmp_path/"corpus";directory.mkdir()
    text="Synthetic role-change wrapper for a harmless canary test."
    row={"case_id":"hf_wild:0","source":"hf_wild","source_index":0,
        "variant":"jailbreak_2023_12_25","text":text,"text_sha256":text_sha(text),
        "normalized_sha256":normalized_sha(text),"group_id":"fixture:heldout",
        "partition":"heldout","category":"fixture","source_role":"jailbreak_wrapper","native_score":None}
    (directory/"cases.jsonl").write_text(json.dumps(row)+"\n",encoding="utf-8")
    (directory/"corpus-lock.json").write_text(json.dumps({"schema_version":1,
        "cases_sha256":sha256(directory/"cases.jsonl"),"row_count":1}),encoding="utf-8")
    return directory


@pytest.fixture
def plan(corpus,tmp_path):
    path=tmp_path/"plan"
    build_plan(corpus,path,sources=("hf_wild",),max_calls=30)
    return path


def test_source_revision_and_expected_blob_hash_are_frozen():
    assert len(HF_REV)==40 and len(HF_PARQUET_SHA)==64


@pytest.mark.parametrize("url",["http://huggingface.co/x","https://127.0.0.1/x",
    "https://huggingface.co.evil.invalid/x","https://user:password@huggingface.co/x"])
def test_dataset_fetch_is_public_https_allowlisted(url):
    with pytest.raises(ValueError):validate_download_url(url)


def test_missing_data_never_downloads_without_explicit_flag(tmp_path):
    with pytest.raises(FileNotFoundError):cached_download("https://huggingface.co/public",tmp_path/"raw")


def test_corrupt_existing_cache_is_not_overwritten(tmp_path):
    file=tmp_path/"cache";file.write_bytes(b"corrupt")
    with pytest.raises(ValueError):cached_download("https://huggingface.co/public",file,expected_sha="0"*64)
    assert file.read_bytes()==b"corrupt"


def test_hf_exact_dedup_and_community_grouping():
    rows=wild_records([{"prompt":"Wrapper   TEXT","jailbreak":True,"community_id":1,"community_name":"x"},
        {"prompt":" wrapper text ","jailbreak":True,"community_id":1},
        {"prompt":"Different wrapper","jailbreak":True,"community_id":1},
        {"prompt":"regular","jailbreak":False}])
    assert len(rows)==2
    assert len({r["partition"] for r in rows})==1
    assert rows[0]["group_id"]==rows[1]["group_id"]


def test_december_hf_community_column_alias():
    rows=wild_records([{"prompt":"Historical wrapper text","jailbreak":True,"community":"AliasFamily","community_id":2}])
    assert rows[0]["category"]=="AliasFamily"


def test_injecagent_variants_are_paired_not_independent_deduped_cases():
    row={"Tool Response":"Untrusted tool text","Attacker Instruction":"fixture goal","User Tool":"DummyRead"}
    base=injec_records([row,row],"dh","base")
    enhanced=injec_records([row,row],"dh","enhanced")
    assert len(base+enhanced)==4
    assert base[0]["group_id"]==enhanced[0]["group_id"]
    assert len({r["group_id"] for r in base+enhanced})==2


def test_behavior_goals_are_not_accepted_as_jailbreak_wrappers():
    rows=benign_records([{"Goal":"Explain a normal task","Category":"example"}])
    assert rows[0]["source_role"]=="benign_behavior_reference"
    with pytest.raises(ValueError):choose_cases(rows,["jbb_benign"])


def test_frozen_corpus_detects_payload_tamper(corpus):
    (corpus/"cases.jsonl").write_text("{}\n",encoding="utf-8")
    with pytest.raises(ValueError):load_corpus(corpus)


def test_unicode_line_separators_inside_payload_do_not_split_json_records(corpus):
    row=json.loads((corpus/"cases.jsonl").read_text())
    row["text"]="original\u2028payload\u0085content";row["text_sha256"]=text_sha(row["text"])
    (corpus/"cases.jsonl").write_text(json.dumps(row,ensure_ascii=False)+"\n",encoding="utf-8")
    lock=json.loads((corpus/"corpus-lock.json").read_text());lock["cases_sha256"]=sha256(corpus/"cases.jsonl")
    (corpus/"corpus-lock.json").write_text(json.dumps(lock),encoding="utf-8")
    assert load_corpus(corpus)[1][0]["text"]==row["text"]


def test_plan_has_complete_paired_conditions_and_no_payload_text(plan):
    data,_,_,team=load_plan(plan)
    assert len(data["trials"])==8
    assert {x["condition"] for x in data["trials"]}=={"clean","attack"}
    assert data["model_calls_upper_bound"]==24
    assert "Synthetic role-change" not in (plan/"plan.json").read_text()


def test_plan_integrity_is_verified_before_execution(plan):
    (plan/"plan.json").write_text("{}",encoding="utf-8")
    with pytest.raises(ValueError):load_plan(plan)


def test_effective_boundary_prompt_changes_invalidate_frozen_plan(plan,monkeypatch):
    import core.langgraph_runtime.teachers.dag as dag
    monkeypatch.setattr(dag,"BOUNDARY_SYSTEM",dag.BOUNDARY_SYSTEM+" changed")
    with pytest.raises(ValueError,match="effective system prompt"):load_plan(plan)


def test_plan_only_does_not_construct_target_model(plan,tmp_path):
    def forbidden():raise AssertionError("Model must not be initialized")
    summary=run_benchmark(plan,tmp_path/"dry",model_factory=forbidden)
    assert summary["status"]=="PLAN_ONLY" and summary["real_api_calls"]==0


def test_real_mode_requires_explicit_flag_and_whole_plan_budget(plan,tmp_path):
    with pytest.raises(PermissionError):run_benchmark(plan,tmp_path/"blocked",mode="real_model")
    assert not (tmp_path/"blocked").exists()
    with pytest.raises(ValueError):run_benchmark(plan,tmp_path/"too_small",mode="real_model",allow_model_calls=True,max_calls=10)
    assert not (tmp_path/"too_small").exists()


def test_offline_echoes_never_become_real_attack_success_scores(plan,tmp_path):
    summary=run_benchmark(plan,tmp_path/"smoke",mode="offline_smoke")
    assert summary["status"]=="OFFLINE_WIRING_ONLY" and summary["real_api_calls"]==0
    assert all(g["task_hijack_proxy_rate_valid"] is None for g in summary["groups"])
    relay=[g for g in summary["groups"] if g["entry"]=="relay_tamper" and g["condition"]=="attack" and g["trust_mode"]=="enforce"]
    assert relay[0]["blocked"]==1


def test_mocked_model_demonstrates_valid_origin_gap_not_signature_magic(plan,tmp_path):
    class Model:
        def call(self,system,payload):
            assert set(payload)=={"task_view","upstream_messages","boundary","instruction_permission"}
            text=json.dumps(payload)
            markers=re.findall(r"CG_CANARY_[0-9a-f]{16}",text)
            return {"output":{"answer":markers[0] if markers else "ordinary math explanation"},
                    "usage":{"total_tokens":3}}
    summary=run_benchmark(plan,tmp_path/"mocked_http_contract",mode="real_model",
        allow_model_calls=True,model_factory=Model)
    producer=[g for g in summary["groups"] if g["entry"]=="producer_context" and g["condition"]=="attack"]
    assert all(g["terminal_marker_count"]==1 for g in producer)
    assert summary["model_invocations"]<=24 and summary["real_api_calls"]==0
    assert summary["status"]=="CUSTOM_TRANSPORT_CONTRACT_RUN"
    # Mocked provider only; this is a unit contract test, not a reported model result.
    rows=(tmp_path/"mocked_http_contract/rows.jsonl").read_text()
    assert "Synthetic role-change wrapper" not in rows
    assert "ordinary math explanation" not in rows


def test_errors_are_separate_from_defense_and_denominators_are_explicit():
    rows=[{"source":"fixture","entry":"producer_context","trust_mode":"enforce","condition":"attack",
           "status":s,"terminal_marker_observed":hit} for s,hit in [("completed",True),("blocked",False),("error",False)]]
    group=summarize(rows,mode="real_model")[0]
    assert group["valid"]==2 and group["errors"]==1 and group["total"]==3
    assert group["task_hijack_proxy_rate_valid"]==.5
    assert group["normal_task_quality"] is None


def test_schema_failures_are_not_reported_as_defense_success(plan,tmp_path):
    class Model:
        def call(self,*args):return {"output":{"answer":"x","unauthorized_tool":"dummy"}}
    summary=run_benchmark(plan,tmp_path/"schema_failure",mode="real_model",
                          allow_model_calls=True,model_factory=Model)
    assert all(g["valid"]==0 and g["schema_or_validation_errors"]==g["total"] for g in summary["groups"])
    assert all(g["task_hijack_proxy_rate_valid"] is None for g in summary["groups"])


def test_first_clean_transport_failure_stops_paid_calls_and_marks_unrun_trials(plan,tmp_path):
    from experiments.focused.redteam.model import ModelError
    class Model:
        def call(self,*args):raise ModelError("PRIVATE_RESPONSE_BODY_MUST_NOT_BE_LOGGED")
    summary=run_benchmark(plan,tmp_path/"preflight",mode="real_model",allow_model_calls=True,model_factory=Model)
    assert summary["status"]=="PREFLIGHT_FAILED" and summary["real_api_calls"]==0
    assert summary["model_invocations"]==1
    assert sum(g["not_run"] for g in summary["groups"])==7
    assert all(g["task_hijack_proxy_rate_valid"] is None for g in summary["groups"])
    assert "PRIVATE_RESPONSE_BODY" not in (tmp_path/"preflight/rows.jsonl").read_text()


def test_marker_in_refusal_text_is_not_terminal_objective_success():
    marker="CG_CANARY_1234567890abcdef"
    assert not terminal_marker("I will not print "+marker,marker)
    assert not terminal_marker('"'+marker+'"',marker)
    assert terminal_marker("answer\n"+marker,marker)


def test_call_budget_reservations_are_thread_safe():
    class Model:
        def call(self,*args):return {"output":{"answer":"x"},"usage":{"total_tokens":2}}
    model=BudgetedModel(Model(),2)
    def call():
        try:model.call("system",{});return True
        except CallBudgetExceeded:return False
    with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(lambda _:call(),range(6)))
    assert sum(result)==2 and model.calls==2 and model.usage["total_tokens"]==4


def test_native_adapter_forwards_per_kind_without_running_models(tmp_path,monkeypatch):
    captured=[]
    def spy(command,**kwargs):captured.append(command);return SimpleNamespace(returncode=0)
    monkeypatch.setattr("core.langgraph_runtime.experiments.subprocess.run",spy)
    summary=run_matrix(ROOT/"configs/benchmark-native-experiments.yaml",tmp_path/"native",execute=True)
    assert summary["failed_jobs"]==0
    command=captured[0]
    assert command[command.index("--per-kind")+1]=="1" and "--dry-run" in command
