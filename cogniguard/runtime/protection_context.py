"""Trusted request context shared by domain nodes; never a LangGraph channel."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass
class ProtectionContext:
    session: Any
    request_id: str
    surface: str
    state: dict[str, Any]
    private_values: set[str] = field(default_factory=set)
    protected_resources: list[dict[str, Any]] = field(default_factory=list)
    approved_chunks: list[dict[str, Any]] = field(default_factory=list)
    approved_source_ids: set[str] = field(default_factory=set)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    sequence: int = 0
    nemo_colang: Any = None

    def charge(self, budget: str, amount: float, *, key: str | None = None) -> None:
        from cogniguard.observability import active_recorder

        self.sequence += 1
        recorder = active_recorder()
        span = recorder.span("gateway.budget") if recorder is not None else nullcontext({})
        with span as metrics:
            reservation = self.session.reserve(
                budget, amount, self.request_id, key=key or f"{budget}:{self.sequence}"
            )
            reservation.commit()
            metrics["validated"] = True


_active: ContextVar[ProtectionContext | None] = ContextVar("cgc_protection_context", default=None)
_transport_token: ContextVar[str | None] = ContextVar("cgc_transport_session", default=None)
_transport_request: ContextVar[str | None] = ContextVar("cgc_transport_request", default=None)
_transport_sink: ContextVar[Callable[[str], None] | None] = ContextVar(
    "cgc_session_sink", default=None
)


def active_protection() -> ProtectionContext | None:
    return _active.get()


@contextmanager
def protection_scope(context: ProtectionContext):
    token = _active.set(context)
    try:
        yield context
    finally:
        _active.reset(token)


@contextmanager
def transport_scope(token: str | None, request_id: str | None, sink: Callable[[str], None]):
    values = (
        _transport_token.set(token),
        _transport_request.set(request_id),
        _transport_sink.set(sink),
    )
    try:
        yield
    finally:
        _transport_token.reset(values[0])
        _transport_request.reset(values[1])
        _transport_sink.reset(values[2])


def transport_credentials() -> tuple[str | None, str | None]:
    return _transport_token.get(), _transport_request.get()


def publish_session_token(token: str) -> None:
    sink = _transport_sink.get()
    if sink is not None:
        _transport_token.set(token)
        sink(token)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value)) if hasattr(value, "__dict__") else {}


def _strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if value.strip() else set()
    if isinstance(value, int) and not isinstance(value, bool) and len(str(abs(value))) >= 6:
        return {str(value)}
    if isinstance(value, Mapping):
        return set().union(*(_strings(v) for v in value.values()), set())
    if isinstance(value, (list, tuple, set)):
        return set().union(*(_strings(v) for v in value), set())
    return set()


def register_profile_context(
    *,
    profile: Any = None,
    approved_context: Any = None,
    selected_records: Iterable[Any] = (),
    private_values: Iterable[str] = (),
) -> None:
    frame = active_protection()
    if frame is None:
        return
    raw = _mapping(profile)
    frame.private_values.update(str(value) for value in private_values if value)
    private_keys = {
        "local_only_fields",
        "raw_multimodal_data",
        "raw_student_data",
        "raw_profile",
        "raw_multimodal_profile",
        "raw_screenshot",
        "wrong_answer_image_path",
        "handwriting_trace",
        "audio_features",
        "emotion_signals",
        "address",
        "email",
        "phone",
        "real_name",
        "student_name",
        "student_id",
        "learner_id",
        "student_number",
        "account",
        "account_number",
        "full_learning_history",
    }

    def walk(mapping):
        for key, value in mapping.items():
            if key in private_keys:
                frame.private_values.update(_strings(value))
            elif isinstance(value, Mapping):
                walk(value)

    walk(raw)
    approved = _strings(approved_context)
    selected = {
        _mapping(_mapping(item).get("record", item)).get("record_id") for item in selected_records
    }
    for record in raw.get("profile_records", []):
        row = _mapping(record)
        if row.get("record_id") not in selected:
            frame.private_values.update(_strings(row.get("value")) - approved)
    frame.evidence.append(
        {"stage": "input", "owner": "MM-FOPD", "private_value_count": len(frame.private_values)}
    )


def register_retrieval_context(
    *,
    protected_resources: Iterable[Any] = (),
    approved_chunks: Iterable[Mapping] = (),
    approved_source_ids: Iterable[str] = (),
    evidence: Mapping | None = None,
) -> None:
    frame = active_protection()
    if frame is None:
        return
    frame.protected_resources.extend(deepcopy(_mapping(item)) for item in protected_resources)
    frame.approved_chunks.extend(deepcopy(_mapping(item)) for item in approved_chunks)
    frame.approved_source_ids.update(str(value) for value in approved_source_ids if value)
    for item in frame.approved_chunks:
        for key in ("resource_id", "chunk_id"):
            if item.get(key):
                frame.approved_source_ids.add(str(item[key]))
    frame.evidence.append({"stage": "retrieval", "owner": "C2-RAG", **dict(evidence or {})})


def charge_domain_budget(budget: str, amount: float, *, key: str | None = None) -> None:
    frame = active_protection()
    if frame is not None and amount > 0:
        frame.charge(budget, float(amount), key=key)


def authorize_image_generation(count: int) -> None:
    frame = active_protection()
    if frame is not None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("Image count must be a positive integer")
        frame.charge("images", count)
        frame.evidence.append(
            {
                "stage": "execution",
                "owner": "CGC",
                "action": "generate_teaching_image",
                "count": count,
            }
        )
