"""Pipeline delivery commits disclosure receipts. MySQL failures skip these cases."""

from __future__ import annotations

import hashlib
import os
import uuid
from copy import deepcopy

import pytest

pymysql = pytest.importorskip("pymysql")

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.capability import CapabilityGrant, CapabilityPolicy
from cogniguard.governance.lifecycle import LifecycleGuard
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.gateway import ProtectionGateway
from cogniguard.runtime.protection_context import register_profile_context
from cogniguard.runtime.sessions import SessionStore
from cogniguard.workflows.pipeline import ProtectedText
from core.access import AccessScope
from core.pipeline import ProtectionPipeline, load_inputs
from core.tests.test_focused import INPUTS

_CONNECT_TIMEOUT = 3


def _server_settings() -> dict:
    return {
        "host": os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
        "user": os.environ.get("COGNIGUARD_MYSQL_USER", "root"),
        "password": os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
    }


@pytest.fixture
def disclosure_store():
    settings = _server_settings()
    try:
        probe = pymysql.connect(**settings, connect_timeout=_CONNECT_TIMEOUT)
    except (pymysql.Error, OSError) as exc:
        pytest.skip(f"MySQL is not reachable: {exc}")
    else:
        probe.close()

    database = "cg_pipeline_disclosure_" + uuid.uuid4().hex[:12]
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


def _case():
    config, profiles, questions, resources = load_inputs(*INPUTS)
    question = next(item for item in questions if item["need_resource"])
    profile = deepcopy(profiles[question["student_id"]])
    baseline = ProtectionPipeline(config, resources).run(
        profile, question, access=AccessScope(profile.student_id)
    )
    resource = deepcopy(baseline.controlled.resource)
    return config, profile, question, resource


def _student(profile, question, student_id: str):
    profile = deepcopy(profile)
    question = deepcopy(question)
    profile.student_id = student_id
    question["student_id"] = student_id
    return profile, question


def _released(result):
    controlled = result.controlled
    return (
        None if controlled is None or controlled.resource is None else controlled.resource.resource_id,
        None if controlled is None else controlled.text,
        result.answer,
    )


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


def _output_guard() -> LifecycleGuard:
    return LifecycleGuard(
        CapabilityPolicy(
            [
                CapabilityGrant("service", target, frozenset({"education"}))
                for target in ("teaching", "delivery")
            ]
        )
    )


def test_delivered_unit_appears_in_history(disclosure_store: DisclosureStore) -> None:
    config, profile, question, resource = _case()
    resource.resource_id = "released_resource"
    resource.chunk_id = "released_chunk"
    registry = AccessRegistry(
        [AssetOwnership(resource.resource_id, "teacher-a", "school", 3)],
        [
            Membership(profile.student_id, "school", "student"),
            Membership("teacher-a", "school", "teacher"),
        ],
        [AccessGrant(profile.student_id, resource.resource_id, "tutoring", 3)],
    )
    pipeline = ProtectionPipeline(config, [resource], disclosure_store=disclosure_store)
    result = pipeline.run(
        profile,
        question,
        access=AccessScope(
            profile.student_id, registry=registry, acting_org_id="school"
        ),
    )
    history = disclosure_store.history(profile.student_id)

    assert len(history) == 1
    receipt = history[0]
    assert receipt.resource_id == resource.resource_id
    assert receipt.unit_id == resource.chunk_id
    assert receipt.recipient_principal_id == profile.student_id
    assert receipt.acting_org_id == "school"
    assert receipt.agent_principal_id == "graph-runtime"
    assert receipt.session_id == pipeline.session_id
    assert receipt.policy_version == 3
    assert receipt.status == "delivered"
    assert receipt.content_sha256 == hashlib.sha256(result.controlled.text.encode()).hexdigest()


def test_blocked_output_cancels_the_receipt(disclosure_store: DisclosureStore) -> None:
    config, profile, question, resource = _case()
    resource.resource_id = "blocked_resource"
    resource.chunk_id = "blocked_chunk"
    pipeline = ProtectionPipeline(
        config,
        [resource],
        disclosure_store=disclosure_store,
        guard=_output_guard(),
        watermark=lambda answer, task, sources: ProtectedText(answer, provenance_valid=False),
    )

    with pytest.raises(PermissionError):
        pipeline.run(profile, question, access=AccessScope(profile.student_id))

    stages = [event["stage"] for event in pipeline.last_trace["events"]]
    assert "govern_output" in stages
    assert disclosure_store.history(profile.student_id) == []
    rows = _rows(disclosure_store)
    assert len(rows) == 1
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["resource_id"] == resource.resource_id
    assert rows[0]["unit_id"] == resource.chunk_id


