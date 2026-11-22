"""Fine-grained graph execution of the existing offline protection pipeline.

Sensitive objects live only in per-call Runtime context, not graph channels.
No checkpointing or automatic retries: domain budget commits are side effects.
"""

from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from cogniguard.governance.evidence import (
    ContextBoundary,
    DomainEvidence,
    EvidenceEnvelope,
    Principal,
    Purpose,
)
from cogniguard.observability.telemetry import (
    LangSmithMonitor,
    SafeTelemetry,
    active_recorder,
    request_observation,
)
from cogniguard.protection.retrieval import inspect_candidate_resources
from cogniguard.runtime.protection_context import (
    charge_domain_budget,
    register_profile_context,
    register_retrieval_context,
)
from core.access import AccessScope
from core.domain import DomainServices, ProtectionResult
from core.teaching import build_teaching_input, generate_offline_answer
from protection.student_profile.src.fopd.context_card import build_context_card
from protection.student_profile.src.fopd.task_parser import parse_task
from protection.student_profile.src.pipeline.ag2_simulator import build_ag2_request
from protection.teacher_resource.src.c2rag.retriever import CopyrightAwareRetriever
from protection.teacher_resource.src.c2rag.return_policy import produce_controlled_resource


@dataclass
class AdapterProtectionResult(ProtectionResult):
    """Do not mislabel an injected generator as the built-in offline rule."""

    def to_dict(self):
        return {**super().to_dict(), "execution_mode": "adapter_supplied"}


class ExecutionState(TypedDict, total=False):
    run_id: str
    stage: str
    resource_required: bool
    selected_count: int
    candidate_count: int
    privacy_before: float
    privacy_after: float
    privacy_exhausted: bool
    resource_exposure: float
    watermark_enabled: bool
    governance_enabled: bool
    blocked: bool
    completed: bool
    decision_code: int


@dataclass
class ProtectedText:
    text: str
    provenance_valid: bool = True
    evidence: dict = field(default_factory=dict)


@dataclass
class Frame:
    owner: "LangGraphProtectionPipeline"
    profile: Any
    question: dict
    access: AccessScope
    recorder: SafeTelemetry
    task: Any = None
    selected: list = field(default_factory=list)
    card: str = ""
    retrieved: list = field(default_factory=list)
    retrieval_evidence: dict = field(default_factory=dict)
    controlled: Any = None
    privacy: dict = field(default_factory=dict)
    teaching: Any = None
    answer: str = ""
    protected: ProtectedText | None = None
    result: ProtectionResult | None = None
    disclosure_receipt_ids: list = field(default_factory=list)
    disclosure_committed: list = field(default_factory=list)
    disclosure_cancelled: list = field(default_factory=list)
    disclosure_settled: bool = False


@dataclass
class RunContext:
    frame: Frame


def stage(name):
    def decorate(fn):
        def invoke(state: ExecutionState, runtime: Runtime[RunContext]):
            frame = runtime.context.frame
            with frame.recorder.span(name) as metrics:
                update = fn(frame, state) or {}
                metrics.update(update)
                return {"stage": name, **update}

        # Keep the actual (state, runtime) signature visible to LangGraph.
        invoke.__name__ = name
        return invoke

    return decorate


@stage("authorize")
def authorize(f, state):
    f.task = parse_task(f.question)
    f.access.authorize(f.profile, f.task)
    if f.owner._subject is not None and f.owner._subject != f.profile.student_id:
        raise PermissionError("Create a fresh pipeline for another student/session")
    f.owner._subject = f.profile.student_id
    f.owner.round_number += 1
    return {"resource_required": bool(f.task.need_resource)}


@stage("minimize_profile")
def minimize_profile(f, state):
    f.selected = f.owner.selector.select(f.owner.profile_policy.filter(f.profile), f.task)
    f.card, _ = build_context_card(f.profile, f.task, f.selected)
    register_profile_context(
        profile=f.profile, approved_context=f.card, selected_records=f.selected
    )
    return {"selected_count": len(f.selected)}


