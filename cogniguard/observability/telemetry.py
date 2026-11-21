"""Content-free local spans and opt-in LangSmith export.

Native graph tracing is disabled even if the parent process enables it. Only
these explicitly constructed, allowlisted records can leave this runtime.
"""

from __future__ import annotations

import inspect
import math
import os
import re
import sys
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

BACKEND_STAGES = frozenset(
    {
        "provider.mimo",
        "gateway.request",
        "gateway.input",
        "gateway.budget",
        "gateway.operation",
        "gateway.delivery",
        "gateway.finalize",
        "dashboard.load_case",
        "dashboard.protected_agents",
        "dashboard.watermark_bind",
        "dashboard.compliance",
        "dashboard.package_view",
        "free_chat.validate",
        "free_chat.check_input",
        "free_chat.select_backend",
        "free_chat.guard_input",
        "free_chat.generate",
        "free_chat.guard_output",
        "free_chat.finish",
        "classroom.load_case",
        "classroom.initialize",
        "classroom.attack_turn",
        "classroom.learning_turn",
        "classroom.finish",
        "classroom_learning.select_student",
        "classroom_learning.teaching_draft",
        "classroom_learning.watermark_media",
        "classroom_learning.audit_bindings",
        "classroom_learning.learning_assessment",
        "classroom_learning.next_step",
        "classroom_learning.state_commit",
        "classroom_learning.assemble_result",
        "protected_turn.prepare",
        "protected_turn.diagnose",
        "protected_turn.retrieve",
        "protected_turn.teach",
        "protected_turn.assess",
        "protected_turn.audit",
        "protected_turn.finish",
        "research.prepare",
        "research.select_profile",
        "research.control_resources",
        "research.audit_answer",
        "research.finish",
    }
)

STAGES = (
    frozenset(
        {
            "authorize",
            "minimize_profile",
            "retrieve",
            "control_resource",
            "measure_privacy",
            "prepare_teaching",
            "govern_input",
            "generate",
            "watermark",
            "govern_output",
            "finalize",
            "validate_plan",
            "execute_adapter",
            "collect_artifacts",
            "teacher_execute",
            "teacher_finalize",
            "tool_validate",
            "tool_freeze",
            "tool_execute",
            "tool_collect",
            "monitor_smoke",
        }
    )
    | BACKEND_STAGES
)
METRICS = frozenset(
    {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "selected_count",
        "candidate_count",
        "privacy_before",
        "privacy_after",
        "privacy_exhausted",
        "resource_exposure",
        "resource_required",
        "watermark_enabled",
        "governance_enabled",
        "artifact_count",
        "dry_run",
        "duration_ms",
        "node_count",
        "succeeded",
        "failed",
        "blocked",
        "completed",
        "decision_code",
        "teacher_index",
        "teacher_count",
        "received_edges",
        "blocked_edges",
        "invalid_edges",
        "output_chars",
        "model_calls",
        "validated",
        "risk_code",
        "source_bytes",
        "exit_code",
        "timed_out",
        "log_count",
        "stopped",
        "attack",
        "requests_used",
        "requests_remaining",
        "model_calls_used",
        "model_calls_remaining",
        "image_calls_used",
        "image_calls_remaining",
        "watermark_verified",
        "budget_exhausted",
    }
)


def safe_metrics(values: dict | None) -> dict:
    result = {}
    for key, value in (values or {}).items():
        if key not in METRICS or type(value) not in (bool, int, float):
            continue
        try:
            if math.isfinite(float(value)):
                result[key] = value
        except (OverflowError, ValueError):
            pass
    return result


def _environment_configuration() -> dict:
    return {
        "enabled": os.environ.get("COGNIGUARD_LANGSMITH_ENABLED", "").strip().lower()
        in {"1", "true", "yes", "on"},
        "project": os.environ.get("COGNIGUARD_LANGSMITH_PROJECT")
        or os.environ.get("LANGSMITH_PROJECT")
        or "cogniguard-langgraph",
        "endpoint": os.environ.get("COGNIGUARD_LANGSMITH_ENDPOINT")
        or os.environ.get("LANGSMITH_ENDPOINT")
        or None,
        "credential_present": bool(os.environ.get("LANGSMITH_API_KEY")),
    }


def _safe_project(project: str) -> str:
    return project if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", project) else "configured"


def configuration_status() -> dict:
    """Inspect existing environment only; never import SDK, build Client or load .env."""
    configuration = _environment_configuration()
    enabled = configuration["enabled"]
    credential_present = configuration["credential_present"]
    return {
        "enabled": enabled,
        "status": ("configured" if credential_present else "credential_missing")
        if enabled
        else "disabled",
        "credential_present": credential_present,
        "project": _safe_project(configuration["project"]),
        "endpoint_configured": bool(configuration["endpoint"]),
        "content_policy": "metrics_only",
        "native_tracing": False,
        "client_initialized": False,
        "remote_confirmed": False,
        "delivery_semantics": "sdk_queue_acceptance",
    }


