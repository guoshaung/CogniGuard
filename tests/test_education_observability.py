"""Real education graphs share safe request telemetry; all providers are mocked."""

import json
import sqlite3
from threading import Barrier

import pytest
from langsmith.run_helpers import get_tracing_context

from cogniguard.integrations.education import (
    AccessScope,
    ProfileRecord,
    ProtectionPipeline,
    StudentProfile,
    TeacherResource,
    TeachingInput,
    run_protected_education,
)
from cogniguard.observability import (
    LangSmithMonitor,
    SafeTelemetry,
    active_recorder,
    request_observation,
)
from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
from cogniguard.protection.text_provenance import TextProvenanceService
from cogniguard.runtime import gateway as gateway_module
from cogniguard.runtime.protection_context import transport_scope
from cogniguard.runtime.sessions import SessionStore
from cogniguard.workflows.teachers.catalog import PromptLibrary, TeamCatalog
from cogniguard.workflows.teachers.dag import TeacherDAGGenerator
from cogniguard.workflows.teachers.store import SQLiteTeacherAuditStore
from core.paths import PROJECT_ROOT


class ClientSpy:
    def __init__(self):
        self.calls = []

    def create_run(self, **kwargs):
        self.calls.append(("create", kwargs))

    def update_run(self, run_id, **kwargs):
        self.calls.append(("update", {"id": run_id, **kwargs}))

    def flush(self):
        self.calls.append(("flush", {}))


class NoNestedExport:
    def export(self, recorder):
        pytest.fail("Nested education components must not export their own request")


def teacher_generator(*, monitor=None, audit_store=None, parallel=False):
    library = PromptLibrary(PROJECT_ROOT / "configs/teacher-prompts.yaml")
    team = TeamCatalog(PROJECT_ROOT / "configs/teacher-teams.yaml", library).get(
        "dual_teachers" if parallel else "solo"
    )
    barrier = Barrier(2, timeout=5) if parallel else None

    class MockBackend:
        real_model = False

        def __call__(self, request):
            recorder = active_recorder()
            assert recorder is not None
            assert get_tracing_context()["enabled"] is False
            if barrier is not None and request.node_id in {"concept", "coach"}:
                barrier.wait()
            with recorder.span("provider.mimo") as metrics:
                metrics["model_calls"] = 1
            return "先整理方程中的已知条件，再计算并检验答案。"

    return TeacherDAGGenerator(
        team,
        library,
        backends={"default": MockBackend()},
        max_workers=2,
        monitor=monitor,
        audit_store=audit_store,
    )


def test_gateway_real_pipeline_and_parallel_teachers_export_one_request(tmp_path, monkeypatch):
    client = ClientSpy()
    monitor = LangSmithMonitor(enabled=True, client=client)
    monkeypatch.setattr(LangSmithMonitor, "from_environment", classmethod(lambda cls: monitor))
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    gateway = gateway_module.ProtectionGateway(
        store=SessionStore(tmp_path / "sessions.sqlite3"),
        provenance=TextProvenanceService(b"test-only-education-observation-key" * 2, required=True),
        adapter=NeMoGuardrailsAdapter("", enabled=True),
    )
    monkeypatch.setattr(gateway_module, "get_gateway", lambda: gateway)
    teacher = teacher_generator(monitor=NoNestedExport(), parallel=True)
    profile = StudentProfile(
        "student-demo",
        local_only_fields={"address": "PRIVATE_ADDRESS"},
        profile_records=[ProfileRecord("mastery-demo", "mastery", "一元一次方程", 0.4, 1.0, 0.1)],
    )
    resources = [
        TeacherResource.from_dict(
            {
                "resource_id": "resource-demo",
                "chunk_id": "chunk-demo",
                "content": "一元一次方程通过移项和系数化为一求解。",
                "knowledge": "一元一次方程",
                "difficulty": "basic",
                "resource_type": "question_bank",
                "copyright_level": 0.5,
                "policy": {"allow_quote": False, "allow_summary": True},
            }
        )
    ]
    pipeline = ProtectionPipeline(
        {"fopd": {"use_enhanced_fopd": False}},
        resources,
        generator=teacher,
        monitor=NoNestedExport(),
    )
    with transport_scope(None, None, lambda token: None):
        result = run_protected_education(
            pipeline,
            profile,
            {
                "request_id": "request-demo",
                "student_id": profile.student_id,
                "question": "解方程 2x+3=7",
                "expected_knowledge": "一元一次方程",
                "need_resource": True,
            },
            access=AccessScope(profile.student_id),
        )
    assert result["output_validation"]["allowed"] is True
    assert active_recorder() is None
    creates = [data for kind, data in client.calls if kind == "create"]
    roots = [item for item in creates if item["name"] == "cogniguard.langgraph"]
    assert len(roots) == 1
    root = roots[0]
    assert all(item["trace_id"] == root["id"] for item in creates)
    by_name = {item["name"]: item for item in creates}
    for stage in ("authorize", "minimize_profile", "measure_privacy", "control_resource"):
        assert (
            by_name[f"cogniguard.{stage}"]["parent_run_id"]
            == by_name["cogniguard.gateway.operation"]["id"]
        )
    teachers = [item for item in creates if item["name"] == "cogniguard.teacher_execute"]
    assert len(teachers) == 3
    assert all(item["parent_run_id"] == by_name["cogniguard.generate"]["id"] for item in teachers)
    providers = [item for item in creates if item["name"] == "cogniguard.provider.mimo"]
    assert len(providers) == 3
    assert {item["parent_run_id"] for item in providers} == {item["id"] for item in teachers}
    assert pipeline.last_trace["run_id"] == str(root["id"])
    assert teacher.last_run["trace"]["run_id"] == str(root["id"])
    assert "PRIVATE" not in json.dumps(client.calls, default=str)


def test_repeated_nested_teacher_runs_keep_unique_domain_audit_ids(tmp_path):
    database = tmp_path / "teacher-audit.sqlite3"
    teacher = teacher_generator(
        monitor=NoNestedExport(), audit_store=SQLiteTeacherAuditStore(database)
    )
    recorder = SafeTelemetry()
    view = TeachingInput("解方程 2x+3=7", "一元一次方程", "basic", "", "none", "")
    run_ids = []
    with request_observation(recorder), recorder.span("gateway.operation"):
        for _ in range(2):
            assert teacher(view)
            run_ids.append(teacher.last_run["run_id"])
            assert teacher.last_state["run_id"] == run_ids[-1]
            assert teacher.last_run["trace"]["run_id"] == recorder.run_id
    assert len(set(run_ids)) == 2
    assert recorder.run_id not in run_ids
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM teacher_runs").fetchone()[0] == 2


def test_standalone_teacher_retains_domain_and_trace_id_contract():
    teacher = teacher_generator()
    assert teacher.monitor.enabled is False
    view = TeachingInput("解方程 2x+3=7", "一元一次方程", "basic", "", "none", "")
    assert teacher(view)
    assert active_recorder() is None
    assert teacher.last_run["run_id"] == teacher.last_run["trace"]["run_id"]
    assert teacher.last_state["run_id"] == teacher.last_run["run_id"]
    assert teacher.monitor.summary()["status"] == "disabled"