@stage("retrieve")
def retrieve(f, state):
    if f.access.registry is not None:
        now = time.time()
        allowed = [r for r in f.owner.resources if f.access.permits(r.resource_id, now)]
        retriever = CopyrightAwareRetriever(allowed, f.owner.budget, f.owner.config)
    else:
        retriever = f.owner.retriever
        if f.access.resource_ids is not None:
            allowed = [r for r in f.owner.resources if r.resource_id in f.access.resource_ids]
            retriever = CopyrightAwareRetriever(allowed, f.owner.budget, f.owner.config)
    retrieved = retriever.retrieve(build_ag2_request(f.task, f.card), f.task, f.card)
    inspection = inspect_candidate_resources(
        [item.resource for item in retrieved], guard=f.owner.retrieval_guard
    )
    f.retrieval_evidence = dict(inspection.evidence)
    # Inspection precedes the single C2-RAG release/budget/source-trace commit.
    f.retrieved = [
        type(item)(resource, item.score, deepcopy(item.components))
        for item, resource in zip(retrieved, inspection.resources)
    ]
    return {"candidate_count": len(f.retrieved)}


@stage("control_resource")
def control_resource(f, state):
    if f.retrieved:
        trace = [
            {
                "rank": rank,
                "resource_id": item.resource.resource_id,
                "chunk_id": item.resource.chunk_id,
                "score": item.score,
                "components": item.components,
            }
            for rank, item in enumerate(f.retrieved, 1)
        ]
        f.controlled = produce_controlled_resource(
            f.retrieved[0].resource, f.owner.budget, f.owner.config, retrieval_trace=trace
        )
    released = []
    if f.controlled is not None and f.controlled.mode != "refuse":
        charge_domain_budget(
            "copyright", max(0.0, f.controlled.exposure_after - f.controlled.exposure_before)
        )
        released.append(
            {
                "resource_id": f.controlled.resource.resource_id,
                "chunk_id": f.controlled.resource.chunk_id,
                "content": f.controlled.text,
                "return_mode": f.controlled.mode,
            }
        )
    register_retrieval_context(
        protected_resources=f.owner.resources,
        approved_chunks=released,
        approved_source_ids=[item["resource_id"] for item in released],
        evidence=f.retrieval_evidence,
    )
    if f.owner.disclosure_store is not None:
        _reserve_disclosures(f, released)
    return {"resource_exposure": float(f.controlled.exposure_after) if f.controlled else 0.0}


@stage("measure_privacy")
def measure_privacy(f, state):
    f.privacy = f.owner.privacy_ledger.measure_and_commit(
        f.profile, [x.record.record_id for x in f.selected], f.card
    ).to_dict()
    if f.privacy["budget_exhausted"]:
        from cogniguard.runtime.protection_context import active_protection
        from cogniguard.runtime.sessions import BudgetExceeded

        if active_protection() is not None:
            raise BudgetExceeded("MM-FOPD profile release budget exhausted")
    charge_domain_budget("privacy", float(f.privacy["released_exposure"]))
    return {
        "privacy_before": f.privacy["budget_before"],
        "privacy_after": f.privacy["budget_after"],
        "privacy_exhausted": f.privacy["budget_exhausted"],
    }


@stage("prepare_teaching")
def prepare_teaching(f, state):
    f.teaching = build_teaching_input(f.task, f.card, f.controlled, f.profile.local_only_fields)


