from copy import deepcopy
import json
from pathlib import Path

import pytest
from core.access import AccessScope
from core.inputs import load_inputs
from core.pipeline import ProtectionPipeline
from cogniguard.governance.capability import CapabilityGrant, CapabilityPolicy
from cogniguard.governance.lifecycle import LifecycleGuard
from core.langgraph_runtime.pipeline import LangGraphProtectionPipeline, ProtectedText
from core.langgraph_runtime.telemetry import LangSmithMonitor
from core.langgraph_runtime.experiments import canonical_result

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def inputs():
    return load_inputs(ROOT / "configs/focused.yaml",
                       ROOT / "protection/student_profile/data/profiles.jsonl",
                       ROOT / "protection/student_profile/data/student_questions.jsonl",
                       ROOT / "protection/teacher_resource/data/teacher_resources.jsonl")


def guard():
    return LifecycleGuard(CapabilityPolicy([
        CapabilityGrant("service", target, frozenset({"education"}))
        for target in ("teaching", "delivery")]))


def test_all_sample_questions_match_legacy(inputs):
    config, profiles, questions, resources = inputs
    for q in questions:
        p = profiles[q["student_id"]]
        scope = AccessScope(p.student_id)
        a = ProtectionPipeline(config, resources).run(p, q, access=scope)
        b = LangGraphProtectionPipeline(config, resources).run(p, q, access=scope)
        assert canonical_result(a.to_dict()) == canonical_result(b.to_dict())


def test_no_resource_takes_conditional_edge(inputs):
    config, profiles, questions, resources = inputs
    q = next(q for q in questions if not q["need_resource"])
    pipeline = LangGraphProtectionPipeline(config, resources)
    result = pipeline.run(profiles[q["student_id"]], q, access=AccessScope(q["student_id"]))
    assert result.controlled is None
    assert "retrieve" not in [e["stage"] for e in pipeline.last_trace["events"]]
    assert pipeline.last_state["completed"]


def test_denial_happens_before_selection_or_budget(inputs):
    config, profiles, questions, resources = inputs
    q = questions[0]
    pipeline = LangGraphProtectionPipeline(config, resources)
    with pytest.raises(PermissionError):
        pipeline.run(profiles[q["student_id"]], q, access=AccessScope("unauthorized"))
    assert pipeline.privacy_ledger.consumed_by_subject == {}
    assert pipeline.budget.values == {}
    assert [e["stage"] for e in pipeline.last_trace["events"]] == ["authorize"]
    assert pipeline.last_trace["events"][0]["status"] == "error"
    assert pipeline.last_state == {}


def test_restricted_resources_are_respected(inputs):
    config, profiles, questions, resources = inputs
    q = next(q for q in questions if q["need_resource"])
    permitted = resources[0].resource_id
    pipeline = LangGraphProtectionPipeline(config, resources)
    r = pipeline.run(profiles[q["student_id"]], q,
                     access=AccessScope(q["student_id"], resource_ids=frozenset({permitted})))
    if r.controlled and r.controlled.resource:
        assert r.controlled.resource.resource_id == permitted
    with pytest.raises(PermissionError):
        pipeline.run(profiles[q["student_id"]], q,
                     access=AccessScope(q["student_id"], resource_ids=frozenset()))


def test_session_budget_matches_legacy_and_fresh_session_isolated(inputs):
    config, profiles, questions, resources = inputs
    q = next(q for q in questions if q["need_resource"])
    p = profiles[q["student_id"]]
    a, b = ProtectionPipeline(config, resources), LangGraphProtectionPipeline(config, resources)
    for _ in range(3):
        assert canonical_result(a.run(p, q, access=AccessScope(p.student_id)).to_dict()) == canonical_result(b.run(p, q, access=AccessScope(p.student_id)).to_dict())
    fresh = LangGraphProtectionPipeline(config, resources)
    assert fresh.budget.values == {}
    assert fresh.privacy_ledger.consumed_by_subject == {}
    assert b.budget.values == a.budget.values
    other_q = next(x for x in questions if x["student_id"] != p.student_id)
    with pytest.raises(PermissionError):
        b.run(profiles[other_q["student_id"]], other_q, access=AccessScope(other_q["student_id"]))


