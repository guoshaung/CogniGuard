"""ReleaseGate metering uses an in-memory receipt store. No MySQL."""

from __future__ import annotations

from contextlib import contextmanager

from cogniguard.governance.access_policy import AccessRegistry
from cogniguard.governance.meter import Measurement
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.meters import LexicalMeter, UnitContentStore
from cogniguard.runtime.release_gate import (
    Candidate,
    GateDecision,
    ReleaseGate,
    ReleaseRequest,
    UnitRelease,
)

_SECRET = "needs-step-free-access"
_LEAKED = ("doc", "leaked")
_HELD = ("doc", "held")


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
            acting_org_id="school",
            agent_principal_id="agent-1",
            session_id="already-held",
            policy_version=0,
            content="held outside the candidate",
            created_at=1.0,
            exposure_delta=1.0,
        )
        self.commit(receipt_id)


class FakeMeter:
    def __init__(
        self,
        units: frozenset[tuple[str, str]] = frozenset(),
        *,
        method: str = "fake",
        fail_on: str | None = None,
    ) -> None:
        self._units = units
        self._method = method
        self._fail_on = fail_on
        self.calls = 0
        self.scopes: list[frozenset[tuple[str, str]]] = []
        self.locked: list[bool] = []
        self.gate: ReleaseGate | None = None

    def measure(self, text: str, *, candidate_units: frozenset[tuple[str, str]]) -> Measurement:
        self.calls += 1
        self.scopes.append(candidate_units)
        if self.gate is not None:
            self.locked.append(self.gate._lock.locked())
        if self._fail_on is not None and text == self._fail_on:
            raise RuntimeError("meter failed")
        return Measurement(units=self._units, method=self._method)


def _request(
    units: tuple[UnitRelease, ...] = (),
    *,
    text: str | None = None,
    scope: frozenset[tuple[str, str]] | None = None,
    recipient: str = "student-b",
) -> ReleaseRequest:
    return ReleaseRequest(
        recipient_principal_id=recipient,
        acting_org_id="school",
        agent_principal_id="agent-1",
        session_id="session-1",
        purpose="tutoring",
        units=units,
        now=10.0,
        text=text,
        meter_scope=frozenset() if scope is None else scope,
    )


def _kept(store: MemoryReceiptStore) -> list[tuple]:
    return [
        (
            row["resource_id"],
            row["unit_id"],
            row["recipient_principal_id"],
            row["content"],
            row["exposure_delta"],
            row["status"],
        )
        for row in store.receipts
    ]


def _lexical(contents: dict[tuple[str, str], str]) -> LexicalMeter:
    return LexicalMeter(UnitContentStore(contents))


def _witness_gate(store: MemoryReceiptStore, meter) -> ReleaseGate:
    witness = frozenset({_HELD, _LEAKED})
    targets = TargetRegistry([ProtectedTarget("goal", "owner", "org", (witness,))])
    return ReleaseGate(store, target_registry=targets, coalition_k=2, meter=meter)


def test_text_is_ignored_when_no_meter_is_configured() -> None:
    unit = UnitRelease("doc", "u1", "chapter text", 0.25)
    plain_store = MemoryReceiptStore()
    text_store = MemoryReceiptStore()
    plain = ReleaseGate(plain_store).evaluate_and_reserve(_request((unit,)))
    text = ReleaseGate(text_store).evaluate_and_reserve(
        _request((unit,), text="should not be measured", scope=frozenset({("doc", "hidden")}))
    )

    assert plain.allowed is True and text.allowed is True
    assert plain.reason == text.reason == "ok"
    assert plain.evidence == text.evidence == {}
    assert _kept(plain_store) == _kept(text_store) == [
        ("doc", "u1", "student-b", "chapter text", 0.25, "reserved")
    ]

    plain_candidate = Candidate("answer", (unit,), 1.0)
    text_candidate = Candidate(
        "answer",
        (unit,),
        1.0,
        text="should not be measured",
        meter_scope=frozenset({("doc", "hidden")}),
    )
    select_plain = MemoryReceiptStore()
    select_text = MemoryReceiptStore()
    plain_choice, plain_decision = ReleaseGate(select_plain).select_and_reserve(
        _request(), [plain_candidate]
    )
    text_choice, text_decision = ReleaseGate(select_text).select_and_reserve(
        _request(), [text_candidate]
    )

    assert plain_choice is plain_candidate
    assert text_choice is text_candidate
    assert plain_decision.evidence == text_decision.evidence == {
        "candidate_count": 1,
        "accepted_count": 1,
        "selected": "answer",
    }
    assert _kept(select_plain) == _kept(select_text)


def test_metered_text_joins_the_coalition_check() -> None:
    meter = _lexical({_LEAKED: _SECRET})
    alone = MemoryReceiptStore()
    allowed = _witness_gate(alone, meter).evaluate_and_reserve(
        _request(text=_SECRET, scope=frozenset({_LEAKED}))
    )
    assert allowed.allowed is True
    assert [row["unit_id"] for row in alone.receipts] == ["leaked"]

    shared = MemoryReceiptStore()
    shared.hold("student-a", *_HELD)
    denied = _witness_gate(shared, meter).evaluate_and_reserve(
        _request(text=_SECRET, scope=frozenset({_LEAKED}))
    )

    assert denied.allowed is False
    assert denied.reason == "reconstruction"
    assert denied.receipt_ids == ()
    assert denied.evidence == {
        "target_count": 1,
        "violation_count": 1,
        "meter_method": "lexical-v1",
        "metered_unit_count": 1,
    }
    assert [row["recipient_principal_id"] for row in shared.receipts] == ["student-a"]