def guard_envelope(f, *, output=False):
    controlled = f.controlled
    source_valid = (
        controlled is None
        or controlled.resource is None
        or any(
            r.resource_id == controlled.resource.resource_id
            and r.chunk_id == controlled.resource.chunk_id
            for r in f.owner.resources
        )
    )
    if output and f.protected is not None:
        source_valid = source_valid and f.protected.provenance_valid
    knowledge_exhausted = bool(
        controlled
        and controlled.resource
        and controlled.exposure_after > controlled.resource.policy.max_exposure + 1e-9
    )
    # No attack labels, target descriptions, expected decisions, or oracle scores.
    evidence = {
        "privacy": DomainEvidence(
            "privacy",
            0.0,
            actual_cost=f.privacy["released_exposure"],
            constraints={"budget_exhausted": f.privacy["budget_exhausted"]},
        ),
        "knowledge": DomainEvidence(
            "knowledge", 0.0, constraints={"budget_exhausted": knowledge_exhausted}
        ),
        "provenance": DomainEvidence("provenance", 0.0, provenance={"valid": source_valid}),
    }
    return EvidenceEnvelope(
        f.recorder.run_id,
        f.owner.session_id,
        str(f.owner.round_number),
        Principal("graph-runtime", "service"),
        "delivery" if output else "teaching",
        Purpose("education"),
        ContextBoundary("langgraph-runtime", "authenticated", False),
        payload={},
        evidence=evidence,
    )


@stage("govern_input")
def govern_input(f, state):
    if f.owner.guard is None:
        return {"governance_enabled": False, "blocked": False}
    decision = f.owner.guard.evaluate(guard_envelope(f), audit_valid=f.owner.guard.audit.verify())
    # A sanitize/degrade recommendation is not executable without a domain
    # transform adapter. Fail closed rather than silently returning raw payload.
    codes = {"allow": 0, "sanitize": 1, "degrade": 2, "quarantine": 3, "refuse": 4, "block": 5}
    return {
        "governance_enabled": True,
        "blocked": decision.action != "allow",
        "decision_code": codes[decision.action],
    }


@stage("generate")
def generate(f, state):
    f.answer = (f.owner.generator or generate_offline_answer)(f.teaching)
    if not isinstance(f.answer, str):
        raise TypeError("Teaching generator must return a string")


@stage("watermark")
def watermark(f, state):
    if f.owner.watermark is None:
        return {"watermark_enabled": False}
    safe_task = deepcopy(f.task)
    safe_task.question, safe_task.knowledge, safe_task.difficulty = (
        f.teaching.question,
        f.teaching.knowledge,
        f.teaching.difficulty,
    )
    protected = f.owner.watermark(
        f.answer, safe_task, f.controlled.source_trace if f.controlled else {}
    )
    if not isinstance(protected, ProtectedText) or not isinstance(protected.text, str):
        raise TypeError("Watermark adapter must return ProtectedText")
    if not isinstance(protected.provenance_valid, bool):
        raise TypeError("Watermark provenance validity must be boolean")
    f.protected = protected
    f.answer = protected.text
    return {"watermark_enabled": True}


@stage("govern_output")
def govern_output(f, state):
    if f.owner.guard is None:
        return {"blocked": False}
    decision = f.owner.guard.evaluate(
        guard_envelope(f, output=True), audit_valid=f.owner.guard.audit.verify()
    )
    codes = {"allow": 0, "sanitize": 1, "degrade": 2, "quarantine": 3, "refuse": 4, "block": 5}
    return {"blocked": decision.action != "allow", "decision_code": codes[decision.action]}


def _policy_version(f, resource_id: str) -> int:
    registry = f.access.registry
    if registry is None:
        return 0
    ownership = registry.owner_of(resource_id)
    if ownership is None:
        return 0
    return ownership.policy_version


def _reserve_disclosures(f, released: list[dict]) -> None:
    store = f.owner.disclosure_store
    acting_org_id = "legacy" if f.access.acting_org_id is None else f.access.acting_org_id
    for item in released:
        receipt_id = store.reserve(
            resource_id=item["resource_id"],
            unit_id=item["chunk_id"],
            recipient_principal_id=f.profile.student_id,
            acting_org_id=acting_org_id,
            agent_principal_id="graph-runtime",
            session_id=f.owner.session_id,
            policy_version=_policy_version(f, item["resource_id"]),
            content=item["content"],
            created_at=time.time(),
        )
        f.disclosure_receipt_ids.append(receipt_id)


def _commit_disclosures(f) -> None:
    store = f.owner.disclosure_store
    if store is None or f.disclosure_settled:
        return
    for receipt_id in f.disclosure_receipt_ids:
        store.commit(receipt_id)
        f.disclosure_committed.append(receipt_id)
    f.disclosure_settled = True