_active_recorder: ContextVar[SafeTelemetry | None] = ContextVar("safe_recorder", default=None)
_active_span: ContextVar[tuple[str, str] | None] = ContextVar("safe_span", default=None)


def active_recorder() -> SafeTelemetry | None:
    """Return the request-local recorder, never request content or credentials."""
    return _active_recorder.get()


class TraceIsolationError(RuntimeError):
    """Native trace isolation could not be safely established or restored."""

    def __init__(self):
        super().__init__("Safe trace isolation is unavailable")


@contextmanager
def request_observation(recorder: SafeTelemetry):
    """Share one safe tree with nested graphs; this does not export anything."""
    token = _active_recorder.set(recorder)
    try:
        try:
            from langsmith import tracing_context
        except ModuleNotFoundError as exc:
            if exc.name != "langsmith":
                raise TraceIsolationError() from None
            tracing = nullcontext()
        except Exception:
            raise TraceIsolationError() from None
        else:
            try:
                tracing = tracing_context(enabled=False)
            except Exception:
                raise TraceIsolationError() from None
        try:
            tracing.__enter__()
        except Exception:
            raise TraceIsolationError() from None
        try:
            yield recorder
        except BaseException:
            # Isolation cleanup must never replace the original business error.
            try:
                tracing.__exit__(*sys.exc_info())
            except BaseException:
                pass
            raise
        else:
            try:
                tracing.__exit__(None, None, None)
            except Exception:
                raise TraceIsolationError() from None
    finally:
        _active_recorder.reset(token)


@dataclass(frozen=True)
class NodeEvent:
    stage: str
    started_at: str
    ended_at: str
    duration_ms: float
    status: str
    metrics: dict = field(default_factory=dict)
    span_id: str | None = None
    parent_span_id: str | None = None


class SafeTelemetry:
    def __init__(self):
        self.run_id = str(uuid4())
        self.events: list[NodeEvent] = []

    @contextmanager
    def span(self, stage: str):
        if stage not in STAGES:
            raise ValueError("Unknown telemetry stage")
        started = datetime.now(timezone.utc).isoformat()
        clock = time.perf_counter()
        span_id = str(uuid4())
        current = _active_span.get()
        parent_span_id = current[1] if current and current[0] == self.run_id else None
        token = _active_span.set((self.run_id, span_id))
        metrics = {}
        status = "ok"
        try:
            yield metrics
        except BaseException:
            status = "error"
            raise
        finally:
            _active_span.reset(token)
            self.events.append(
                NodeEvent(
                    stage,
                    started,
                    datetime.now(timezone.utc).isoformat(),
                    round((time.perf_counter() - clock) * 1000, 4),
                    status,
                    safe_metrics(metrics),
                    span_id,
                    parent_span_id,
                )
            )

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "content_policy": "metrics_only",
            "events": [asdict(e) for e in self.events],
        }


