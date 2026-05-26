from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer
from typing import Any

import pytest

from server import CogniGuardDashboardAPIHandler


@pytest.fixture()
def api_base_url() -> str:
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
