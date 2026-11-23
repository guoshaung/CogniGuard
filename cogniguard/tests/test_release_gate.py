"""ReleaseGate does not depend on education types. MySQL failures skip these cases."""

from __future__ import annotations

import math
import os
import time
import uuid
from contextlib import nullcontext
from threading import Barrier, Lock, Thread

import pytest

pymysql = pytest.importorskip("pymysql")

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry, RegistryHolder
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.release_gate import (
    Candidate,
    CommitContext,
    GateDecision,
    ReleaseGate,
    ReleaseRequest,
    UnitRelease,
)

_CONNECT_TIMEOUT = 3
_STUDENT_A = "student-a"
_STUDENT_B = "student-b"


def _server_settings() -> dict:
    return {
        "host": os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
        "user": os.environ.get("COGNIGUARD_MYSQL_USER", "root"),
        "password": os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
    }


@pytest.fixture
def store():
    settings = _server_settings()
    try:
        probe = pymysql.connect(**settings, connect_timeout=_CONNECT_TIMEOUT)
    except (pymysql.Error, OSError) as exc:
        pytest.skip(f"MySQL is not reachable: {exc}")
    else:
        probe.close()

    database = "cg_release_gate_" + uuid.uuid4().hex[:12]
    opened = DisclosureStore(**settings, database=database)
    try:
        yield opened
    finally:
        opened.close()
        admin = pymysql.connect(**settings, autocommit=True, connect_timeout=_CONNECT_TIMEOUT)
        try:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            admin.close()


def _rows(store: DisclosureStore) -> list[dict]:
    admin = pymysql.connect(
        host=store._host,
        port=store._port,
        user=store._user,
        password=store._password,
        database=store._database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=_CONNECT_TIMEOUT,
    )
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                """
                SELECT resource_id, unit_id, recipient_principal_id, status, policy_version
                FROM disclosure_receipt
                ORDER BY created_at, receipt_id
                """
            )
            return list(cursor.fetchall())
    finally:
        admin.close()


def _request(recipient: str, unit_id: str, *, resource_id: str = "doc") -> ReleaseRequest:
    return ReleaseRequest(
        recipient_principal_id=recipient,
        acting_org_id="school",
        agent_principal_id="agent-1",
        session_id="session-1",
        purpose="tutoring",
        units=(UnitRelease(resource_id, unit_id, f"text-{unit_id}"),),
        now=10.0,
    )


def _registry() -> AccessRegistry:
    return AccessRegistry(
        [AssetOwnership("doc", "teacher-a", "school", 3)],
        [
            Membership(_STUDENT_B, "school", "student"),
            Membership("teacher-a", "school", "teacher"),
        ],
        [AccessGrant(_STUDENT_B, "doc", "tutoring", 3)],
    )


def _witness_registry() -> TargetRegistry:
    witness = frozenset({("doc", "u1"), ("doc", "u2")})
    return TargetRegistry([ProtectedTarget("witness", "owner", "org", (witness,))])


def test_authorization_allows_a_granted_release_and_rejects_the_rest(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, access_registry=_registry())

    denied = gate.evaluate_and_reserve(_request("intruder", "u1"))
    mixed = gate.evaluate_and_reserve(
        ReleaseRequest(
            recipient_principal_id=_STUDENT_B,
            acting_org_id="school",
            agent_principal_id="agent-1",
            session_id="session-1",
            purpose="tutoring",
            units=(
                UnitRelease("doc", "u1", "text-u1"),
                UnitRelease("other", "u9", "text-u9"),
            ),
            now=10.0,
        )
    )
    allowed = gate.evaluate_and_reserve(_request(_STUDENT_B, "u1"))

    assert denied == GateDecision(False, "unauthorized", (), {})
    assert mixed == GateDecision(False, "unauthorized", (), {})
    assert allowed.allowed is True
    assert allowed.reason == "ok"
    assert allowed.evidence == {}
    assert len(allowed.receipt_ids) == 1
    rows = _rows(store)
    assert len(rows) == 1
    assert rows[0]["recipient_principal_id"] == _STUDENT_B
    assert rows[0]["unit_id"] == "u1"
    assert rows[0]["status"] == "reserved"
    assert rows[0]["policy_version"] == 3


