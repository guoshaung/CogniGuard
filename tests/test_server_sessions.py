from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cogniguard.runtime.sessions import (
    BudgetExceeded,
    InvalidSessionToken,
    RequestConflict,
    SessionStore,
)


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "sessions.sqlite3")


def test_token_is_server_created_private_and_not_session_id(store: SessionStore) -> None:
    session = store.get_or_create()
    assert len(session.token) >= 40
    assert session.token not in repr(session)
    assert store.get_or_create(session.token).session_id == session.session_id
    for token in ("", "unknown", session.session_id):
        with pytest.raises(InvalidSessionToken):
            store.get_or_create(token)
    assert "token" not in session.to_public()
    for path in store.path.parent.glob("sessions.sqlite3*"):
        if path.is_file():
            assert session.token.encode() not in path.read_bytes()


def test_state_is_server_owned_persistent_and_nested(store: SessionStore) -> None:
    session = store.get_or_create()
    with session.lock(), session.transaction() as state:
        state["history"] = [{"role": "user", "content": "hello"}]
        with session.transaction() as nested:
            assert nested is state
            nested["classroom"] = {"turn": 1}
    loaded = SessionStore(store.path).get_or_create(session.token)
    assert loaded.load_state() == state
    copy = loaded.load_state()
    copy["classroom"]["turn"] = 99
    assert loaded.load_state()["classroom"]["turn"] == 1
    with pytest.raises(RuntimeError), loaded.transaction() as state:
        state["classroom"]["turn"] = 2
        raise RuntimeError("cancel")
    assert loaded.load_state()["classroom"]["turn"] == 1
    with pytest.raises(ValueError, match="credentials"):
        session.save_state({"session_token": session.token})


def test_atomic_reservations_are_idempotent_and_survive_restart(store: SessionStore) -> None:
    session = store.get_or_create()
    first = session.reserve("images", 1, "first")
    assert session.reserve("images", 1, "first").reservation_id == first.reservation_id
    with pytest.raises(RequestConflict):
        session.reserve("images", 2, "first")
    first.commit()
    second = session.reserve("images", 1, "second")
    restarted = SessionStore(store.path, limits={"images": 100}).get_or_create(session.token)
    assert restarted.budget("images") == {"limit": 2, "committed": 1, "reserved": 1, "remaining": 0}
    with pytest.raises(BudgetExceeded):
        restarted.reserve("images", 1, "third")
    with pytest.raises(ValueError, match="confirmation"):
        second.release()
    second.release(no_side_effects=True)
    second.release(no_side_effects=True)
    assert restarted.budget("images")["remaining"] == 1
    with pytest.raises(RequestConflict):
        second.commit()
    with pytest.raises(RequestConflict):
        restarted.reserve("images", 1, "second")


@pytest.mark.parametrize("budget", ["privacy", "copyright"])
def test_generic_ledger_uses_fixed_units_without_float_overdraft(
    store: SessionStore, budget: str
) -> None:
    session = store.get_or_create()
    session.reserve(budget, 0.7, "one").commit()
    session.reserve(budget, 0.3, "two")
    with pytest.raises(BudgetExceeded):
        session.reserve(budget, 0.000000001, "three")
    assert session.budget(budget)["remaining"] == 0


def test_completed_request_replays_result_without_charge_or_side_effects(
    store: SessionStore,
) -> None:
    session = store.get_or_create()
    effects = []
    with session.request("request-1", fingerprint="body-hash") as request:
        assert not request.cached
        session.reserve("images", 1, request.request_id)
        effects.append("image")
        request.complete({"answer": "done", "artifacts": ["mock-image"]})
    restarted = SessionStore(store.path).get_or_create(session.token)
    with restarted.request("request-1", fingerprint="body-hash") as request:
        assert request.cached
        assert request.result["answer"] == "done"
        if not request.cached:
            effects.append("image")
    assert effects == ["image"]
    assert restarted.budget("requests")["committed"] == 1
    assert restarted.budget("images")["committed"] == 1
    with pytest.raises(RequestConflict, match="different"):
        restarted.claim_request("request-1", fingerprint="another-body")


