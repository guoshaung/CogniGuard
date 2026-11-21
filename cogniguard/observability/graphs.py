"""Safe node-level LangSmith monitoring for protected LangGraph workflows.

Graph state and invocation context never enter the exporter. Native LangGraph
tracing remains disabled even when the global tracing flag is set elsewhere.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .telemetry import (
    STAGES,
    LangSmithMonitor,
    SafeTelemetry,
    active_recorder,
    request_observation,
    safe_metrics,
)


def observed_node(graph_name: str, node_name: str, fn: Callable):
    stage = f"{graph_name}.{node_name}"
    if stage not in STAGES:
        raise ValueError(f"Unregistered safe graph stage: {stage}")

    @wraps(fn)
    def wrapped(state, runtime):
        recorder: SafeTelemetry = runtime.context.frame.recorder
        with recorder.span(stage) as metrics:
            update = fn(state, runtime)
            if isinstance(update, dict):
                metrics.update(safe_metrics(update))
            return update

    return wrapped


def invoke_observed_graph(
    graph,
    state: dict,
    *,
    context: Any,
    frame: Any,
    monitor: LangSmithMonitor | None = None,
    config: dict | None = None,
):
    shared = active_recorder()
    original = frame.recorder
    if shared is not None:
        frame.recorder = shared
    else:
        monitor = monitor or LangSmithMonitor.from_environment()
    try:
        with request_observation(frame.recorder):
            return graph.invoke(state, context=context, config=config)
    finally:
        try:
            # The outer request owns export, once all delivery spans have closed.
            if shared is None:
                monitor.export(frame.recorder)
        finally:
            frame.recorder = original
