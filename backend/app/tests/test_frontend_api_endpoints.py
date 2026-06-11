from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer
from typing import Any

import pytest

from server import CogniGuardDashboardAPIHandler


@pytest.fixture()
def deterministic_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("MIMO_API_KEY", "")


@pytest.fixture()
def api_base_url(deterministic_runtime: None) -> str:
    httpd = HTTPServer(("127.0.0.1", 0), CogniGuardDashboardAPIHandler)
    host, port = httpd.server_address
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _get_json(base_url: str, path: str) -> Any:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=10) as response:
        assert response.status == 200
        assert response.headers["Content-Type"] == "application/json"
        return json.loads(response.read().decode("utf-8"))


def _post_ndjson(base_url: str, path: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.status == 200
        assert response.headers["Content-Type"].startswith("application/x-ndjson")
        return [
            json.loads(line.decode("utf-8"))
            for line in response
            if line.strip()
        ]


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def test_dashboard_metrics_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/dashboard/metrics")

    required = {
        "total_requests",
        "normal_requests",
        "attack_requests",
        "blocked_attacks",
        "sanitized_attacks",
        "degraded_attacks",
        "successful_attacks",
        "attack_success_rate",
        "defense_success_rate",
        "privacy_protection_rate",
        "copyright_protection_rate",
        "audit_coverage_rate",
    }
    assert required <= set(payload)
    for key in (
        "attack_success_rate",
        "defense_success_rate",
        "privacy_protection_rate",
        "copyright_protection_rate",
        "audit_coverage_rate",
    ):
        assert 0 <= payload[key] <= 1


def test_runtime_status_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/runtime/status")

    required = {
        "runtime_mode",
        "llm_provider",
        "api_key_loaded",
        "nemo_guardrails_enabled",
        "fallback_reason",
        "agent_call_mode",
    }
    assert required <= set(payload)
    assert payload["runtime_mode"] in {"mock", "llm", "guarded_llm"}
    assert payload["llm_provider"] == "Xiaomi MiMo"
    assert payload["agent_call_mode"] in {"deterministic_fallback", "real_llm"}


def test_demo_workflow_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/demo/workflow")
    steps = payload["steps"]

    assert len(steps) >= 7
    required = {
        "step_id",
        "step_name",
        "input_summary",
        "output_summary",
        "risk_score",
        "tpcs_decision",
        "related_agent",
        "related_protection_layer",
    }
    assert all(required <= set(step) for step in steps)
    assert any("MM-FOPD" in step["related_protection_layer"] for step in steps)
    assert any("HSW-ST" in step["related_protection_layer"] for step in steps)


def test_run_case_returns_new_protected_multi_agent_round(api_base_url: str) -> None:
    first = _get_json(api_base_url, "/api/run-case?index=0&t=1")
    second = _get_json(api_base_url, "/api/run-case?index=0&t=2")

    assert first["round_id"] != second["round_id"]
    required = {
        "round_id",
        "runtime_status",
        "workflow_steps",
        "agent_outputs",
        "communication_logs",
        "protection_logs",
        "final_protected_teaching_answer",
        "audit_trace",
    }
    assert required <= set(first)
    assert first["workflow_steps"]
    step_required = {
        "step_id",
        "step_name",
        "layer",
        "input_summary",
        "output_summary",
        "tpcs_decision",
        "nemo_decision",
        "risk_score",
        "timestamp",
    }
    assert all(step_required <= set(step) for step in first["workflow_steps"])
    assert all(
        step["tpcs_decision"] in {"allow", "sanitize", "degrade", "refuse"}
        for step in first["workflow_steps"]
    )
    assert all(
        step["nemo_decision"] in {"not_enabled", "allow", "block", "rewrite"}
        for step in first["workflow_steps"]
    )
    assert {"mm_fopd", "c2_rag", "hsw_st", "tpcs", "nemo_guardrails"} <= set(
        first["protection_logs"]
    )
    assert first["communication_logs"]


def test_run_case_stream_emits_incremental_events(api_base_url: str) -> None:
    events = _post_ndjson(
        api_base_url,
        "/api/run-case/stream",
        {
            "case_index": 0,
            "runtime_mode": "mock",
            "enable_nemo": False,
        },
    )

    event_types = [event["type"] for event in events]
    workflow_steps = [
        event["step"]
        for event in events
        if event["type"] == "workflow_step"
    ]

    assert event_types[0] == "stream_opened"
    assert "run_started" in event_types
    assert len(workflow_steps) == 12
    assert event_types.count("run_completed") == 1
    assert event_types.index("workflow_step") < event_types.index("run_completed")


def test_classroom_dialogue_preserves_closed_loop_state_and_attack_feedback(
    api_base_url: str,
) -> None:
    first = _post_json(
        api_base_url,
        "/api/dialogue/next-round",
        {
            "case_index": 0,
            "turn_kind": "learning",
            "round_number": 1,
        },
    )
    attack = _post_json(
        api_base_url,
        "/api/dialogue/next-round",
        {
            "case_index": 0,
            "turn_kind": "attack",
            "round_number": 1,
            "attack_type": "copyright_reconstruction",
            "session_state": first["session_state"],
        },
    )
    second = _post_json(
        api_base_url,
        "/api/dialogue/next-round",
        {
            "case_index": 0,
            "turn_kind": "learning",
            "round_number": 2,
            "session_state": attack["session_state"],
        },
    )

    assert [message["role"] for message in first["messages"][:4]] == [
        "student",
        "teacher",
        "learner",
        "feedback",
    ]
    assert attack["attack_blocked"] is True
    assert attack["session_state"]["tpcs"]["degradation_level"] >= 1
    assert (
        second["session_state"]["teacher_resource"]["return_mode"]
        == "synthetic_variant"
    )
    assert second["session_state"]["student_profile"]["learning_evidence"]
    assert second["session_state"]["student_profile"]["student_agent"]
    assert second["session_state"]["audit_trace"]["hash_chain_head"] != "GENESIS"


def test_classroom_dialogue_continues_until_target_is_confirmed(
    api_base_url: str,
) -> None:
    state = None
    result = None
    for round_number in range(1, 20):
        result = _post_json(
            api_base_url,
            "/api/dialogue/next-round",
            {
                "case_index": 0,
                "turn_kind": "learning",
                "round_number": round_number,
                "target_mastery": 0.82,
                "session_state": state,
            },
        )
        state = result["session_state"]
        if result["goal"]["goal_met"]:
            break

    assert result is not None
    assert result["goal"]["goal_met"] is True
    assert result["goal"]["consecutive_passes"] >= 2
    assert state["student_profile"]["mastery_estimate"] >= 0.82
    assert any(message["role"] == "goal" for message in result["messages"])


def test_single_and_batch_attack_execution_endpoints(api_base_url: str) -> None:
    single = _post_json(
        api_base_url,
        "/api/run-attack",
        {"attack_case_id": "atk_003"},
    )
    batch = _post_json(
        api_base_url,
        "/api/attacks/run-batch",
        {},
    )

    assert single["success"] is True
    assert single["case"]["attack_case_id"] == "atk_003"
    assert single["case"]["actual_decision"]
    assert batch["success"] is True
    assert len(batch["results"]) == 7


def test_mm_fopd_cases_endpoint_does_not_expose_raw_payloads(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/mm-fopd/cases")
    cases = payload["cases"]

    assert cases
    required = {
        "raw_data_summary",
        "educational_semantics",
        "context_card",
        "allowed_fields",
        "forbidden_fields",
        "privacy_level",
        "disclosure_score",
        "privacy_budget_remaining",
    }
    assert required <= set(cases[0])
    dumped = json.dumps(cases, ensure_ascii=False)
    assert "coordinate_points" not in dumped
    assert "data/raw" not in dumped.replace("\\", "/")
    assert cases[0]["raw_data_summary"]["raw_payload_exposed"] is False


def test_c2rag_cases_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/c2-rag/cases")
    cases = payload["cases"]

    assert cases
    required = {
        "query",
        "resource_id",
        "chunk_id",
        "copyright_level",
        "exposure_budget_before",
        "exposure_cost",
        "exposure_budget_after",
        "return_mode",
        "controlled_content",
        "prompt_injection_detected",
    }
    assert required <= set(cases[0])
    assert cases[0]["return_mode"] in {"summary", "variant", "snippet", "outline", "quote"}


def test_agent_communications_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/agents/communications")
    communications = payload["communications"]

    assert communications
    required = {
        "sender",
        "receiver",
        "message_type",
        "privacy_level",
        "disclosure_score",
        "cumulative_disclosure_score",
        "round_id",
        "tpcs_decision",
        "timestamp",
    }
    assert required <= set(communications[0])
    assert communications[0]["tpcs_decision"] in {"approved", "blocked"}


def test_attack_results_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/attacks/results")
    results = payload["results"]

    assert len(results) >= 7
    required = {
        "attack_case_id",
        "attack_type",
        "malicious_prompt",
        "target_agent",
        "target_protection_layer",
        "expected_defense",
        "actual_decision",
        "result",
        "risk_score",
        "audit_log_id",
    }
    assert required <= set(results[0])


def test_audit_traces_endpoint(api_base_url: str) -> None:
    payload = _get_json(api_base_url, "/api/audit/traces")
    traces = payload["traces"]

    assert traces
    required = {
        "answer_id",
        "watermark_id",
        "profile_card_id",
        "resource_ids",
        "chunk_ids",
        "agent_ids",
        "communication_log_id",
        "risk_log_id",
        "profile_update_log_id",
        "timestamp",
        "audit_complete",
    }
    assert required <= set(traces[0])
    assert traces[0]["watermark_id"]
    assert traces[0]["audit_complete"] is True
