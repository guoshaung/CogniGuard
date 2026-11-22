"""Disclosure receipts are reserved, then committed or cancelled. Time is passed in."""

from __future__ import annotations

import os
import uuid
from threading import Lock, Thread

import pymysql
import pytest

from cogniguard.governance.disclosure import DisclosureStore

_SECRET = "ORIGINAL_TEXT_SHOULD_NOT_BE_STORED"


def _mysql_kwargs(database: str) -> dict:
    return {
        "host": os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
        "user": os.environ.get("COGNIGUARD_MYSQL_USER", "root"),
        "password": os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
        "database": database,
    }


@pytest.fixture
def store():
    database = "cg_disclosure_" + uuid.uuid4().hex[:16]
    kwargs = _mysql_kwargs(database)
    opened = DisclosureStore(**kwargs)
    try:
        yield opened
    finally:
        opened.close()
        admin = pymysql.connect(
            host=kwargs["host"],
            port=kwargs["port"],
            user=kwargs["user"],
            password=kwargs["password"],
            autocommit=True,
        )
        try:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            admin.close()


def _reserve(store: DisclosureStore, **overrides) -> str:
    fields = {
        "resource_id": "r1",
        "unit_id": "u1",
        "recipient_principal_id": "s1",
        "acting_org_id": "school",
        "agent_principal_id": "agent-1",
        "session_id": "session-1",
        "policy_version": 1,
        "content": _SECRET,
        "created_at": 10.0,
    }
    fields.update(overrides)
    return store.reserve(**fields)


def test_commit_puts_the_receipt_in_history(store: DisclosureStore) -> None:
    receipt_id = _reserve(store, created_at=12.5)
    store.commit(receipt_id)
    history = store.history("s1")

    assert len(history) == 1
    receipt = history[0]
    assert receipt.receipt_id == receipt_id
    assert receipt.status == "delivered"
    assert receipt.created_at == 12.5
    assert receipt.content_sha256 != _SECRET
    assert _SECRET not in receipt.content_sha256


def test_cancel_and_uncommitted_reserve_stay_out_of_history(store: DisclosureStore) -> None:
    cancelled = _reserve(store, unit_id="cancelled", created_at=1.0)
    store.cancel(cancelled)
    _reserve(store, unit_id="still-reserved", created_at=2.0)

    assert store.history("s1") == []


def test_coalition_units_are_the_delivered_union(store: DisclosureStore) -> None:
    first = _reserve(store, recipient_principal_id="s1", resource_id="r1", unit_id="u1", created_at=1.0)
    duplicate = _reserve(store, recipient_principal_id="s2", resource_id="r1", unit_id="u1", created_at=2.0)
    second = _reserve(store, recipient_principal_id="s1", resource_id="r1", unit_id="u2", created_at=3.0)
    third = _reserve(store, recipient_principal_id="s3", resource_id="r2", unit_id="u1", created_at=4.0)
    pending = _reserve(store, recipient_principal_id="s2", resource_id="r9", unit_id="u9", created_at=5.0)
    for receipt_id in (first, duplicate, second, third):
        store.commit(receipt_id)

    units = store.coalition_units(["s1", "s2", "s3"])

    assert units == frozenset({("r1", "u1"), ("r1", "u2"), ("r2", "u1")})
    assert ("r9", "u9") not in units
    assert pending


def test_second_commit_raises(store: DisclosureStore) -> None:
    receipt_id = _reserve(store)
    store.commit(receipt_id)

    with pytest.raises(ValueError):
        store.commit(receipt_id)


def test_ten_threads_commit_exactly_ten_receipts(store: DisclosureStore) -> None:
    errors: list[BaseException] = []
    receipt_ids: list[str] = []
    collected = Lock()

    def worker(index: int) -> None:
        try:
            receipt_id = _reserve(
                store,
                recipient_principal_id="s-concurrent",
                unit_id=f"unit-{index}",
                content=f"{_SECRET}-{index}",
                created_at=float(index),
            )
            store.commit(receipt_id)
            with collected:
                receipt_ids.append(receipt_id)
        except BaseException as exc:
            with collected:
                errors.append(exc)

    threads = [Thread(target=worker, args=(index,)) for index in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    history = store.history("s-concurrent")
    assert len(history) == 10
    assert len({receipt.receipt_id for receipt in history}) == 10
    assert {receipt.receipt_id for receipt in history} == set(receipt_ids)


def test_table_has_no_column_for_original_text(store: DisclosureStore) -> None:
    kwargs = _mysql_kwargs(store._database)
    receipt_id = _reserve(store, content=_SECRET, created_at=7.0)
    store.commit(receipt_id)
    admin = pymysql.connect(
        host=kwargs["host"],
        port=kwargs["port"],
        user=kwargs["user"],
        password=kwargs["password"],
        database=kwargs["database"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with admin.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM disclosure_receipt")
            columns = [row["Field"] for row in cursor.fetchall()]
            cursor.execute("SELECT * FROM disclosure_receipt")
            rows = cursor.fetchall()
    finally:
        admin.close()

    assert columns == [
        "receipt_id",
        "resource_id",
        "unit_id",
        "recipient_principal_id",
        "acting_org_id",
        "agent_principal_id",
        "session_id",
        "policy_version",
        "status",
        "content_sha256",
        "created_at",
    ]
    assert "content" not in columns
    stored = " ".join(str(value) for row in rows for value in row.values())
    assert _SECRET not in stored