def test_declared_and_metered_units_keep_a_stable_union() -> None:
    text = "candidate wording"
    declared = (
        UnitRelease("m-res", "z", "kept-z", 0.2),
        UnitRelease("m-res", "a", "kept-a", 0.2),
    )
    scope = frozenset({("a-res", "9"), ("z-res", "1")})
    found = frozenset({("m-res", "a"), ("z-res", "1"), ("a-res", "9")})
    meter = FakeMeter(found, method="scripted")
    store = MemoryReceiptStore()
    decision = ReleaseGate(store, meter=meter).evaluate_and_reserve(
        _request(declared, text=text, scope=scope)
    )

    assert meter.scopes == [scope | {("m-res", "z"), ("m-res", "a")}]
    assert decision.evidence == {"meter_method": "scripted", "metered_unit_count": 3}
    assert _kept(store) == [
        ("m-res", "z", "student-b", "kept-z", 0.2, "reserved"),
        ("m-res", "a", "student-b", "kept-a", 0.2, "reserved"),
        ("a-res", "9", "student-b", text, 1.0, "reserved"),
        ("z-res", "1", "student-b", text, 1.0, "reserved"),
    ]


def test_metered_unit_requires_authorization() -> None:
    unit = ("secret-doc", "body")
    registry = AccessRegistry(
        [AssetOwnership("secret-doc", "teacher-a", "school", 1)],
        [Membership("student-b", "school", "student")],
        [],
    )
    store = MemoryReceiptStore()
    decision = ReleaseGate(
        store, access_registry=registry, meter=_lexical({unit: _SECRET})
    ).evaluate_and_reserve(_request(text=_SECRET, scope=frozenset({unit})))

    assert decision.reason == "unauthorized"
    assert decision.receipt_ids == ()
    assert store.receipts == []


def test_units_outside_meter_scope_are_not_disclosed() -> None:
    inside = ("doc", "inside")
    outside = ("doc", "outside")
    inside_text = "abcdefghijklmnop"
    outside_text = "qrstuvwxyz012345"
    store = MemoryReceiptStore()
    decision = ReleaseGate(
        store,
        meter=_lexical({inside: inside_text, outside: outside_text}),
    ).evaluate_and_reserve(
        _request(text=f"{inside_text} {outside_text}", scope=frozenset({inside}))
    )

    assert decision.allowed is True
    assert decision.evidence == {"meter_method": "lexical-v1", "metered_unit_count": 1}
    assert [row["unit_id"] for row in store.receipts] == ["inside"]
    assert outside_text not in repr(decision.evidence)
    assert "outside" not in repr(decision.evidence)


def test_meter_failure_reserves_nothing_and_select_skips_that_candidate() -> None:
    store = MemoryReceiptStore()
    meter = FakeMeter(fail_on="explode")
    gate = ReleaseGate(store, meter=meter)
    meter.gate = gate
    decision = gate.evaluate_and_reserve(_request(text="explode"))

    assert decision == GateDecision(False, "meter_error", (), {})
    assert store.receipts == []
    assert meter.calls == 1
    assert meter.locked == [False]

    select_store = MemoryReceiptStore()
    select_meter = FakeMeter(
        frozenset({("doc", "safe")}), method="boom-v1", fail_on="explode"
    )
    select_gate = ReleaseGate(select_store, meter=select_meter)
    select_meter.gate = select_gate
    bad = Candidate("bad", (UnitRelease("doc", "declared-bad", "nope"),), 5.0, text="explode")
    good = Candidate("good", (), 1.0, text="safe text")
    chosen, selected = select_gate.select_and_reserve(_request(), [bad, good])

    assert chosen is not None and chosen.name == "good"
    assert selected.evidence == {
        "candidate_count": 2,
        "accepted_count": 1,
        "selected": "good",
        "meter_error_count": 1,
        "meter_method": "boom-v1",
        "metered_unit_count": 1,
    }
    assert [row["unit_id"] for row in select_store.receipts] == ["safe"]
    assert select_meter.locked == [False, False]


def test_evidence_omits_unit_text_and_ids() -> None:
    unit = ("lesson", "step-free")
    meter = _lexical({unit: _SECRET})
    store = MemoryReceiptStore()
    decision = ReleaseGate(store, meter=meter).evaluate_and_reserve(
        _request(text=_SECRET, scope=frozenset({unit}))
    )
    select_store = MemoryReceiptStore()
    chosen, selected = ReleaseGate(select_store, meter=meter).select_and_reserve(
        _request(),
        [Candidate("reply", (), 1.0, text=_SECRET, meter_scope=frozenset({unit}))],
    )

    assert decision.evidence == {"meter_method": "lexical-v1", "metered_unit_count": 1}
    assert selected.evidence == {
        "candidate_count": 1,
        "accepted_count": 1,
        "selected": "reply",
        "meter_method": "lexical-v1",
        "metered_unit_count": 1,
    }
    assert chosen is not None and chosen.name == "reply"
    for evidence in (decision.evidence, selected.evidence):
        rendered = repr(evidence)
        assert _SECRET not in rendered
        assert "lesson" not in rendered
        assert "step-free" not in rendered


def test_meter_is_called_once_before_the_lock() -> None:
    meter = FakeMeter(method="probe")
    gate = ReleaseGate(MemoryReceiptStore(), meter=meter)
    meter.gate = gate
    gate.evaluate_and_reserve(_request(text="probe"))

    assert meter.calls == 1
    assert meter.locked == [False]

    select_meter = FakeMeter(method="probe")
    select_gate = ReleaseGate(MemoryReceiptStore(), meter=select_meter)
    select_meter.gate = select_gate
    select_gate.select_and_reserve(_request(), [Candidate("only", (), 1.0, text="probe")])

    assert select_meter.calls == 1
    assert select_meter.locked == [False]
