"""ReleaseGate does not depend on education types. MySQL failures skip these cases."""

from __future__ import annotations

import os
import uuid
from threading import Barrier, Lock, Thread

import pytest

pymysql = pytest.importorskip("pymysql")

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.release_gate import (
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
    setup.commit(held)
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

    gate.commit(first)

    assert [row["status"] for row in _rows(store)] == ["delivered"]
    assert len(store.history(_STUDENT_A)) == 1
    second = gate.evaluate_and_reserve(_request(_STUDENT_A, "u2"))
    gate.cancel(second)

    assert {row["unit_id"]: row["status"] for row in _rows(store)} == {
        "u1": "delivered",
        "u2": "cancelled",
    }
    assert [receipt.unit_id for receipt in store.history(_STUDENT_A)] == ["u1"]


def test_concurrent_pair_lets_exactly_one_release_through(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2)
    allowed_per_round = []
    winners = []
    for _ in range(20):
        barrier = Barrier(2)
        found: dict[str, GateDecision] = {}
        errors: list[BaseException] = []
        record = Lock()

        def release(student: str, unit_id: str) -> None:
            try:
                barrier.wait(30)
                decision = gate.evaluate_and_reserve(_request(student, unit_id))
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
        assert errors == []
        allowed = [decision for decision in found.values() if decision.allowed]
        refused = [decision for decision in found.values() if not decision.allowed]
        assert len(allowed) == 1
        assert len(refused) == 1
        assert allowed[0].reason == "ok"
        assert refused[0].reason == "reconstruction"
        assert refused[0].receipt_ids == ()
        reserved = [row for row in _rows(store) if row["status"] == "reserved"]
        assert len(reserved) == 1
        allowed_per_round.append(1)
        winners.append(reserved[0]["recipient_principal_id"])
        gate.cancel(allowed[0])

    assert allowed_per_round == [1] * 20
    assert len(winners) == 20
    assert set(winners) <= {_STUDENT_A, _STUDENT_B}
    assert [row["status"] for row in _rows(store)] == ["cancelled"] * 20
