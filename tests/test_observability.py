"""Safe observability contracts; no real LangSmith service or models."""

import asyncio
import importlib
import json
from types import SimpleNamespace

import pytest

from cogniguard.observability import (
    LangSmithMonitor,
    NodeEvent,
    SafeTelemetry,
    TraceIsolationError,
    active_recorder,
    configuration_status,
    request_observation,
    safe_metrics,
)
from cogniguard.observability.graphs import invoke_observed_graph, observed_node


class ClientSpy:
    def __init__(self):
        self.calls = []

    def create_run(self, **kwargs):
        self.calls.append(("create", kwargs))

    def update_run(self, run_id, **kwargs):
        self.calls.append(("update", {"id": run_id, **kwargs}))

    def flush(self):
        self.calls.append(("flush", {}))


def test_legacy_modules_preserve_identity():
    for old, new in (
        ("core.langgraph_runtime.telemetry", "cogniguard.observability.telemetry"),
        ("core.langgraph_runtime.workflow_monitor", "cogniguard.observability.graphs"),
    ):
        assert importlib.import_module(old) is importlib.import_module(new)


def test_native_global_tracing_is_not_an_export_opt_in(monkeypatch):
    monkeypatch.delenv("COGNIGUARD_LANGSMITH_ENABLED", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monitor = LangSmithMonitor.from_environment()
    assert monitor.client is None
    assert monitor.summary()["status"] == "disabled"


def test_configuration_reads_environment_without_constructing_any_monitor(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Configuration inspection constructed a monitor")

    monkeypatch.setattr(LangSmithMonitor, "__init__", forbidden)
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_API_KEY")
    monkeypatch.delenv("COGNIGUARD_LANGSMITH_PROJECT", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "standard-project")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://PRIVATE_KEY@host/private?token=PRIVATE")
    status = configuration_status()
    assert status["status"] == "configured"
    assert status["project"] == "standard-project"
    assert status["client_initialized"] is False
    assert status["credential_present"] is True
    assert "PRIVATE" not in json.dumps(status)


@pytest.mark.parametrize("command", ["status", "smoke"])
@pytest.mark.parametrize("project", ["standard-project", "PRIVATE_PROJECT/path"])
def test_cli_configuration_is_local_safe_and_uses_standard_alias(
    monkeypatch,
    capsys,
    command,
    project,
):
    import langsmith

    from cogniguard.runtime import mode
    from cogniguard.workflows import __main__ as cli

    bootstraps = []
    monkeypatch.setattr(mode, "_load_env_file", lambda: bootstraps.append(True))
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "true")
    monkeypatch.delenv("COGNIGUARD_LANGSMITH_PROJECT", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", project)
    monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_API_KEY")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://PRIVATE_AUTH@host?key=PRIVATE")
    monkeypatch.setattr(langsmith, "Client", lambda **kwargs: pytest.fail("Client constructed"))
    monkeypatch.setattr("sys.argv", ["cogniguard.workflows", "langsmith", command])
    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == (project if project == "standard-project" else "configured")
    assert payload["status"] == ("configured" if command == "status" else "PLANNED_NO_NETWORK")
    assert payload["client_initialized"] is False
    assert "PRIVATE" not in json.dumps(payload)
    assert bootstraps == [True]


def test_api_runtime_configuration_never_constructs_client(monkeypatch):
    import langsmith

    from cogniguard.api.routes import dashboard
    from cogniguard.api.routing import ApiRequest

    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_API_KEY")
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_PROJECT", "PRIVATE_PROJECT/path")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://PRIVATE_AUTH@host?key=PRIVATE")
    monkeypatch.setattr(langsmith, "Client", lambda **kwargs: pytest.fail("Client constructed"))
    monkeypatch.setattr(dashboard, "get_runtime_status", lambda: {"agent_call_mode": "mock"})
    output = []
    handler = SimpleNamespace(_send_json=lambda payload, **kwargs: output.append(payload))
    dashboard.runtime_status(handler, ApiRequest.from_target("/api/runtime/status"))
    assert output[0]["observability"]["client_initialized"] is False
    assert output[0]["observability"]["status"] == "configured"
    assert "PRIVATE" not in json.dumps(output)


