from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from cogniguard.api.http_server import CogniGuardDashboardAPIHandler
from cogniguard.api.routes import cases, create_router
from cogniguard.api.routing import ApiRequest, Route, Router
from cogniguard.api.services import case_execution
from cogniguard.api.services import watermarks as watermark_service
from cogniguard.runtime import mode


@pytest.fixture()
def api_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), CogniGuardDashboardAPIHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def exchange(url: str, method: str = "GET", body: bytes | None = None):
    request = urllib.request.Request(url, data=body, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        data = response.read()
        return response.status, response.headers, json.loads(data) if data else None


def test_registry_prefers_exact_and_longer_prefix_and_rejects_duplicates():
    router = Router()
    events = []

    def endpoint(handler, request):
        events.append(request.path)

    router.register(Route("GET", "/api/files/", endpoint, prefix=True))
    router.register(Route("GET", "/api/files/images/", endpoint, prefix=True))
    router.register(Route("GET", "/api/files/images/current", endpoint))
    assert router.match("GET", "/api/files/images/current").prefix is False
    assert router.match("GET", "/api/files/images/other").path == "/api/files/images/"
    assert router.dispatch("GET", None, ApiRequest.from_target("/api/files/report?index=4"))
    assert events == ["/api/files/report"]
    assert not router.dispatch("POST", None, ApiRequest.from_target("/api/unknown"))
    with pytest.raises(ValueError, match="Duplicate"):
        router.register(Route("GET", "/api/files/", endpoint, prefix=True))


def test_active_routes_exclude_legacy_routers():
    assert all(".legacy." not in route.endpoint.__module__ for route in create_router().routes)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_unknown_api_is_json_404(api_url, method):
    status, headers, data = exchange(f"{api_url}/api/does-not-exist", method)
    assert status == 404
    assert headers["Content-Type"] == "application/json"
    assert data["path"] == "/api/does-not-exist"


def test_wrong_method_reports_allowed_method(api_url):
    status, headers, _ = exchange(f"{api_url}/api/dialogue/free-chat")
    assert status == 405
    assert headers["Allow"] == "POST, OPTIONS"


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/dialogue/free-chat", b"{broken"),
        ("/api/dialogue/free-chat", b"[]"),
        ("/api/dialogue/free-chat", b"null"),
        ("/api/dialogue/next-round", b"{broken"),
        ("/api/run-case", b"{broken"),
        ("/api/run-case/stream", b"{broken"),
        ("/api/watermark/detect", b"{broken"),
        ("/api/watermark/image-detect", b"{broken"),
        ("/api/watermark/image-attack", b"{broken"),
        ("/api/watermark-attack", b"{broken"),
        ("/api/run-attack", b"{broken"),
    ],
)
def test_malformed_request_is_400_before_workflow_runs(api_url, path, body):
    status, _, data = exchange(f"{api_url}{path}", "POST", body)
    assert status == 400
    assert "error" in data


def test_encoded_static_traversal_is_rejected(api_url):
    status, _, data = exchange(f"{api_url}/%2e%2e/.env")
    assert status == 404
    assert data["error"] == "File not found"


def test_get_and_post_use_the_same_boolean_parser(api_url, monkeypatch):
    seen = []

    def execute(case_index, **kwargs):
        seen.append((case_index, kwargs["enable_nemo"]))
        return {"success": True}

    monkeypatch.setattr(cases, "execute_case", execute)
    assert exchange(f"{api_url}/api/run-case?index=2&enable_nemo=false")[0] == 200
    body = json.dumps({"case_index": 2, "enable_nemo": "false"}).encode()
    assert exchange(f"{api_url}/api/run-case", "POST", body)[0] == 200
    assert seen == [(2, False), (2, False)]
    assert exchange(f"{api_url}/api/run-case?enable_nemo=invalid")[0] == 400
    assert len(seen) == 2


def test_watermark_attack_preserves_demo_fallback(api_url, monkeypatch):
    monkeypatch.setattr(watermark_service, "run_all_attacks", None)
    body = json.dumps({"text": "therefore test"}).encode()
    status, _, data = exchange(f"{api_url}/api/watermark-attack", "POST", body)
    assert status == 200
    assert data["original_text"] == "therefore test"
    assert {item["attack_type"] for item in data["attacks"]} == {
        "delete_sentences",
        "light_paraphrase",
    }


@pytest.fixture()
def runtime_defaults(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("MIMO_API_KEY", "test-key-never-sent-to-a-model")
    monkeypatch.setattr(mode, "_load_env_file", lambda *args: None)
    monkeypatch.setattr(mode, "_nemo_guardrails_available", lambda: False)


def test_runtime_override_is_nested_exception_safe_and_thread_local(runtime_defaults):
    barrier = threading.Barrier(2)

    def read(selected):
        with mode.runtime_options(selected, selected == "guarded_llm"):
            barrier.wait(timeout=3)
            return mode.get_runtime_status()["runtime_mode"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(read, name) for name in ("llm", "guarded_llm")]
        assert [item.result(timeout=5) for item in futures] == ["llm", "guarded_llm"]
    assert mode.get_runtime_status()["runtime_mode"] == "mock"
    with mode.runtime_options("llm", False):
        with pytest.raises(RuntimeError):
            with mode.runtime_options("guarded_llm", True):
                raise RuntimeError("failed workflow")
        assert mode.get_runtime_status()["runtime_mode"] == "llm"
    assert mode.get_runtime_status()["runtime_mode"] == "mock"


def test_shared_case_service_scopes_options_and_logs_once(runtime_defaults, monkeypatch):
    def run_demo(**kwargs):
        assert mode.get_runtime_status()["runtime_mode"] == "guarded_llm"
        return {"round_id": "test-round"}

    monkeypatch.setattr(case_execution.dependencies, "run_demo", run_demo)
    monkeypatch.setattr(
        case_execution.dependencies,
        "load_demo_case",
        lambda **kwargs: SimpleNamespace(
            educational_semantics={},
            simulated_student_response="test response",
        ),
    )
    records = []
    monkeypatch.setattr(case_execution, "append_log", records.append)
    result = case_execution.execute_case(1, runtime_mode="guarded_llm")
    assert result["runtime_status"]["runtime_mode"] == "guarded_llm"
    assert len(records) == 1
    assert mode.get_runtime_status()["runtime_mode"] == "mock"


def test_langgraph_nodes_inherit_request_runtime(runtime_defaults):
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(dict)
    builder.add_node(
        "read_runtime",
        lambda state: {
            "runtime_mode": mode.get_runtime_status()["runtime_mode"],
        },
    )
    builder.add_edge(START, "read_runtime")
    builder.add_edge("read_runtime", END)
    graph = builder.compile(checkpointer=False)
    with mode.runtime_options("guarded_llm", True):
        assert graph.invoke({})["runtime_mode"] == "guarded_llm"
    assert mode.get_runtime_status()["runtime_mode"] == "mock"


def test_case_failure_restores_runtime_without_logging_success(runtime_defaults, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("case failed")

    monkeypatch.setattr(case_execution.dependencies, "run_demo", fail)
    records = []
    monkeypatch.setattr(case_execution, "append_log", records.append)
    with pytest.raises(RuntimeError, match="case failed"):
        case_execution.execute_case(0, runtime_mode="guarded_llm")
    assert records == []
    assert mode.get_runtime_status()["runtime_mode"] == "mock"
