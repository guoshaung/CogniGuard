"""MySQL DisclosureStore reliability: real cross-process races, persistence across tasks,
duplicate submissions and the database state after a failed commit-time recheck.

These are implementation-reliability checks, not an algorithmic contribution. They skip
when no MySQL server is reachable (same rule as test_release_gate.py).
"""

from __future__ import annotations

import multiprocessing as mp
import os

import pytest

pymysql = pytest.importorskip("pymysql")

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry, RegistryHolder
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.release_gate import ReleaseGate
from cogniguard.tests.test_release_gate import (  # noqa: F401  (fixture re-export)
    _STUDENT_A,
    _STUDENT_B,
    _request,
    _witness_registry,
    store,
)

_ROUNDS = 12


def _settings(store: DisclosureStore) -> dict:
    return {"host": store._host, "port": store._port, "user": store._user,
            "password": store._password, "database": store._database}


def _statuses(store: DisclosureStore) -> list[tuple[str, str, str]]:
    conn = pymysql.connect(**_settings(store), autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT recipient_principal_id, unit_id, status FROM disclosure_receipt")
            return sorted(cur.fetchall())
    finally:
        conn.close()


def _clear(store: DisclosureStore) -> None:
    conn = pymysql.connect(**_settings(store), autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM disclosure_receipt")
    finally:
        conn.close()


def _race_worker(settings, recipient, unit, barrier, results):
    """A separate OS process with its own connection, store object and gate."""
    worker_store = DisclosureStore(**settings)
    try:
        gate = ReleaseGate(worker_store, target_registry=_witness_registry(), coalition_k=2)
        barrier.wait(timeout=20)
        decision = gate.evaluate_and_reserve(_request(recipient, unit))
        if decision.allowed:
            gate.commit(decision, 11.0)
        results.put((recipient, decision.reason))
    finally:
        worker_store.close()


def test_cross_process_race_releases_at_most_one_completing_unit(store: DisclosureStore) -> None:
    """Two processes ask for the two halves of one witness at once (k=2): at most one may win."""
    settings = _settings(store)
    ctx = mp.get_context("spawn")
    outcomes = []
    for _ in range(_ROUNDS):
        _clear(store)
        barrier = ctx.Barrier(2)
        results = ctx.Queue()
        procs = [ctx.Process(target=_race_worker, args=(settings, r, u, barrier, results))
                 for r, u in ((_STUDENT_A, "u1"), (_STUDENT_B, "u2"))]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=60)
            assert p.exitcode == 0
        got = dict(results.get(timeout=5) for _ in procs)
        allowed = sum(reason == "ok" for reason in got.values())
        delivered = [row for row in _statuses(store) if row[2] == "delivered"]
        assert allowed == len(delivered) == 1, (got, delivered)
        outcomes.append(got)
    assert len(outcomes) == _ROUNDS


def test_receipts_survive_a_new_task_and_a_new_store_object(store: DisclosureStore) -> None:
    """A later task (new store object, new gate) still sees what an earlier task delivered."""
    first = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2)
    decision = first.evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    assert decision.allowed and first.commit(decision, 11.0)

    reopened = DisclosureStore(**_settings(store))
    try:
        later = ReleaseGate(reopened, target_registry=_witness_registry(), coalition_k=2)
        blocked = later.evaluate_and_reserve(_request(_STUDENT_B, "u2"))
        assert not blocked.allowed and blocked.reason == "reconstruction"
        assert reopened.holders_of({("doc", "u1")}) == {_STUDENT_A: frozenset({("doc", "u1")})}
    finally:
        reopened.close()


def test_duplicate_commit_and_cancel_cannot_change_a_settled_receipt(store: DisclosureStore) -> None:
    gate = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2)
    decision = gate.evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    receipt = decision.receipt_ids[0]
    store.commit(receipt)
    with pytest.raises(ValueError):
        store.commit(receipt)          # a retried commit is rejected, not double-counted
    with pytest.raises(ValueError):
        store.cancel(receipt)          # a delivered receipt cannot be withdrawn
    assert _statuses(store) == [(_STUDENT_A, "u1", "delivered")]


def test_duplicate_submission_from_two_store_objects_settles_once(store: DisclosureStore) -> None:
    """The same receipt committed through two connections: exactly one transition succeeds."""
    gate = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2)
    receipt = gate.evaluate_and_reserve(_request(_STUDENT_A, "u1")).receipt_ids[0]
    other = DisclosureStore(**_settings(store))
    try:
        outcomes = []
        for s in (store, other):
            try:
                s.commit(receipt)
                outcomes.append("ok")
            except ValueError:
                outcomes.append("rejected")
        assert sorted(outcomes) == ["ok", "rejected"]
    finally:
        other.close()
    assert _statuses(store) == [(_STUDENT_A, "u1", "delivered")]


def _holder_registry(version: int, *, granted: bool) -> AccessRegistry:
    grants = [AccessGrant(_STUDENT_A, "doc", "tutoring", version)] if granted else []
    return AccessRegistry(
        [AssetOwnership("doc", "teacher-a", "school", version)],
        [Membership(_STUDENT_A, "school", "student"), Membership("teacher-a", "school", "teacher")],
        grants,
    )


def test_failed_commit_recheck_leaves_cancelled_rows_that_no_longer_count(store: DisclosureStore) -> None:
    holder = RegistryHolder(_holder_registry(1, granted=True))
    gate = ReleaseGate(store, target_registry=_witness_registry(), coalition_k=2, registry_holder=holder)
    decision = gate.evaluate_and_reserve(_request(_STUDENT_A, "u1"))
    assert decision.allowed
    holder.replace(_holder_registry(2, granted=False))   # revoked between reserve and commit
    assert gate.commit(decision, 11.0) is False
    assert _statuses(store) == [(_STUDENT_A, "u1", "cancelled")]
    assert store.holders_of({("doc", "u1")}) == {}
    with pytest.raises(ValueError):
        store.commit(decision.receipt_ids[0])         # a cancelled receipt cannot be revived
