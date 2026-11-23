"""Education pipeline metering. Receipts stay in memory; the meter is a fake."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy

import pytest

from cogniguard.governance.meter import Measurement
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.protection_context import ProtectionContext, protection_scope
from cogniguard.runtime.sessions import SessionStore
from cogniguard.workflows.pipeline import LangGraphProtectionPipeline
from core.access import AccessScope
from core.pipeline import load_inputs
from core.tests.test_focused import INPUTS

_MISSING = object()
_HELD = ("pack", "held-unit")
_LEAKED = ("pack", "leaked-unit")


class MemoryReceiptStore:
    """Receipt log kept in the process. Reserved and delivered rows both count as held."""

    def __init__(self) -> None:
        self.receipts: list[dict] = []

    @contextmanager
    def release_section(self):
        yield

    def reserve(
        self,
        *,
        resource_id: str,
        unit_id: str,
        recipient_principal_id: str,
        acting_org_id: str,
        agent_principal_id: str,
        session_id: str,
        policy_version: int,
        content: str,
        created_at: float,
        exposure_delta: float = 0.0,
    ) -> str:
        receipt_id = f"r{len(self.receipts) + 1}"
        self.receipts.append(
            {
                "receipt_id": receipt_id,
                "resource_id": resource_id,
                "unit_id": unit_id,
                "recipient_principal_id": recipient_principal_id,
                "content": content,
                "exposure_delta": exposure_delta,
                "status": "reserved",
            }
        )
        return receipt_id

    def commit(self, receipt_id: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = "delivered"

    def cancel(self, receipt_id: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = "cancelled"

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset[tuple[str, str]]]:
        held: dict[str, set[tuple[str, str]]] = {}
        for row in self.receipts:
            if row["status"] not in ("reserved", "delivered"):
                continue
            pair = (row["resource_id"], row["unit_id"])
            if pair not in units:
                continue
            held.setdefault(row["recipient_principal_id"], set()).add(pair)
        return {name: frozenset(pairs) for name, pairs in held.items()}

    def hold(self, recipient: str, resource_id: str, unit_id: str) -> None:
        receipt_id = self.reserve(
            resource_id=resource_id,
            unit_id=unit_id,
            recipient_principal_id=recipient,
            acting_org_id="legacy",
            agent_principal_id="graph-runtime",
            session_id="already-held",
            policy_version=0,
            content="held outside this answer",
            created_at=1.0,
            exposure_delta=1.0,
        )
        self.commit(receipt_id)


class FakeMeter:
    def __init__(
        self,
        units: frozenset[tuple[str, str]] = frozenset(),
        *,
        method: str = "fake-v1",
        fail: bool = False,
    ) -> None:
        self._units = units
        self._method = method
        self._fail = fail
        self.calls = 0
        self.texts: list[str] = []
        self.scopes: list[frozenset[tuple[str, str]]] = []

    def measure(self, text: str, *, candidate_units: frozenset[tuple[str, str]]) -> Measurement:
        self.calls += 1
        self.texts.append(text)
        self.scopes.append(candidate_units)
        if self._fail:
            raise RuntimeError("meter failed")
        return Measurement(units=self._units, method=self._method)


@pytest.fixture(scope="module")
def case():
    config, profiles, questions, resources = load_inputs(*INPUTS)
    question = next(item for item in questions if item["need_resource"])
    profile = deepcopy(profiles[question["student_id"]])
    baseline = LangGraphProtectionPipeline(config, resources).run(
        profile, question, access=AccessScope(profile.student_id)
    )
    return config, profile, question, deepcopy(baseline.controlled.resource)


def _student(profile, question, student_id: str):
    profile = deepcopy(profile)
    question = deepcopy(question)
    profile.student_id = student_id
    question["student_id"] = student_id
    return profile, question


def _prepare(config, resource, *, mode: str, chunk_id: str):
    config = deepcopy(config)
    resource = deepcopy(resource)
    resource.resource_id = "pack"
    resource.chunk_id = chunk_id
    rules = dict(config["c2rag"]["disclosure_rule"])
    thresholds = dict(config["c2rag"]["thresholds"])
    if mode == "summary":
        resource.policy.allow_quote = False
        resource.policy.allow_variant = False
        resource.policy.allow_summary = True
        resource.copyright_level = 0.5
        thresholds["summary"] = 1.0
        rules["summary"] = False
        config["c2rag"]["high_copyright_threshold"] = 2.0
    else:
        resource.policy.allow_quote = True
        resource.policy.allow_summary = False
        resource.policy.allow_variant = False
        resource.copyright_level = 0.1
        thresholds["quote"] = 1.0
        rules["quote"] = True
        config["c2rag"]["quote_copyright_threshold"] = 1.0
    config["c2rag"]["disclosure_rule"] = rules
    config["c2rag"]["thresholds"] = thresholds
    return config, resource


def _witness(*units: tuple[str, str]) -> TargetRegistry:
    return TargetRegistry([ProtectedTarget("goal", "owner", "org", (frozenset(units),))])


def _rows(store: MemoryReceiptStore) -> list[tuple]:
    return [
        (row["resource_id"], row["unit_id"], row["recipient_principal_id"], row["status"])
        for row in store.receipts
    ]


def _run(config, profile, question, resource, store, student_id: str, **kwargs):
    pipeline = LangGraphProtectionPipeline(
        config, [resource], disclosure_store=store, **kwargs
    )
    student, ask = _student(profile, question, student_id)
    result = pipeline.run(student, ask, access=AccessScope(student.student_id))
    return result


def _retrieval_scope(result) -> frozenset[tuple[str, str]]:
    trace = result.controlled.source_trace["retrieval_trace"]
    return frozenset((item["resource_id"], item["chunk_id"]) for item in trace)


def _without_timestamp(result) -> dict:
    trace = deepcopy(result.controlled.source_trace)
    trace.pop("timestamp", None)
    return trace


def test_explicit_none_matches_the_omitted_meter(case) -> None:
    config, profile, question, resource = case
    resource = deepcopy(resource)
    resource.resource_id = "pack"
    resource.chunk_id = "same-unit"
    registry = _witness(("pack", "same-unit"), ("pack", "other-unit"))

    def run(meter=_MISSING):
        store = MemoryReceiptStore()
        kwargs = {
            "disclosure_store": store,
            "target_registry": registry,
            "coalition_k": 2,
        }
        if meter is not _MISSING:
            kwargs["meter"] = meter
        pipeline = LangGraphProtectionPipeline(deepcopy(config), [deepcopy(resource)], **kwargs)
        student, ask = _student(profile, question, "student-same")
        result = pipeline.run(student, ask, access=AccessScope(student.student_id))
        return result, store

    plain, plain_store = run()
    named, named_store = run(None)

    assert plain.controlled.mode == named.controlled.mode
    assert plain.controlled.text == named.controlled.text
    assert plain.answer == named.answer
    assert _without_timestamp(plain) == _without_timestamp(named)
    assert _rows(plain_store) == _rows(named_store)
    check = plain.controlled.source_trace["coalition_check"]
    assert "meter_method" not in check
    assert "metered_unit_count" not in check
    assert check == named.controlled.source_trace["coalition_check"]


def test_summary_rule_cannot_hide_a_metered_unit(case) -> None:
    config, profile, question, resource = case
    config, resource = _prepare(config, resource, mode="summary", chunk_id="leaked-unit")
    store = MemoryReceiptStore()
    store.hold("student-a", *_HELD)
    meter = FakeMeter(frozenset({_LEAKED}))
    result = _run(
        config,
        profile,
        question,
        resource,
        store,
        "student-b",
        target_registry=_witness(_HELD, _LEAKED),
        coalition_k=2,
        meter=meter,
    )
    evidence = result.controlled.source_trace["coalition_check"]

    assert meter.calls == 1
    assert meter.scopes == [_retrieval_scope(result)]
    assert meter.texts[0].startswith("资源摘要")
    assert result.controlled.mode == "refuse"
    assert evidence == {
        "target_count": 1,
        "violation_count": 1,
        "decision": "refuse",
        "selected": "refuse",
        "accepted_count": 1,
        "meter_method": "fake-v1",
        "metered_unit_count": 1,
    }
    assert _rows(store) == [("pack", "held-unit", "student-a", "delivered")]
    rendered = repr(evidence)
    assert resource.content not in rendered
    assert "leaked-unit" not in rendered
    assert "held-unit" not in rendered


def test_empty_meter_releases_a_quote_without_a_receipt(case) -> None:
    config, profile, question, resource = case
    config, resource = _prepare(config, resource, mode="quote", chunk_id="quoted-unit")
    store = MemoryReceiptStore()
    meter = FakeMeter(frozenset())
    result = _run(
        config,
        profile,
        question,
        resource,
        store,
        "student-quote",
        target_registry=_witness(("pack", "quoted-unit")),
        coalition_k=2,
        meter=meter,
    )
    evidence = result.controlled.source_trace["coalition_check"]

    assert result.controlled.mode == "quote"
    assert meter.calls == 1
    assert meter.scopes == [_retrieval_scope(result)]
    assert store.receipts == []
    assert evidence == {
        "target_count": 0,
        "violation_count": 0,
        "decision": "release",
        "selected": "quote",
        "accepted_count": 2,
        "meter_method": "fake-v1",
        "metered_unit_count": 0,
    }
    rendered = repr(evidence)
    assert "quoted-unit" not in rendered
    assert resource.content not in rendered
    assert result.controlled.text not in rendered


def test_meter_failure_refuses_without_a_receipt(case) -> None:
    config, profile, question, resource = case
    config, resource = _prepare(config, resource, mode="quote", chunk_id="quoted-unit")
    meter = FakeMeter(fail=True)
    store = MemoryReceiptStore()
    result = _run(
        config,
        profile,
        question,
        resource,
        store,
        "student-fail",
        target_registry=_witness(("pack", "quoted-unit")),
        coalition_k=2,
        meter=meter,
    )

    assert meter.calls == 1
    assert result.controlled.mode == "refuse"
    assert result.controlled.text.startswith("该资料当前不适合")
    assert store.receipts == []
    assert result.controlled.source_trace["coalition_check"]["meter_error"] is True

    reserve_store = MemoryReceiptStore()
    reserve_meter = FakeMeter(fail=True)
    reserve_config, reserve_resource = _prepare(
        case[0], case[3], mode="quote", chunk_id="quoted-unit"
    )
    reserved = _run(
        reserve_config,
        profile,
        question,
        reserve_resource,
        reserve_store,
        "student-fail-reserve",
        meter=reserve_meter,
    )

    assert reserve_meter.calls == 1
    assert reserved.controlled.mode == "refuse"
    assert reserve_store.receipts == []
    assert reserved.controlled.source_trace["coalition_check"]["meter_error"] is True


def test_reserve_uses_metered_units_when_no_witness_is_registered(case) -> None:
    config, profile, question, resource = case
    config, resource = _prepare(config, resource, mode="summary", chunk_id="visible-chunk")
    store = MemoryReceiptStore()
    meter = FakeMeter(frozenset({("pack", "metered-secret-unit")}))
    result = _run(
        config,
        profile,
        question,
        resource,
        store,
        "student-reserve",
        meter=meter,
    )
    evidence = repr(result.controlled.source_trace.get("coalition_check", {}))

    assert meter.calls == 1
    assert meter.scopes == [_retrieval_scope(result)]
    assert _rows(store) == [("pack", "metered-secret-unit", "student-reserve", "delivered")]
    assert store.receipts[0]["content"] == result.controlled.text
    assert "metered-secret-unit" not in evidence
    assert "visible-chunk" not in evidence
    assert resource.content not in evidence


def test_meter_failure_refuses_before_budget_or_approval(case, tmp_path) -> None:
    config, profile, question, resource = case
    config, resource = _prepare(config, resource, mode="quote", chunk_id="quoted-unit")
    resource.content = "CHUNK-SECRET-9f3a"
    resource.policy.max_quote_len = len(resource.content)
    store = MemoryReceiptStore()
    meter = FakeMeter(fail=True)
    session = SessionStore(
        tmp_path / "meter-fail.sqlite3",
        limits={"privacy": 100, "copyright": 10},
    ).get_or_create()
    context = ProtectionContext(session, "meter-fail", "test", {})
    copyright_before = session.budget("copyright")
    pipeline = LangGraphProtectionPipeline(
        config, [resource], disclosure_store=store, meter=meter
    )
    student, ask = _student(profile, question, "student-early-refuse")
    with protection_scope(context):
        result = pipeline.run(student, ask, access=AccessScope(student.student_id))

    assert store.receipts == []
    assert resource.content not in result.controlled.text
    assert resource.content not in result.answer
    assert context.approved_chunks == []
    assert session.budget("copyright") == copyright_before
    assert result.controlled.source_trace["coalition_check"]["meter_error"] is True
