import json
from types import SimpleNamespace

import pytest

from core.langgraph_runtime.workflow_monitor import observed_node, invoke_observed_graph
from core.langgraph_runtime.telemetry import LangSmithMonitor, SafeTelemetry


class ClientSpy:
    def __init__(self):
        self.calls = []

    def create_run(self, *args, **kwargs):
        self.calls.append(("create", args, kwargs))

    def update_run(self, *args, **kwargs):
        self.calls.append(("update", args, kwargs))

    def flush(self):
        self.calls.append(("flush", (), {}))


def test_backend_node_exports_only_static_stage_and_numeric_metrics():
    frame = SimpleNamespace(recorder=SafeTelemetry())
    runtime = SimpleNamespace(context=SimpleNamespace(frame=frame))
    def node(state, runtime):
        return {"stage": "validate", "completed": True,
                "question": "PRIVATE_STUDENT_QUESTION", "student_id": "PRIVATE_ID"}
    wrapped = observed_node("free_chat", "validate", node)

    class Graph:
        def invoke(self, state, *, context, config=None):
            return wrapped(state, runtime)

    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)
    result = invoke_observed_graph(Graph(), {}, context=runtime.context,
                                   frame=frame, monitor=monitor)
    assert result["completed"] is True
    assert frame.recorder.events[0].stage == "free_chat.validate"
    assert frame.recorder.events[0].metrics == {"completed": True}
    serialized = json.dumps(client.calls, default=str)
    assert "PRIVATE_" not in serialized
    assert "cogniguard.free_chat.validate" in serialized
    assert monitor.last_status == "submitted"


def test_backend_error_exports_only_generic_failure():
    frame = SimpleNamespace(recorder=SafeTelemetry())
    runtime = SimpleNamespace(context=SimpleNamespace(frame=frame))
    def node(state, runtime):
        raise RuntimeError("PRIVATE_SECRET_STACK")
    wrapped = observed_node("free_chat", "validate", node)

    class Graph:
        def invoke(self, state, *, context, config=None):
            return wrapped(state, runtime)

    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)
    with pytest.raises(RuntimeError, match="PRIVATE_SECRET_STACK"):
        invoke_observed_graph(Graph(), {}, context=runtime.context,
                              frame=frame, monitor=monitor)
    assert frame.recorder.events[0].status == "error"
    serialized = json.dumps(client.calls, default=str)
    assert "PRIVATE_" not in serialized
    assert "node_failed" in serialized


def test_backend_graph_disables_global_native_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    frame = SimpleNamespace(recorder=SafeTelemetry())
    runtime = SimpleNamespace(context=SimpleNamespace(frame=frame))

    def node(state, runtime):
        from langsmith.run_helpers import get_tracing_context
        assert get_tracing_context()["enabled"] is False
        return {"completed": True}

    wrapped = observed_node("free_chat", "validate", node)

    class Graph:
        def invoke(self, state, *, context, config=None):
            return wrapped(state, runtime)

    result = invoke_observed_graph(Graph(), {}, context=runtime.context,
                                   frame=frame, monitor=LangSmithMonitor())
    assert result["completed"] is True