def test_failed_and_active_requests_cannot_reexecute_and_failure_keeps_charge(
    store: SessionStore,
) -> None:
    session = store.get_or_create()
    session.claim_request("active")
    with pytest.raises(RequestConflict):
        session.claim_request("active")
    with pytest.raises(RuntimeError), session.request("failed"):
        session.reserve("images", 2, "failed")
        raise RuntimeError("uncertain external side effect")
    with pytest.raises(RequestConflict):
        SessionStore(store.path).get_or_create(session.token).claim_request("failed")
    assert session.budget("images")["committed"] == 2
    with pytest.raises(BudgetExceeded):
        session.reserve("images", 1, "different-request")


def test_state_rollback_does_not_refund_durable_budget(store: SessionStore) -> None:
    session = store.get_or_create()
    with pytest.raises(RuntimeError), session.transaction() as state:
        session.reserve("images", 1, "durable")
        state["should_not_persist"] = True
        raise RuntimeError("interrupt")
    assert session.load_state() == {}
    assert session.budget("images")["reserved"] == 1


def test_request_requires_final_result_and_never_stores_token(store: SessionStore) -> None:
    session = store.get_or_create()
    with pytest.raises(RequestConflict, match="final result"), session.request("unfinished"):
        pass
    with pytest.raises(ValueError, match="credentials"), session.request("leak") as request:
        request.complete({"session_token": session.token})
    for request_id in ("unfinished", "leak"):
        with pytest.raises(RequestConflict):
            session.claim_request(request_id)


def test_requests_and_budget_limits_are_server_configurable(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3", limits={"requests": 1, "privacy": 10})
    session = store.get_or_create()
    with session.request("one") as request:
        request.complete({})
    with pytest.raises(BudgetExceeded), session.request("two"):
        pytest.fail("Budget must reject before reaching execution")
    assert session.budget_snapshot()["privacy"]["limit"] == 10


def test_concurrent_threads_cannot_overdraw_image_budget(store: SessionStore) -> None:
    session = store.get_or_create()

    def reserve(index: int) -> bool:
        other = SessionStore(store.path).get_or_create(session.token)
        try:
            other.reserve("images", 1, f"thread-{index}")
        except BudgetExceeded:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(16))) == 2
    assert session.budget("images")["remaining"] == 0


def test_concurrent_claims_execute_only_one_request(store: SessionStore) -> None:
    session = store.get_or_create()

    def claim(_: int) -> bool:
        other = store.get_or_create(session.token)
        try:
            other.claim_request("same-request", fingerprint="same-body-hash")
        except RequestConflict:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(claim, range(16))) == 1


def test_sessions_cannot_commit_each_others_reservations(store: SessionStore) -> None:
    owner = store.get_or_create()
    other = store.get_or_create()
    reservation = owner.reserve("images", 1, "one")
    with pytest.raises(RequestConflict):
        other.commit(reservation)
    assert other.budget("images")["remaining"] == 2
    assert owner.budget("images")["reserved"] == 1


def test_same_session_thread_state_updates_are_serialized(store: SessionStore) -> None:
    session = store.get_or_create()

    def increment(_: int) -> None:
        other = store.get_or_create(session.token)
        with other.transaction() as state:
            state["counter"] = state.get("counter", 0) + 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(increment, range(30)))
    assert session.load_state()["counter"] == 30


def test_processes_share_atomic_budgets_and_session_state(store: SessionStore) -> None:
    session = store.get_or_create()
    script = """
import json, os
from cogniguard.runtime.sessions import SessionStore, BudgetExceeded
session = SessionStore(os.environ['CG_TEST_DB']).get_or_create(os.environ['CG_TEST_TOKEN'])
success = 0
for index in range(5):
    with session.transaction() as state:
        state['counter'] = state.get('counter', 0) + 1
    try:
        session.reserve('images', 1, str(os.getpid()) + '-' + str(index))
        success += 1
    except BudgetExceeded:
        pass
print(json.dumps(success))
"""
    env = {**os.environ, "CG_TEST_DB": str(store.path), "CG_TEST_TOKEN": session.token}
    root = Path(__file__).resolve().parents[1]
    children = [
        subprocess.Popen(
            [sys.executable, "-c", script],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    outputs = [child.communicate(timeout=30) for child in children]
    assert all(child.returncode == 0 for child in children), [err for _, err in outputs]
    assert sum(json.loads(out) for out, _ in outputs) == 2
    assert session.load_state()["counter"] == 20
    assert session.budget("images")["reserved"] == 2
