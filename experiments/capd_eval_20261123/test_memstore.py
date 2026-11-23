"""Memory receipt log matches the MySQL log on the same operations."""

from __future__ import annotations

import os
import time
import uuid
from threading import Event, Thread

import pytest

from cogniguard.runtime.disclosure_store import ReleaseBusy

from experiments.capd_eval_20261123.memstore import MemoryDisclosureStore

_CONNECT_TIMEOUT = 3


def _reserve(store, recipient: str, unit_id: str, created_at: float, content: str, exposure: float):
    return store.reserve(
        resource_id="pack",
        unit_id=unit_id,
        recipient_principal_id=recipient,
        acting_org_id="lab",
        agent_principal_id="eval",
        session_id=recipient,
        policy_version=1,
        content=content,
        created_at=created_at,
        exposure_delta=exposure,
    )


def _exercise(store):
    first = _reserve(store, "alice", "u1", 1.0, "alpha", 0.5)
    second = _reserve(store, "alice", "u2", 2.0, "beta", 0.25)
    third = _reserve(store, "bob", "u1", 3.0, "alpha", 0.5)
    fourth = _reserve(store, "alice", "u3", 4.0, "gamma", 1.0)
    store.commit(first)
    store.cancel(second)
    store.commit(third)
    with store.release_section():
        holders = store.holders_of({("pack", "u1"), ("pack", "u2"), ("pack", "u3")})
    return first, second, third, fourth, holders


def _view(store) -> dict:
    history = store.history("alice")
    return {
        "history": [
            (
                item.resource_id,
                item.unit_id,
                item.recipient_principal_id,
                item.status,
                item.content_sha256,
                item.exposure_delta,
                item.acting_org_id,
                item.policy_version,
            )
            for item in history
        ],
        "holders": store.holders_of({("pack", "u1"), ("pack", "u2"), ("pack", "u3")}),
        "coalition": store.coalition_units(["alice", "bob"]),
        "exposure": store.exposure_by_recipient("pack", "u1"),
        "coalition_exposure": store.coalition_exposure("pack", "u1", ["alice", "bob"]),
    }


def test_reserved_rows_count_until_cancelled() -> None:
    store = MemoryDisclosureStore()
    _first, _second, _third, fourth, holders = _exercise(store)
    assert holders["alice"] == frozenset({("pack", "u1"), ("pack", "u3")})
    assert holders["bob"] == frozenset({("pack", "u1")})
    assert ("pack", "u2") not in store.coalition_units(["alice"])
    assert store.history("alice")[0].unit_id == "u1"
    assert store.history("bob")[0].status == "delivered"
    store.commit(fourth)
    with pytest.raises(ValueError):
        store.commit(fourth)
    assert store.coalition_units(["alice"]) == frozenset({("pack", "u1"), ("pack", "u3")})
    assert store.exposure_by_recipient("pack", "u1") == {"alice": 0.5, "bob": 0.5}
    assert store.coalition_exposure("pack", "u1", ["alice"]) == 0.5
    assert store.holders_of(set()) == {}
    assert store.coalition_units([]) == frozenset()


def test_release_section_reports_busy() -> None:
    store = MemoryDisclosureStore()
    started = Event()

    def hold() -> None:
        with store.release_section():
            started.set()
            time.sleep(0.3)

    thread = Thread(target=hold)
    thread.start()
    try:
        assert started.wait(1)
        with pytest.raises(ReleaseBusy):
            with store.release_section(timeout=0.05):
                pass
    finally:
        thread.join()


def test_memory_matches_mysql_on_the_same_operations() -> None:
    pymysql = pytest.importorskip("pymysql")
    settings = {
        "host": os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
        "user": os.environ.get("COGNIGUARD_MYSQL_USER", "root"),
        "password": os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
    }
    try:
        probe = pymysql.connect(**settings, connect_timeout=_CONNECT_TIMEOUT)
    except (pymysql.Error, OSError) as exc:
        pytest.skip(f"MySQL is not reachable: {exc}")
    else:
        probe.close()

    from cogniguard.runtime.disclosure_store import DisclosureStore

    database = "cg_capd_mem_" + uuid.uuid4().hex[:12]
    mysql = DisclosureStore(**settings, database=database)
    memory = MemoryDisclosureStore()
    try:
        _exercise(memory)
        _exercise(mysql)
        assert _view(memory) == _view(mysql)
        with pytest.raises(ValueError):
            memory.commit("missing")
        with pytest.raises(ValueError):
            mysql.commit("missing")
    finally:
        mysql.close()
        admin = pymysql.connect(**settings, autocommit=True, connect_timeout=_CONNECT_TIMEOUT)
        try:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            admin.close()