@pytest.mark.parametrize("has_key", [True, False])
def test_cli_explicit_submit_reports_actual_monitor_state(monkeypatch, capsys, has_key):
    import langsmith

    from cogniguard.runtime import mode
    from cogniguard.workflows import __main__ as cli

    monkeypatch.setattr(mode, "_load_env_file", lambda: None)
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "false")
    if has_key:
        monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_API_KEY")
    else:
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    client = ClientSpy()
    constructed = []

    def factory(**kwargs):
        constructed.append(kwargs)
        return client

    monkeypatch.setattr(langsmith, "Client", factory)
    monkeypatch.setattr("sys.argv", ["cogniguard.workflows", "langsmith", "smoke", "--submit"])
    assert cli.main() == (0 if has_key else 1)
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == ("submitted" if has_key else "CREDENTIAL_MISSING")
    assert payload["client_initialized"] is has_key
    assert payload["remote_confirmed"] is False
    if has_key:
        assert payload["enabled"] is True
        assert constructed and client.calls
    else:
        assert not constructed and not client.calls
    assert "PRIVATE_API_KEY" not in json.dumps(payload)


def test_environment_aliases_and_explicit_precedence(monkeypatch):
    monkeypatch.delenv("COGNIGUARD_LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("COGNIGUARD_LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.setenv("LANGSMITH_PROJECT", "standard-project")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://standard.invalid")
    monitor = LangSmithMonitor()
    assert monitor.project == "standard-project"
    assert monitor.endpoint == "https://standard.invalid"
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_PROJECT", "cogni-project")
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENDPOINT", "https://cogni.invalid")
    monitor = LangSmithMonitor()
    assert monitor.project == "cogni-project"
    assert monitor.endpoint == "https://cogni.invalid"


def test_enabled_client_initialization_does_not_submit(monkeypatch):
    import langsmith

    constructed = []
    monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_KEY")
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "true")
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENDPOINT", "https://safe.invalid")

    def client(**kwargs):
        constructed.append(kwargs)
        return ClientSpy()

    monkeypatch.setattr(langsmith, "Client", client)
    monitor = LangSmithMonitor.from_environment()
    assert monitor.enabled
    assert constructed[0]["api_url"] == "https://safe.invalid"
    assert constructed[0]["hide_inputs"] is True
    assert constructed[0]["hide_outputs"] is True
    assert constructed[0]["timeout_ms"] == 2000
    assert monitor.client.calls == []


def test_request_graphs_share_nested_spans_and_export_once(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    request = SafeTelemetry()
    original = SafeTelemetry()
    frame = SimpleNamespace(recorder=original)
    runtime = SimpleNamespace(context=SimpleNamespace(frame=frame))
    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)

    def node(state, runtime):
        from langsmith.run_helpers import get_tracing_context

        assert get_tracing_context()["enabled"] is False
        assert active_recorder() is request
        return {"model_calls": 1, "question": "PRIVATE_PROFILE"}

    wrapped = observed_node("free_chat", "generate", node)

    class Graph:
        def invoke(self, state, *, context, config=None):
            return wrapped(state, runtime)

    with request_observation(request):
        with request.span("gateway.request"):
            with request.span("gateway.operation"):
                invoke_observed_graph(
                    Graph(), {}, context=runtime.context, frame=frame, monitor=monitor
                )
            with request.span("gateway.delivery") as metrics:
                metrics.update(watermark_verified=True, model_calls=1)
            assert client.calls == []
    assert active_recorder() is None
    assert frame.recorder is original
    assert not original.events
    assert len(request.events) == 4
    assert monitor.export(request)
    creates = [data for kind, data in client.calls if kind == "create"]
    assert len(creates) == 5
    stages = {item["name"]: item for item in creates}
    assert (
        stages["cogniguard.gateway.operation"]["parent_run_id"]
        == stages["cogniguard.gateway.request"]["id"]
    )
    assert (
        stages["cogniguard.free_chat.generate"]["parent_run_id"]
        == stages["cogniguard.gateway.operation"]["id"]
    )
    assert "PRIVATE" not in json.dumps(client.calls, default=str)
    assert monitor.summary()["status"] == "submitted"


