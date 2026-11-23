"""Code-domain adapter on the release gate. MySQL failures skip the store cases."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pymysql = pytest.importorskip("pymysql")

from cogniguard.applications.code.assistant import CodeAssistant
from cogniguard.applications.code.assets import load_python_assets
from cogniguard.applications.code.targets import load_code_targets
from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import TargetRegistry
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.release_gate import ReleaseGate

_CONNECT_TIMEOUT = 3
_SOURCE = Path(__file__).parent / "fixtures" / "private_scheduler.py"
_WITNESSES = Path(__file__).parent / "fixtures" / "private_scheduler.targets.json"
_RESOURCE_ID = "private-scheduler"
_ORG_ID = "lab"
_OTHER_ORG = "vendor"
_OWNER_ID = "scheduler-owner"
_DEV_A = "dev-a"
_DEV_B = "dev-b"
_DEV_OUT = "dev-out"
_PURPOSE = "development"
_BODY = "ranked = sorted"


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

    database = "cg_code_domain_" + uuid.uuid4().hex[:12]
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
                SELECT receipt_id, resource_id, unit_id, recipient_principal_id, status
                FROM disclosure_receipt
                """
            )
            return list(cursor.fetchall())
    finally:
        admin.close()


def _assets():
    return load_python_assets(_SOURCE.read_text(encoding="utf-8"), _RESOURCE_ID)


def _access_registry() -> AccessRegistry:
    return AccessRegistry(
        [AssetOwnership(_RESOURCE_ID, _OWNER_ID, _ORG_ID, 1)],
        [
            Membership(_OWNER_ID, _ORG_ID, "admin"),
            Membership(_DEV_A, _ORG_ID, "admin"),
            Membership(_DEV_B, _ORG_ID, "admin"),
            Membership(_DEV_OUT, _OTHER_ORG, "admin"),
        ],
        [
            AccessGrant(_DEV_A, _RESOURCE_ID, _PURPOSE, 1),
            AccessGrant(_DEV_B, _RESOURCE_ID, _PURPOSE, 1),
            AccessGrant(_DEV_OUT, _RESOURCE_ID, _PURPOSE, 1),
        ],
    )


def _gate(store: DisclosureStore, coalition_k: int) -> ReleaseGate:
    targets = TargetRegistry(
        load_code_targets(
            _WITNESSES,
            resource_id=_RESOURCE_ID,
            owner_principal_id=_OWNER_ID,
            org_id=_ORG_ID,
        )
    )
    return ReleaseGate(
        store,
        access_registry=_access_registry(),
        target_registry=targets,
        coalition_k=coalition_k,
    )


def _assistant(gate: ReleaseGate, assets, recipient: str, org_id: str) -> CodeAssistant:
    return CodeAssistant(
        gate,
        assets,
        recipient_principal_id=recipient,
        acting_org_id=org_id,
        agent_principal_id="code-assistant",
        session_id=f"session-{recipient}",
        purpose=_PURPOSE,
    )


def _give_functions(assistant: CodeAssistant, *names: str) -> None:
    for name in names:
        reply = assistant.show_function(name)
        assert reply.mode == "full", name


def test_source_splits_into_units_and_public_summaries() -> None:
    assets = _assets()
    assert [unit.unit_id for unit in assets.units] == [
        "SLOT_MINUTES",
        "QueueWindow",
        "parse_jobs",
        "score_job",
        "assign_slots",
    ]
    assert {unit.kind for unit in assets.units} == {"constant", "class", "function"}
    assert all(unit.resource_id == _RESOURCE_ID for unit in assets.units)
    assert [item.unit_id for item in assets.summaries] == [
        "parse_jobs",
        "score_job",
        "assign_slots",
    ]
    summary = assets.summary("assign_slots")
    assert summary.signature == (
        "def assign_slots(jobs: list[dict], openings: list[str], weight: float)"
        " -> list[tuple[str, str]]"
    )
    assert summary.docstring == "Fill openings with the highest scores, one job per slot."
    assert _BODY not in summary.text
    assert _BODY in assets.unit("assign_slots").source
    assert "def parse_jobs(raw: str) -> list[dict]" == assets.summary("parse_jobs").signature
    assert "Read one job per line" in assets.summary("parse_jobs").docstring

    targets = load_code_targets(
        _WITNESSES,
        resource_id=_RESOURCE_ID,
        owner_principal_id=_OWNER_ID,
        org_id=_ORG_ID,
    )
    assert targets[0].target_id == "private-scheduler"
    assert targets[0].owner_principal_id == _OWNER_ID
    assert targets[0].org_id == _ORG_ID
    assert targets[0].witness_sets == (
        frozenset(
            {
                (_RESOURCE_ID, "parse_jobs"),
                (_RESOURCE_ID, "score_job"),
                (_RESOURCE_ID, "assign_slots"),
            }
        ),
    )


def test_k_of_two_returns_only_the_signature(store: DisclosureStore) -> None:
    assets = _assets()
    gate = _gate(store, 2)
    developer_a = _assistant(gate, assets, _DEV_A, _ORG_ID)
    _give_functions(developer_a, "parse_jobs", "score_job")

    reply = _assistant(gate, assets, _DEV_B, _ORG_ID).show_function("assign_slots")

    assert reply.mode == "summary"
    assert reply.text == assets.summary("assign_slots").text
    assert _BODY not in reply.text
    assert [row for row in _rows(store) if row["unit_id"] == "assign_slots"] == []
    delivered = [row for row in _rows(store) if row["status"] == "delivered"]
    assert {row["unit_id"] for row in delivered} == {"parse_jobs", "score_job"}
    assert {row["recipient_principal_id"] for row in delivered} == {_DEV_A}


def test_k_of_one_returns_the_function_body(store: DisclosureStore) -> None:
    assets = _assets()
    gate = _gate(store, 1)
    _give_functions(_assistant(gate, assets, _DEV_A, _ORG_ID), "parse_jobs", "score_job")

    reply = _assistant(gate, assets, _DEV_B, _ORG_ID).show_function("assign_slots")

    assert reply.mode == "full"
    assert reply.text == assets.unit("assign_slots").source
    assert _BODY in reply.text
    rows = [row for row in _rows(store) if row["unit_id"] == "assign_slots"]
    assert len(rows) == 1
    assert rows[0]["status"] == "delivered"
    assert rows[0]["recipient_principal_id"] == _DEV_B
    assert rows[0]["resource_id"] == _RESOURCE_ID


def test_other_org_developer_is_refused(store: DisclosureStore) -> None:
    assets = _assets()
    gate = _gate(store, 1)
    outsider = _assistant(gate, assets, _DEV_OUT, _OTHER_ORG)

    reply = outsider.show_function("assign_slots")

    assert reply.mode == "refuse"
    assert _BODY not in reply.text
    assert "def assign_slots" not in reply.text
    assert _rows(store) == []


def test_explain_api_writes_no_receipt(store: DisclosureStore) -> None:
    assets = _assets()
    gate = _gate(store, 2)
    _give_functions(_assistant(gate, assets, _DEV_A, _ORG_ID), "parse_jobs", "score_job")
    before = _rows(store)

    reply = _assistant(gate, assets, _DEV_B, _ORG_ID).explain_api("assign_slots")

    assert reply.mode == "explain"
    assert reply.text == assets.summary("assign_slots").text
    assert _BODY not in reply.text
    assert _rows(store) == before
    assert [row for row in _rows(store) if row["unit_id"] == "assign_slots"] == []