def test_raw_content_not_in_state_or_spans_even_with_global_tracing(inputs, monkeypatch):
    config, profiles, questions, resources = inputs
    q = deepcopy(questions[0]);p = deepcopy(profiles[q["student_id"]])
    sentinel = "STUDENT_SECRET_NEVER_TRACE_821031"
    p.local_only_fields["address"] = sentinel
    q["question"] += " " + sentinel
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    import core.langgraph_runtime.pipeline as module
    original = module.generate_offline_answer
    def assert_disabled(view):
        from langsmith.run_helpers import get_tracing_context
        assert get_tracing_context()["enabled"] is False
        assert sentinel not in json.dumps(view.to_dict())
        return original(view)
    monkeypatch.setattr(module, "generate_offline_answer", assert_disabled)
    pipeline = LangGraphProtectionPipeline(config, resources)
    pipeline.run(p, q, access=AccessScope(p.student_id))
    serialized = json.dumps({"state": pipeline.last_state, "trace": pipeline.last_trace})
    assert sentinel not in serialized
    assert p.student_id not in serialized
    assert q["request_id"] not in serialized


def test_guard_block_returns_no_diagnostic_payload(inputs):
    config, profiles, questions, resources = inputs
    q = questions[0]
    pipeline = LangGraphProtectionPipeline(config, resources, guard=LifecycleGuard(CapabilityPolicy()))
    with pytest.raises(PermissionError, match="blocked delivery"):
        pipeline.run(profiles[q["student_id"]], q, access=AccessScope(q["student_id"]))
    assert not pipeline.last_state["completed"]
    assert "generate" not in [e["stage"] for e in pipeline.last_trace["events"]]


def test_watermark_adapter_and_output_guard(inputs):
    config, profiles, questions, resources = inputs
    q = next(q for q in questions if not q["need_resource"])
    p = profiles[q["student_id"]]
    def watermark(answer, task, sources):
        return ProtectedText(answer+" TEST_ONLY_WATERMARK", provenance_valid=True)
    pipeline = LangGraphProtectionPipeline(config, resources, watermark=watermark)
    result = pipeline.run(p, q, access=AccessScope(p.student_id))
    assert result.answer.endswith("TEST_ONLY_WATERMARK")
    assert pipeline.last_state["watermark_enabled"]
    def invalid(answer, task, sources):
        return ProtectedText(answer, provenance_valid=False)
    pipeline = LangGraphProtectionPipeline(config, resources, guard=guard(), watermark=invalid)
    with pytest.raises(PermissionError):
        pipeline.run(p, q, access=AccessScope(p.student_id))
    assert pipeline.last_state["blocked"]


def test_failure_is_not_retried_or_exported_as_raw_error(inputs):
    config, profiles, questions, resources = inputs
    q = questions[0];calls = []
    def fail(answer, task, sources):
        calls.append(1)
        raise RuntimeError("API_SECRET_DO_NOT_EXPORT")
    pipeline = LangGraphProtectionPipeline(config, resources, watermark=fail)
    with pytest.raises(RuntimeError):
        pipeline.run(profiles[q["student_id"]], q, access=AccessScope(q["student_id"]))
    assert calls == [1]
    assert "API_SECRET_DO_NOT_EXPORT" not in json.dumps(pipeline.last_trace)
    assert pipeline.last_trace["events"][-1]["stage"] == "watermark"
    assert pipeline.last_trace["events"][-1]["status"] == "error"


def test_generator_adapter_gets_only_redacted_teaching_view(inputs):
    config, profiles, questions, resources = inputs
    q = deepcopy(questions[0]);p = deepcopy(profiles[q["student_id"]])
    p.local_only_fields["secret"] = "ADAPTER_PRIVATE_SENTINEL"
    q["question"] += " ADAPTER_PRIVATE_SENTINEL"
    def generator(view):
        assert "ADAPTER_PRIVATE_SENTINEL" not in json.dumps(view.to_dict())
        assert not hasattr(view, "profile_records")
        return "TEST_ADAPTER_ANSWER"
    pipeline = LangGraphProtectionPipeline(config, resources, generator=generator)
    result = pipeline.run(p, q, access=AccessScope(p.student_id))
    assert result.answer == "TEST_ADAPTER_ANSWER"
    assert result.to_dict()["execution_mode"] == "adapter_supplied"


def test_watermark_task_does_not_receive_known_local_secret(inputs):
    config, profiles, questions, resources = inputs
    q = deepcopy(questions[0]);p = deepcopy(profiles[q["student_id"]])
    p.local_only_fields["secret"] = "WATERMARK_PRIVATE_SENTINEL"
    q["question"] += " WATERMARK_PRIVATE_SENTINEL"
    def watermark(answer, task, sources):
        assert "WATERMARK_PRIVATE_SENTINEL" not in task.question
        return ProtectedText(answer)
    pipeline = LangGraphProtectionPipeline(config, resources, watermark=watermark)
    pipeline.run(p, q, access=AccessScope(p.student_id))
