import json

import pytest
from core.langgraph_runtime.telemetry import SafeTelemetry, LangSmithMonitor, safe_metrics


class ClientSpy:
    def __init__(self):self.calls = []
    def create_run(self, *args, **kwargs):
        import inspect
        from langsmith import Client
        inspect.signature(Client.create_run).bind(None, *args, **kwargs)
        self.calls.append(("create", args, kwargs))
    def update_run(self, *args, **kwargs):
        import inspect
        from langsmith import Client
        inspect.signature(Client.update_run).bind(None, *args, **kwargs)
        self.calls.append(("update", args, kwargs))
    def flush(self):self.calls.append(("flush", (), {}))


def test_default_monitor_does_not_create_cloud_client():
    monitor = LangSmithMonitor()
    assert monitor.client is None
    assert not monitor.export(SafeTelemetry())


def test_backend_env_opt_in_without_key_remains_available(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "1")
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_PROJECT", "safe-test-project")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monitor = LangSmithMonitor.from_environment()
    assert monitor.enabled is False
    assert monitor.project == "safe-test-project"
    assert monitor.last_status == "credential_missing"
    recorder = SafeTelemetry()
    with recorder.span("free_chat.validate"):
        pass
    assert monitor.export(recorder) is False
    assert monitor.last_status == "credential_missing"


def test_backend_client_initialization_failure_is_nonfatal(monkeypatch):
    import langsmith
    monkeypatch.setenv("COGNIGUARD_LANGSMITH_ENABLED", "1")
    monkeypatch.setenv("LANGSMITH_API_KEY", "TEST_KEY_NOT_REAL")
    def broken_client(*args, **kwargs):
        raise RuntimeError("PRIVATE_AUTH_DETAIL")
    monkeypatch.setattr(langsmith, "Client", broken_client)
    monitor = LangSmithMonitor.from_environment()
    assert monitor.enabled is False
    assert monitor.last_status == "client_init_failed"
    recorder = SafeTelemetry()
    with recorder.span("free_chat.validate"):
        pass
    assert monitor.export(recorder) is False
    assert monitor.last_status == "client_init_failed"


def test_metric_allowlist_rejects_content_and_nonfinite_numbers():
    assert safe_metrics({"selected_count": 3, "question": "PRIVATE", "student_id": "PRIVATE",
                         "privacy_after": float("nan"), "duration_ms": float("inf")}) == {"selected_count": 3}


def test_unknown_span_name_rejected():
    with pytest.raises(ValueError):
        with SafeTelemetry().span("PRIVATE_STUDENT_NAME"):pass


def test_export_tree_has_no_raw_input_output_metadata_or_exception():
    recorder = SafeTelemetry()
    with recorder.span("generate") as metrics:
        metrics.update(selected_count=3, question="PRIVATE_QUESTION", student_id="PRIVATE_STUDENT")
    with pytest.raises(RuntimeError):
        with recorder.span("watermark"):
            raise RuntimeError("PRIVATE_API_KEY_AND_STACK")
    client = ClientSpy();monitor = LangSmithMonitor(enabled=True, client=client)
    assert monitor.export(recorder)
    serialized = json.dumps(client.calls, default=str)
    assert "PRIVATE_" not in serialized
    assert "node_failed" in serialized
    creates = [args for verb, args, kw in client.calls if verb == "create"]
    assert len(creates) == 3
    for verb, args, kwargs in client.calls:
        assert kwargs.get("inputs", {}) == {}
        assert kwargs.get("outputs", {}) == {}


def test_transport_failure_is_nonfatal_and_error_is_not_logged():
    class Broken(ClientSpy):
        def create_run(self, *args, **kwargs):raise RuntimeError("Authorization: PRIVATE_KEY")
    recorder = SafeTelemetry()
    with recorder.span("generate"):pass
    monitor = LangSmithMonitor(enabled=True, client=Broken())
    assert monitor.export(recorder) is False
    assert monitor.last_status == "export_failed"


def test_real_sdk_serializes_safe_spans_with_mocked_transport(monkeypatch):
    from langsmith import Client
    captured = []
    class Response:
        status_code = 200
        text = '{}'
        def json(self):return {}
        def raise_for_status(self):pass
    def transport(self, *args, **kwargs):
        captured.append((args, kwargs))
        return Response()
    monkeypatch.setattr(Client, "request_with_retries", transport)
    client = Client(api_url="http://127.0.0.1:1", api_key="TEST_KEY_NOT_REAL",
                    auto_batch_tracing=False, hide_inputs=True, hide_outputs=True,
                    hide_metadata=lambda m: safe_metrics(m), omit_traced_runtime_info=True,
                    info={"version": "0.0"})
    recorder = SafeTelemetry()
    with recorder.span("generate") as metrics:
        metrics.update(selected_count=2, question="PRIVATE_RAW_INPUT")
    monitor = LangSmithMonitor(enabled=True, client=client)
    assert monitor.export(recorder)
    serialized = repr(captured)
    assert captured
    assert "PRIVATE_RAW_INPUT" not in serialized
    assert "cogniguard.generate" in serialized
    client.close()


def test_parallel_spans_root_uses_earliest_start_and_latest_end():
    from core.langgraph_runtime.telemetry import NodeEvent
    from datetime import datetime
    recorder = SafeTelemetry()
    # Completion order is not start order when teachers run in parallel.
    recorder.events = [
        NodeEvent("teacher_execute", "2026-10-13T00:00:02+00:00", "2026-10-13T00:00:03+00:00", 1000, "ok", {"teacher_index": 1}),
        NodeEvent("teacher_execute", "2026-10-13T00:00:01+00:00", "2026-10-13T00:00:04+00:00", 3000, "ok", {"teacher_index": 0})]
    client = ClientSpy();monitor = LangSmithMonitor(enabled=True, client=client)
    assert monitor.export(recorder)
    root = client.calls[0][2]
    last = [c for c in client.calls if c[0] == "update"][-1][2]
    assert root["start_time"] == datetime.fromisoformat("2026-10-13T00:00:01+00:00")
    assert last["end_time"] == datetime.fromisoformat("2026-10-13T00:00:04+00:00")