def test_reconstruction_writes_no_receipt(store: DisclosureStore) -> None:
    setup = ReleaseGate(store)
    held = setup.evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    assert setup.commit(held, 10.0) is True
    gate = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2)

    denied = gate.evaluate_and_reserve(_request(_STUDENT_B, "u2"))

    assert denied.allowed is False
    assert denied.reason == "reconstruction"
    assert denied.receipt_ids == ()
    assert denied.evidence == {"target_count": 1, "violation_count": 1}
    assert all(type(value) is int for value in denied.evidence.values())
    assert _rows(store) == [
        {
            "resource_id": "doc",
            "unit_id": "u1",
            "recipient_principal_id": _STUDENT_A,
            "status": "delivered",
            "policy_version": 0,
        }
    ]


def test_commit_and_cancel_set_the_receipt_status(store: DisclosureStore) -> None:
    gate = ReleaseGate(store)
    first = gate.evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    assert [row["status"] for row in _rows(store)] == ["reserved"]

    assert gate.commit(first, 10.0) is True

    assert [row["status"] for row in _rows(store)] == ["delivered"]
    assert len(store.history(_STUDENT_A)) == 1
    second = gate.evaluate_and_reserve(_request(_STUDENT_A, "u2"))
    gate.cancel(second)

    assert {row["unit_id"]: row["status"] for row in _rows(store)} == {
        "u1": "delivered",
        "u2": "cancelled",
    }
    assert [receipt.unit_id for receipt in store.history(_STUDENT_A)] == ["u1"]


class _SlowHolders:
    """Widen the gap between the coalition check and reserve."""

    def __init__(self, inner: DisclosureStore) -> None:
        self._inner = inner

    def holders_of(self, units):
        found = self._inner.holders_of(units)
        time.sleep(0.05)
        return found

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _UnlockedGate(ReleaseGate):
    """Same checks, but the store lock is replaced with a no-op."""

    def __init__(self, store, access_registry=None, target_registry=None, coalition_k=None):
        super().__init__(store, access_registry, target_registry, coalition_k)
        self._lock = nullcontext()