def test_error_resets_context_and_never_exports_exception_message():
    recorder = SafeTelemetry()
    with pytest.raises(RuntimeError):
        with request_observation(recorder):
            with recorder.span("gateway.delivery"):
                raise RuntimeError("PRIVATE_PROFILE_AND_KEY")
    assert active_recorder() is None
    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)
    assert monitor.export(recorder)
    payload = json.dumps(client.calls, default=str)
    assert "node_failed" in payload
    assert "PRIVATE" not in payload


def test_metrics_status_and_corrupted_record_do_not_leak():
    assert safe_metrics(
        {
            "model_calls": 2,
            "duration_ms": 10**1000,
            "source_bytes": float("nan"),
            "prompt": "PRIVATE",
        }
    ) == {"model_calls": 2}
    monitor = LangSmithMonitor(
        enabled=True,
        client=ClientSpy(),
        project="PRIVATE/key",
        endpoint="https://PRIVATE_KEY@host/path?key=PRIVATE",
    )
    monitor.last_status = "PRIVATE_ERROR"
    summary = monitor.summary()
    assert summary["status"] == "unknown"
    assert "PRIVATE" not in json.dumps(summary)
    recorder = SafeTelemetry()
    recorder.events = [NodeEvent("PRIVATE_PROFILE", "bad", "bad", 1, "ok")]
    assert monitor.export(recorder) is False
    assert monitor.summary()["status"] == "invalid_record"
    assert monitor.client.calls == []


def test_remote_failure_is_nonfatal_and_safe():
    class Broken(ClientSpy):
        def create_run(self, **kwargs):
            raise RuntimeError("PRIVATE_AUTH_HEADER")

    recorder = SafeTelemetry()
    with recorder.span("gateway.input") as metrics:
        metrics["validated"] = True
    monitor = LangSmithMonitor(enabled=True, client=Broken())
    assert monitor.export(recorder) is False
    assert monitor.summary()["status"] == "export_failed"
    assert "PRIVATE" not in json.dumps(monitor.summary())


@pytest.mark.parametrize("failure", ["construct", "enter", "exit"])
def test_trace_isolation_errors_are_sanitized_and_fail_closed(monkeypatch, failure):
    import langsmith

    entered = []

    class BrokenContext:
        def __enter__(self):
            if failure == "enter":
                raise RuntimeError("PRIVATE_CONTEXT")

        def __exit__(self, *args):
            if failure == "exit":
                raise RuntimeError("PRIVATE_CONTEXT")

    def factory(**kwargs):
        if failure == "construct":
            raise RuntimeError("PRIVATE_CONTEXT")
        return BrokenContext()

    monkeypatch.setattr(langsmith, "tracing_context", factory)
    with pytest.raises(TraceIsolationError) as caught:
        with request_observation(SafeTelemetry()):
            entered.append(True)
    assert entered == ([True] if failure == "exit" else [])
    assert "PRIVATE" not in str(caught.value)
    assert caught.value.__suppress_context__ is True
    assert active_recorder() is None


def test_trace_cleanup_never_overrides_business_error(monkeypatch):
    import langsmith

    class BrokenCleanup:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            raise RuntimeError("PRIVATE_CLEANUP_ERROR")

    monkeypatch.setattr(langsmith, "tracing_context", lambda **kwargs: BrokenCleanup())
    original = ValueError("business validation failed")
    with pytest.raises(ValueError) as caught:
        with request_observation(SafeTelemetry()):
            raise original
    assert caught.value is original
    assert active_recorder() is None


def test_only_bounded_flush_is_called():
    class Bounded(ClientSpy):
        def flush(self, timeout=None):
            self.calls.append(("flush", {"timeout": timeout}))

    class Unbounded(ClientSpy):
        def flush(self):
            pytest.fail("Unbounded flush invoked")

    recorder = SafeTelemetry()
    with recorder.span("monitor_smoke"):
        pass
    bounded = Bounded()
    monitor = LangSmithMonitor(enabled=True, client=bounded)
    assert monitor.export(recorder)
    assert ("flush", {"timeout": 0.25}) in bounded.calls
    assert monitor.summary()["remote_confirmed"] is False
    monitor = LangSmithMonitor(enabled=True, client=Unbounded())
    assert monitor.export(recorder)
    assert monitor.summary()["status"] == "submitted"
    assert monitor.summary()["remote_confirmed"] is False