class LangSmithMonitor:
    """Export completed safe spans. Never wraps arbitrary model/tool functions."""

    def __init__(self, *, enabled=False, client=None, project=None, endpoint=None):
        configuration = _environment_configuration()
        self.enabled = enabled
        self.project = project or configuration["project"]
        self.endpoint = endpoint or configuration["endpoint"]
        self.client = client
        self.last_status = "disabled"
        if enabled and client is None:
            if not os.environ.get("LANGSMITH_API_KEY"):
                raise ValueError(
                    "Set LANGSMITH_API_KEY locally; do not put it in a dataset or plan"
                )
            from langsmith import Client

            self.client = Client(
                hide_inputs=True,
                hide_outputs=True,
                hide_metadata=lambda m: safe_metrics(m),
                omit_traced_runtime_info=True,
                api_url=self.endpoint,
                timeout_ms=2000,
            )

    def summary(self) -> dict:
        """Public status: no API key, URL, arbitrary exception or request identifiers."""
        statuses = {
            "disabled",
            "credential_missing",
            "client_init_failed",
            "empty",
            "submitted",
            "export_failed",
            "invalid_record",
        }
        return {
            "enabled": bool(self.enabled),
            "status": self.last_status if self.last_status in statuses else "unknown",
            "project": _safe_project(self.project),
            "endpoint_configured": bool(self.endpoint),
            "content_policy": "metrics_only",
            "native_tracing": False,
            "client_initialized": self.client is not None,
            "remote_confirmed": False,
            "delivery_semantics": "sdk_queue_acceptance",
        }

    @classmethod
    def from_environment(cls):
        """Backend opt-in; LANGSMITH_TRACING alone never enables raw tracing."""
        configuration = _environment_configuration()
        enabled = configuration["enabled"]
        project = configuration["project"]
        if enabled and not configuration["credential_present"]:
            monitor = cls(enabled=False, project=project)
            monitor.last_status = "credential_missing"
            return monitor
        if enabled:
            try:
                return cls(enabled=True, project=project)
            except Exception:
                # A broken observability client must not break a teaching turn.
                monitor = cls(enabled=False, project=project)
                monitor.last_status = "client_init_failed"
                return monitor
        return cls(enabled=False, project=project)

    def export(self, recorder: SafeTelemetry) -> bool:
        if not self.enabled:
            if self.last_status not in {"credential_missing", "client_init_failed"}:
                self.last_status = "disabled"
            return False
        if not recorder.events:
            self.last_status = "empty"
            return False
        # Revalidate records at the boundary, including records made by tests.
        try:
            run_id = UUID(recorder.run_id)
            events = list(recorder.events)
            event_ids = {e.span_id: UUID(e.span_id) for e in events if e.span_id}
            if len(event_ids) != sum(bool(e.span_id) for e in events):
                raise ValueError("Duplicate span")
            if run_id in event_ids.values():
                raise ValueError("Duplicate root")
            by_id = {e.span_id: e for e in events if e.span_id}
            depths = {}
            for event in events:
                if event.stage not in STAGES or event.status not in {"ok", "error"}:
                    raise ValueError("Invalid stage")
                if event.parent_span_id and event.parent_span_id not in event_ids:
                    raise ValueError("Missing parent")
                if not math.isfinite(event.duration_ms) or event.duration_ms < 0:
                    raise ValueError("Invalid duration")
                start = datetime.fromisoformat(event.started_at)
                end = datetime.fromisoformat(event.ended_at)
                if start.tzinfo is None or end.tzinfo is None or end < start:
                    raise ValueError("Invalid interval")
                ancestors = set()
                parent_id = event.parent_span_id
                while parent_id:
                    if parent_id == event.span_id or parent_id in ancestors:
                        raise ValueError("Cyclic spans")
                    ancestors.add(parent_id)
                    parent_id = by_id[parent_id].parent_span_id
                depths[id(event)] = len(ancestors)
        except (TypeError, ValueError, AttributeError, KeyError, OverflowError):
            self.last_status = "invalid_record"
            return False
        try:
            root_start = min(datetime.fromisoformat(e.started_at) for e in events)
            root_order = root_start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + str(
                run_id
            )
            orders = {}
            self.client.create_run(
                name="cogniguard.langgraph",
                run_type="chain",
                id=run_id,
                trace_id=run_id,
                dotted_order=root_order,
                inputs={},
                project_name=self.project,
                start_time=root_start,
                extra={"metadata": {"node_count": len(events)}},
            )
            # Parent starts before child even though completed events arrive child-first.
            for event in sorted(events, key=lambda e: (depths[id(e)], e.started_at)):
                child = event_ids[event.span_id] if event.span_id else uuid4()
                start = datetime.fromisoformat(event.started_at)
                order = (
                    orders.get(event.parent_span_id, root_order)
                    + "."
                    + start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    + str(child)
                )
                if event.span_id:
                    orders[event.span_id] = order
                self.client.create_run(
                    name="cogniguard." + event.stage,
                    run_type="llm" if event.stage == "provider.mimo" else "chain",
                    id=child,
                    trace_id=run_id,
                    dotted_order=order,
                    parent_run_id=event_ids.get(event.parent_span_id, run_id),
                    inputs={},
                    project_name=self.project,
                    start_time=start,
                    extra={"metadata": safe_metrics(event.metrics)},
                )
                self.client.update_run(
                    child,
                    trace_id=run_id,
                    dotted_order=order,
                    outputs={},
                    end_time=datetime.fromisoformat(event.ended_at),
                    error="node_failed" if event.status == "error" else None,
                    extra={
                        "metadata": {
                            **safe_metrics(event.metrics),
                            "duration_ms": event.duration_ms,
                        }
                    },
                )
            self.client.update_run(
                run_id,
                trace_id=run_id,
                dotted_order=root_order,
                outputs={},
                end_time=max(datetime.fromisoformat(e.ended_at) for e in events),
                error="execution_failed" if any(e.status == "error" for e in events) else None,
            )
            flush = getattr(self.client, "flush", None)
            if callable(flush):
                try:
                    parameter = inspect.signature(flush).parameters.get("timeout")
                except (TypeError, ValueError):
                    parameter = None
                if parameter is not None and parameter.kind in {
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                }:
                    flush(timeout=0.25)
            # SDK acceptance is not a remote delivery confirmation.
            self.last_status = "submitted"
            return True
        except Exception:
            # Observability failure must not turn into a safety-policy failure.
            # Never log the exception: transport messages may contain headers.
            self.last_status = "export_failed"
            return False