def _race_round(gates: dict[str, ReleaseGate]) -> dict[str, GateDecision]:
    barrier = Barrier(2)
    found: dict[str, GateDecision] = {}
    errors: list[BaseException] = []
    record = Lock()

    def release(student: str, unit_id: str) -> None:
        try:
            barrier.wait(30)
            decision = gates[student].evaluate_and_reserve(_request(student, unit_id))
            with record:
                found[student] = decision
        except BaseException as exc:
            with record:
                errors.append(exc)

    threads = [
        Thread(target=release, args=(_STUDENT_A, "u1")),
        Thread(target=release, args=(_STUDENT_B, "u2")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
        assert not thread.is_alive()
    assert errors == [], errors
    assert set(found) == {_STUDENT_A, _STUDENT_B}
    return found


def _cancel_decisions(gate: ReleaseGate, decisions) -> None:
    for decision in decisions:
        if decision.receipt_ids:
            gate.cancel(decision)


def _tally(found: dict[str, GateDecision]) -> str:
    allowed = {student for student, decision in found.items() if decision.allowed}
    if allowed == {_STUDENT_A}:
        return "a"
    if allowed == {_STUDENT_B}:
        return "b"
    if allowed == {_STUDENT_A, _STUDENT_B}:
        return "both"
    return "none"


def _run_race_group(store: DisclosureStore, gates: dict[str, ReleaseGate]) -> dict[str, int]:
    counts = {"a": 0, "b": 0, "both": 0, "none": 0}
    previous: list[GateDecision] = []
    for _ in range(20):
        _cancel_decisions(gates[_STUDENT_A], previous)
        found = _race_round(gates)
        outcome = _tally(found)
        counts[outcome] += 1
        reserved = [row for row in _rows(store) if row["status"] == "reserved"]
        assert len(reserved) == sum(decision.allowed for decision in found.values())
        for decision in found.values():
            if decision.allowed:
                assert decision.reason == "ok"
            else:
                assert decision.reason == "reconstruction"
                assert decision.receipt_ids == ()
        previous = list(found.values())
    _cancel_decisions(gates[_STUDENT_A], previous)
    return counts


def test_shared_store_lock_closes_the_race_an_unlocked_gate_still_shows(store: DisclosureStore) -> None:
    slow = _SlowHolders(store)
    registry = _witness_registry()
    unlocked = {
        _STUDENT_A: _UnlockedGate(slow, target_registry=registry, coalition_k=2),
        _STUDENT_B: _UnlockedGate(slow, target_registry=registry, coalition_k=2),
    }
    locked = {
        _STUDENT_A: ReleaseGate(slow, target_registry=registry, coalition_k=2),
        _STUDENT_B: ReleaseGate(slow, target_registry=registry, coalition_k=2),
    }
    assert locked[_STUDENT_A]._lock is locked[_STUDENT_B]._lock

    control = _run_race_group(store, unlocked)
    experiment = _run_race_group(store, locked)

    assert control["both"] >= 1
    assert experiment["a"] + experiment["b"] == 20
    assert experiment["both"] == 0
    assert experiment["none"] == 0
    print(
        f"control a={control['a']} b={control['b']} both={control['both']}; "
        f"experiment a={experiment['a']} b={experiment['b']} both={experiment['both']}"
    )


class _ProcessLockOnly(_SlowHolders):
    """Keep the per-object lock and skip the database lock."""

    def release_section(self, timeout: float = 10.0):
        return nullcontext()


def _bind_release_env(monkeypatch, store: DisclosureStore) -> None:
    monkeypatch.setenv("COGNIGUARD_MYSQL_HOST", store._host)
    monkeypatch.setenv("COGNIGUARD_MYSQL_PORT", str(store._port))
    monkeypatch.setenv("COGNIGUARD_MYSQL_USER", store._user)
    monkeypatch.setenv("COGNIGUARD_MYSQL_PASSWORD", store._password)
    monkeypatch.setenv("COGNIGUARD_MYSQL_DATABASE", store._database)


def _named_lock_available(store: DisclosureStore) -> int:
    """1 when this call acquires the release lock, else 0. An acquire is released."""
    name = f"cogniguard_release_{store._database}"
    conn = pymysql.connect(
        host=store._host,
        port=store._port,
        user=store._user,
        password=store._password,
        database=store._database,
        autocommit=True,
        connect_timeout=_CONNECT_TIMEOUT,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", (name, 0))
            got = cursor.fetchone()[0]
            if got == 1:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
        return 0 if got is None else int(got)
    finally:
        conn.close()


def test_named_lock_closes_the_cross_object_race_a_process_lock_does_not(
    store: DisclosureStore, monkeypatch
) -> None:
    _bind_release_env(monkeypatch, store)
    left = DisclosureStore.from_env()
    try:
        right = DisclosureStore.from_env()
        try:
            assert left is not right
            assert left._database == right._database == store._database
            registry = _witness_registry()
            control = {
                _STUDENT_A: ReleaseGate(
                    _ProcessLockOnly(left), target_registry=registry, coalition_k=2
                ),
                _STUDENT_B: ReleaseGate(
                    _ProcessLockOnly(right), target_registry=registry, coalition_k=2
                ),
            }
            experiment = {
                _STUDENT_A: ReleaseGate(
                    _SlowHolders(left), target_registry=registry, coalition_k=2
                ),
                _STUDENT_B: ReleaseGate(
                    _SlowHolders(right), target_registry=registry, coalition_k=2
                ),
            }
            assert type(control[_STUDENT_A]._lock) is Lock
            assert type(control[_STUDENT_B]._lock) is Lock
            assert control[_STUDENT_A]._lock is not control[_STUDENT_B]._lock
            assert experiment[_STUDENT_A]._lock is not experiment[_STUDENT_B]._lock

            control_counts = _run_race_group(store, control)
            experiment_counts = _run_race_group(store, experiment)

            assert control_counts["both"] >= 1
            assert experiment_counts["a"] + experiment_counts["b"] == 20
            assert experiment_counts["both"] == 0
            assert experiment_counts["none"] == 0
            print(
                f"control a={control_counts['a']} b={control_counts['b']} "
                f"both={control_counts['both']}; "
                f"experiment a={experiment_counts['a']} b={experiment_counts['b']} "
                f"both={experiment_counts['both']}"
            )
        finally:
            right.close()
    finally:
        left.close()


def test_busy_when_another_connection_holds_the_release_lock(
    store: DisclosureStore, monkeypatch
) -> None:
    name = f"cogniguard_release_{store._database}"
    original = DisclosureStore.release_section

    def fast(self, timeout: float = 10.0):
        return original(self, 0.2)

    monkeypatch.setattr(DisclosureStore, "release_section", fast)
    holder = pymysql.connect(
        host=store._host,
        port=store._port,
        user=store._user,
        password=store._password,
        database=store._database,
        autocommit=True,
        connect_timeout=_CONNECT_TIMEOUT,
    )
    try:
        with holder.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", (name, 0))
            assert cursor.fetchone()[0] == 1
        decision = ReleaseGate(store).evaluate_and_reserve(_request(_STUDENT_A, "u1"))
        assert decision == GateDecision(False, "busy", (), {})
        assert _rows(store) == []
    finally:
        with holder.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
        holder.close()


class _FailWhileLockHeld:
    """The named lock is held, then the section fails before reserve."""

    def __init__(self, inner: DisclosureStore) -> None:
        self._inner = inner

    def holders_of(self, units):
        assert _named_lock_available(self._inner) == 0
        raise RuntimeError("section failed")

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_exception_inside_the_section_releases_the_named_lock(store: DisclosureStore) -> None:
    gate = ReleaseGate(
        _FailWhileLockHeld(store), target_registry=_witness_registry(), coalition_k=2
    )
    with pytest.raises(RuntimeError, match="section failed"):
        gate.evaluate_and_reserve(_request(_STUDENT_A, "u1"))

    assert _rows(store) == []
    assert _named_lock_available(store) == 1
    decision = ReleaseGate(store).evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    assert decision.allowed is True
    assert decision.reason == "ok"
    assert len(decision.receipt_ids) == 1
    assert [row["status"] for row in _rows(store)] == ["reserved"]


def _holder_registry(*grants: AccessGrant, versions: dict[str, int] | None = None) -> AccessRegistry:
    versions = versions or {}
    resource_ids = sorted({grant.resource_id for grant in grants})
    return AccessRegistry(
        [
            AssetOwnership(resource_id, "teacher-a", "school", versions.get(resource_id, 3))
            for resource_id in resource_ids
        ],
        [
            Membership(_STUDENT_B, "school", "student"),
            Membership("teacher-a", "school", "teacher"),
        ],
        list(grants),
    )


def test_commit_cancels_when_the_holder_changes_or_the_grant_expires(store: DisclosureStore) -> None:
    grants = (
        AccessGrant(_STUDENT_B, "doc", "tutoring", 3),
        AccessGrant(_STUDENT_B, "notes", "tutoring", 3),
    )
    registry = _holder_registry(*grants)
    holder = RegistryHolder(registry)
    gate = ReleaseGate(store, registry_holder=holder)
    both = ReleaseRequest(
        recipient_principal_id=_STUDENT_B,
        acting_org_id="school",
        agent_principal_id="agent-1",
        session_id="session-1",
        purpose="tutoring",
        units=(UnitRelease("doc", "u1", "text-u1"), UnitRelease("notes", "u2", "text-u2")),
        now=10.0,
    )
    reserved = gate.evaluate_and_reserve(both)
    assert reserved.unit_versions == (("doc", 3), ("notes", 3))
    assert reserved.commit_context == CommitContext(_STUDENT_B, "tutoring", "school")
    holder.replace(registry.with_policy_version("doc", 4))

    assert gate.commit(reserved, 10.0) is False
    assert {(row["unit_id"], row["status"]) for row in _rows(store)} == {
        ("u1", "cancelled"),
        ("u2", "cancelled"),
    }
    assert store.history(_STUDENT_B) == []

    kept = ReleaseGate(store, registry_holder=holder).evaluate_and_reserve(
        _request(_STUDENT_B, "u3", resource_id="notes")
    )
    holder.replace(registry)
    assert gate.commit(kept, 10.0) is True
    assert {row["unit_id"]: row["status"] for row in _rows(store)}["u3"] == "delivered"
    assert [receipt.unit_id for receipt in store.history(_STUDENT_B)] == ["u3"]

    expiring = _holder_registry(AccessGrant(_STUDENT_B, "doc", "tutoring", 3, expires_at=100.0))
    expiry_holder = RegistryHolder(expiring)
    expiry_gate = ReleaseGate(store, registry_holder=expiry_holder)
    expired = expiry_gate.evaluate_and_reserve(_request(_STUDENT_B, "u4"))
    assert expiry_gate.commit(expired, 100.0) is False
    assert {row["unit_id"]: row["status"] for row in _rows(store)}["u4"] == "cancelled"
    assert [receipt.unit_id for receipt in store.history(_STUDENT_B)] == ["u3"]


def _base(recipient: str = _STUDENT_A) -> ReleaseRequest:
    return ReleaseRequest(
        recipient_principal_id=recipient,
        acting_org_id="school",
        agent_principal_id="agent-1",
        session_id="session-1",
        purpose="tutoring",
        units=(),
        now=10.0,
    )


def _unit(unit_id: str, resource_id: str = "doc") -> UnitRelease:
    return UnitRelease(resource_id, unit_id, f"text-{unit_id}")


def _goal(*unit_ids: str, value: float = 1.0) -> TargetRegistry:
    witness = frozenset(("doc", unit_id) for unit_id in unit_ids)
    return TargetRegistry([ProtectedTarget("goal", "owner", "org", (witness,), value)])


def _reserved_units(store: DisclosureStore) -> set[str]:
    return {row["unit_id"] for row in _rows(store) if row["status"] == "reserved"}


def test_unsafe_original_loses_to_a_lower_utility_rewrite(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_goal("u1", "u2"), coalition_k=2)
    original = Candidate("original", (_unit("u1"), _unit("u2")), utility=5.0)
    rewrite = Candidate("rewrite", (_unit("u1"),), utility=1.0)

    chosen, decision = gate.select_and_reserve(_base(), [original, rewrite])

    assert chosen is rewrite
    assert decision.allowed is True
    assert decision.reason == "ok"
    assert decision.evidence == {
        "candidate_count": 2,
        "accepted_count": 1,
        "selected": "rewrite",
    }
    assert _reserved_units(store) == {"u1"}


def test_farther_safe_candidate_wins_on_price(store: DisclosureStore) -> None:
    # k = 1, value = 1, lambda = 1, decay = 1.
    # close releases a,b: distance 2, score 1 - exp(-2).
    # far releases a,x: distance 3, score 0.95 - exp(-3). Both disclose two units.
    score_close = 1.0 - math.exp(-2)
    score_far = 0.95 - math.exp(-3)
    assert score_far > score_close
    gate = ReleaseGate(store, target_registry=_goal("a", "b", "c", "d"), coalition_k=1)
    close = Candidate("close", (_unit("a"), _unit("b")), utility=1.0)
    far = Candidate("far", (_unit("a"), _unit("x")), utility=0.95)

    chosen, decision = gate.select_and_reserve(_base(), [close, far])

    assert chosen is far
    assert decision.reason == "ok"
    assert decision.evidence["accepted_count"] == 2
    assert decision.evidence["selected"] == "far"
    assert _reserved_units(store) == {"a", "x"}


def test_empty_candidate_is_selected_when_it_is_the_only_safe_one(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_goal("u1", "u2"), coalition_k=1)
    full = Candidate("full", (_unit("u1"), _unit("u2")), utility=10.0)
    public = Candidate("public", (), utility=0.0)

    chosen, decision = gate.select_and_reserve(_base(), [full, public])

    assert chosen is public
    assert decision.reason == "ok"
    assert decision.receipt_ids == ()
    assert decision.evidence["selected"] == "public"
    assert decision.evidence["accepted_count"] == 1
    assert _rows(store) == []


def test_no_safe_candidate_writes_no_receipt(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_goal("u1", "u2"), coalition_k=1)
    first = Candidate("first", (_unit("u1"), _unit("u2")), utility=3.0)
    second = Candidate("second", (_unit("u2"), _unit("u1")), utility=4.0)

    chosen, decision = gate.select_and_reserve(_base(), [first, second])

    assert chosen is None
    assert decision == GateDecision(
        False,
        "no_safe_candidate",
        (),
        {"candidate_count": 2, "accepted_count": 0, "selected": ""},
    )
    assert _rows(store) == []


def test_zero_price_lambda_picks_the_highest_utility_safe_candidate(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_goal("a", "b", "c", "d"), coalition_k=1)
    close = Candidate("close", (_unit("a"), _unit("b")), utility=1.0)
    far = Candidate("far", (_unit("a"), _unit("x")), utility=0.95)

    chosen, decision = gate.select_and_reserve(_base(), [far, close], price_lambda=0.0)

    assert chosen is close
    assert decision.evidence == {
        "candidate_count": 2,
        "accepted_count": 2,
        "selected": "close",
    }
    assert _reserved_units(store) == {"a", "b"}