def test_async_request_contexts_keep_separate_parent_trees():
    async def request():
        recorder = SafeTelemetry()

        async def child(stage):
            assert active_recorder() is recorder
            with recorder.span(stage):
                await asyncio.sleep(0)
                assert active_recorder() is recorder

        with request_observation(recorder), recorder.span("gateway.request"):
            await asyncio.gather(child("gateway.input"), child("gateway.delivery"))
        root = next(e for e in recorder.events if e.stage == "gateway.request")
        assert all(e.parent_span_id == root.span_id for e in recorder.events if e is not root)
        return recorder

    async def run():
        left, right = await asyncio.gather(request(), request())
        assert left.run_id != right.run_id
        assert active_recorder() is None

    asyncio.run(run())


def test_gateway_provider_and_nested_graph_export_one_safe_request(tmp_path, monkeypatch):
    from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
    from cogniguard.protection.text_provenance import TextProvenanceService
    from cogniguard.providers.mimo import MiMoChatClient
    from cogniguard.runtime.gateway import ProtectionGateway
    from cogniguard.runtime.protection_context import charge_domain_budget, transport_scope
    from cogniguard.runtime.sessions import SessionStore

    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)
    monkeypatch.setattr(LangSmithMonitor, "from_environment", classmethod(lambda cls: monitor))
    monkeypatch.setattr(
        MiMoChatClient,
        "_post_chat_completions",
        lambda self, body, on_text_delta=None: '{"answer":"先列出题目的已知条件。"}',
    )
    gateway = ProtectionGateway(
        store=SessionStore(tmp_path / "observed-sessions.sqlite3"),
        provenance=TextProvenanceService(b"test-only-observability-key" * 3, required=True),
        adapter=NeMoGuardrailsAdapter("", enabled=True),
    )
    graph_frame = SimpleNamespace(recorder=SafeTelemetry())
    runtime = SimpleNamespace(context=SimpleNamespace(frame=graph_frame))

    def node(state, runtime):
        return MiMoChatClient("PRIVATE_API_KEY").chat("PRIVATE_SYSTEM_PROMPT", state)

    wrapped = observed_node("free_chat", "generate", node)

    class Graph:
        def invoke(self, state, *, context, config=None):
            return wrapped(state, runtime)

    def operation(frame):
        charge_domain_budget("privacy", 0.1)
        return invoke_observed_graph(
            Graph(),
            {"profile": "PRIVATE_RAW_PROFILE", "resource": "PRIVATE_RESOURCE"},
            context=runtime.context,
            frame=graph_frame,
        )

    with transport_scope(None, None, lambda token: None):
        result = gateway.run("observability-test", {"message": "请解释解题步骤。"}, operation)
    assert result["output_validation"]["allowed"] is True
    assert result["observability"]["content_policy"] == "metrics_only"
    creates = [data for kind, data in client.calls if kind == "create"]
    root = creates[0]
    assert str(root["id"]) == result["observability"]["trace_id"]
    assert len([data for data in creates if data["name"] == "cogniguard.langgraph"]) == 1
    stages = {item["name"]: item for item in creates}
    assert "cogniguard.gateway.budget" in stages
    provider = stages["cogniguard.provider.mimo"]
    assert provider["run_type"] == "llm"
    graph = stages["cogniguard.free_chat.generate"]
    assert provider["parent_run_id"] == graph["id"]
    assert provider["trace_id"] == root["id"]
    assert provider["dotted_order"].startswith(graph["dotted_order"] + ".")
    assert provider["extra"]["metadata"]["model_calls"] == 1
    assert "PRIVATE" not in json.dumps(client.calls, default=str)
    assert monitor.summary()["status"] == "submitted"