def _cancel_disclosures(f) -> None:
    store = f.owner.disclosure_store
    if store is None or f.disclosure_settled:
        return
    committed = set(f.disclosure_committed)
    pending = [
        receipt_id
        for receipt_id in f.disclosure_receipt_ids
        if receipt_id not in committed and receipt_id not in f.disclosure_cancelled
    ]
    for receipt_id in pending:
        store.cancel(receipt_id)
        f.disclosure_cancelled.append(receipt_id)
    f.disclosure_settled = True


@stage("finalize")
def finalize(f, state):
    if state.get("blocked"):
        # Output or input governance refused delivery. Drop the reserved receipts.
        _cancel_disclosures(f)
        # Do not return a diagnostic ProtectionResult with rejected content.
        return {"completed": False}
    result_type = (
        AdapterProtectionResult
        if f.owner.generator is not None or f.owner.watermark is not None
        else ProtectionResult
    )
    f.result = result_type(
        f.task, f.card, f.selected, f.controlled, f.answer, f.privacy, f.teaching
    )
    # govern_output has already passed. This is the completed delivery.
    _commit_disclosures(f)
    return {"completed": True}


def build_graph():
    graph = StateGraph(ExecutionState, context_schema=RunContext)
    nodes = {
        name: globals()[name]
        for name in (
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
        )
    }
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.add_edge(START, "authorize")
    graph.add_edge("authorize", "minimize_profile")
    graph.add_conditional_edges(
        "minimize_profile",
        lambda s: "resource" if s["resource_required"] else "privacy",
        {"resource": "retrieve", "privacy": "measure_privacy"},
    )
    graph.add_edge("retrieve", "control_resource")
    graph.add_edge("control_resource", "measure_privacy")
    graph.add_edge("measure_privacy", "prepare_teaching")
    graph.add_edge("prepare_teaching", "govern_input")
    graph.add_conditional_edges(
        "govern_input",
        lambda s: "stop" if s["blocked"] else "continue",
        {"stop": "finalize", "continue": "generate"},
    )
    graph.add_edge("generate", "watermark")
    graph.add_edge("watermark", "govern_output")
    graph.add_edge("govern_output", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=False, name="CogniGuardProtection")


class LangGraphProtectionPipeline(DomainServices):
    """One object per authorized session, preserving legacy algorithm behavior.

    The default is parity mode (no additional governance/watermark). Optional
    hooks must be supplied by trusted application code, never by task text.
    """

    def __init__(
        self,
        config,
        resources,
        *,
        guard=None,
        watermark: Callable | None = None,
        generator: Callable | None = None,
        monitor: LangSmithMonitor | None = None,
        retrieval_guard=None,
        disclosure_store=None,
    ):
        super().__init__(deepcopy(config), list(resources))
        self.guard, self.watermark = guard, watermark
        self.retrieval_guard = retrieval_guard
        self.disclosure_store = disclosure_store
        self.generator = generator
        self.monitor = monitor or LangSmithMonitor()
        self.graph = build_graph()
        self.lock = RLock()
        self.session_id = SafeTelemetry().run_id
        self.round_number = 0
        self.last_trace = {}
        self.last_state = {}
        self._subject = None

    def run(self, profile, question, *, access: AccessScope):
        with self.lock:
            outer = active_recorder()
            recorder = outer or SafeTelemetry()
            frame = Frame(self, deepcopy(profile), deepcopy(question), access, recorder)
            self.last_state = {}
            try:
                with request_observation(recorder):
                    self.last_state = self.graph.invoke(
                        {"run_id": recorder.run_id}, context=RunContext(frame)
                    )
                if frame.result is None:
                    raise PermissionError("Governance blocked delivery")
                return frame.result
            except Exception:
                # A node failed before finalize could settle the reserved receipts.
                _cancel_disclosures(frame)
                raise
            finally:
                self.last_trace = recorder.to_dict()
                if outer is None:
                    self.monitor.export(recorder)
                # Frame is call-local; checkpoints never contain its contents.