def test_coalition_units_are_the_union_of_two_students(disclosure_store: DisclosureStore) -> None:
    config, profile, question, resource = _case()
    first_resource = deepcopy(resource)
    first_resource.resource_id = "resource_one"
    first_resource.chunk_id = "unit_one"
    second_resource = deepcopy(resource)
    second_resource.resource_id = "resource_two"
    second_resource.chunk_id = "unit_two"
    first_profile, first_question = _student(profile, question, "student-one")
    second_profile, second_question = _student(profile, question, "student-two")
    first = ProtectionPipeline(
        config, [first_resource, second_resource], disclosure_store=disclosure_store
    )
    second = ProtectionPipeline(
        config, [first_resource, second_resource], disclosure_store=disclosure_store
    )

    first.run(
        first_profile,
        first_question,
        access=AccessScope(first_profile.student_id, resource_ids=frozenset({first_resource.resource_id})),
    )
    second.run(
        second_profile,
        second_question,
        access=AccessScope(second_profile.student_id, resource_ids=frozenset({second_resource.resource_id})),
    )

    assert disclosure_store.coalition_units(["student-one", "student-two"]) == frozenset(
        {
            (first_resource.resource_id, first_resource.chunk_id),
            (second_resource.resource_id, second_resource.chunk_id),
        }
    )


def test_without_disclosure_store_matches_the_previous_result() -> None:
    config, profile, question, resource = _case()
    allowed = deepcopy(resource)
    allowed.resource_id = "allowed_resource"
    allowed.chunk_id = "allowed_chunk"
    denied = deepcopy(resource)
    denied.resource_id = "denied_resource"
    denied.chunk_id = "denied_chunk"
    scope = AccessScope(profile.student_id, resource_ids=frozenset({allowed.resource_id}))
    default = ProtectionPipeline(config, [denied, allowed]).run(profile, question, access=scope)
    explicit = ProtectionPipeline(config, [denied, allowed], disclosure_store=None).run(
        profile, question, access=scope
    )

    assert _released(default) == _released(explicit)
    assert default.controlled.resource.resource_id == allowed.resource_id
    assert explicit.controlled.resource.chunk_id == allowed.chunk_id


_GATEWAY_KEY = b"test-only-signing-key-not-for-deploy" * 2
_SAFE_ANSWER = "先识别题目的已知条件。"
_PRIVATE_VALUE = "SERVER-ONLY-IDENTITY-928341"


def _gateway(tmp_path):
    return ProtectionGateway(
        store=SessionStore(
            tmp_path / "sessions.sqlite3",
            limits={"requests": 1000, "privacy": 100, "copyright": 100},
        ),
        provenance=TextProvenanceService(_GATEWAY_KEY, required=True),
        adapter=NeMoGuardrailsAdapter("", enabled=True),
    )


def _run_gateway(gateway, pipeline, profile, question, answer: str, *, private: str | None):
    def operation(frame):
        released = pipeline.run(profile, question, access=AccessScope(profile.student_id))
        if private is not None:
            register_profile_context(private_values=[private])
        return {"answer": answer, "released": released.controlled is not None}

    return gateway.run("case", {}, operation, request_id="disclosure-delivery")


def test_gateway_delivery_commits_the_receipt(disclosure_store: DisclosureStore, tmp_path) -> None:
    config, profile, question, resource = _case()
    resource.resource_id = "gateway_released_resource"
    resource.chunk_id = "gateway_released_chunk"
    pipeline = ProtectionPipeline(config, [resource], disclosure_store=disclosure_store)

    result = _run_gateway(
        _gateway(tmp_path), pipeline, profile, question, _SAFE_ANSWER, private=None
    )

    assert result["output_validation"]["allowed"] is True
    assert result["released"] is True
    history = disclosure_store.history(profile.student_id)
    assert len(history) == 1
    assert history[0].status == "delivered"
    assert history[0].resource_id == resource.resource_id
    rows = _rows(disclosure_store)
    assert len(rows) == 1
    assert rows[0]["status"] == "delivered"


def test_gateway_output_validation_cancels_the_receipt(
    disclosure_store: DisclosureStore, tmp_path
) -> None:
    config, profile, question, resource = _case()
    resource.resource_id = "gateway_blocked_resource"
    resource.chunk_id = "gateway_blocked_chunk"
    pipeline = ProtectionPipeline(config, [resource], disclosure_store=disclosure_store)

    result = _run_gateway(
        _gateway(tmp_path),
        pipeline,
        profile,
        question,
        f"答案里包含 {_PRIVATE_VALUE}",
        private=_PRIVATE_VALUE,
    )

    assert result["output_validation"]["allowed"] is False
    assert disclosure_store.history(profile.student_id) == []
    rows = _rows(disclosure_store)
    assert len(rows) == 1
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["resource_id"] == resource.resource_id
    assert rows[0]["unit_id"] == resource.chunk_id


def test_direct_pipeline_commits_without_gateway(disclosure_store: DisclosureStore) -> None:
    config, profile, question, resource = _case()
    resource.resource_id = "direct_released_resource"
    resource.chunk_id = "direct_released_chunk"
    pipeline = ProtectionPipeline(config, [resource], disclosure_store=disclosure_store)

    pipeline.run(profile, question, access=AccessScope(profile.student_id))

    history = disclosure_store.history(profile.student_id)
    assert len(history) == 1
    assert history[0].status == "delivered"
    assert history[0].resource_id == resource.resource_id
    rows = _rows(disclosure_store)
    assert rows[0]["status"] == "delivered"
