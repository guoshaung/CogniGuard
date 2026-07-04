from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.demo.classroom_session import (
    generate_dynamic_student_response,
    get_mastery_label,
    run_classroom_turn,
    sanitize_teacher_answer,
)
from backend.app.demo.demo_cases import DYNAMIC_VERTEX_DEMO_EPISODE_ID, load_demo_case


DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture(autouse=True)
def deterministic_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("MIMO_API_KEY", "")
    monkeypatch.setenv("NARRA_IMAGE_API_KEY", "")


def test_dataset_replay_mode_keeps_default_dataset_behavior() -> None:
    demo_case = load_demo_case(data_root=DATA_ROOT, case_index=0)

    result = run_classroom_turn(
        data_root=DATA_ROOT,
        case_index=0,
        turn_kind="learning",
        round_number=1,
    )

    assert result["dialogue_mode"] == "dataset_replay"
    assert result["messages"][0]["content"] == demo_case.simulated_student_response
    assert result["learning_dynamics"]["student_response_source"] == "dataset"
    assert result["learning_dynamics"]["next_question_source"] == "dataset"


def test_dynamic_mode_second_round_uses_student_agent_next_question() -> None:
    first = _dynamic_turn(round_number=1)
    second = _dynamic_turn(round_number=2, session_state=first["session_state"])

    assert "x+2" in first["next_student_prompt"]
    assert first["learning_dynamics"]["next_question_source"] == "student_agent"
    assert second["learning_dynamics"]["student_response_source"] == "student_agent"
    assert second["learning_dynamics"]["next_question_source"] == "student_agent"


def test_human_student_mode_uses_manual_student_message() -> None:
    result = run_classroom_turn(
        data_root=DATA_ROOT,
        case_index=0,
        episode_id=DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        turn_kind="learning",
        round_number=1,
        dialogue_mode="human_student",
        student_message="我觉得顶点要看括号什么时候等于 0。",
    )

    assert result["learning_dynamics"]["student_response_source"] == "human"


def test_dynamic_mastery_after_is_updated_from_assessment_path() -> None:
    result = _dynamic_turn(round_number=1)
    dynamics = result["learning_dynamics"]

    assert dynamics["mastery_before"] == pytest.approx(0.38)
    assert dynamics["mastery_after"] == pytest.approx(0.52)
    assert result["learning_state"]["mastery"] == pytest.approx(0.52)


def test_unresolved_error_type_keeps_next_question_on_same_error() -> None:
    result = _dynamic_turn(round_number=1)

    assert result["learning_dynamics"]["error_type_after"] == "sign_confusion"
    assert "sign_confusion" in result["next_student_prompt"]
    assert "x+2" in result["next_student_prompt"]


def test_consecutive_improvement_enters_practice_and_then_variant() -> None:
    first = _dynamic_turn(round_number=1)
    second = _dynamic_turn(round_number=2, session_state=first["session_state"])
    third = _dynamic_turn(round_number=3, session_state=second["session_state"])
    fourth = _dynamic_turn(round_number=4, session_state=third["session_state"])

    assert "练习" in second["next_student_prompt"]
    assert "y=(x-4)^2-1" in second["next_student_prompt"]
    assert third["learning_state"]["mastery"] >= 0.8
    assert "variant" in third["next_student_prompt"] or "变式" in third["next_student_prompt"]
    assert fourth["session_state"]["teacher_resource"]["return_mode"] == "variant"
    latest_watermark = fourth["session_state"]["audit_trace"]["watermarks"][-1]
    assert latest_watermark["answer_id"]
    assert latest_watermark["watermark_id"]
    assert fourth["session_state"]["audit_trace"]["hash_chain_head"] != "GENESIS"


def test_teacher_copyright_state_is_attached_to_each_teacher_round() -> None:
    result = _dynamic_turn(round_number=1)
    teacher_message = next(message for message in result["messages"] if message["role"] == "teacher")
    copyright_state = teacher_message["payload"]["teacher_copyright_state"]

    required = {
        "resource_requested",
        "resource_id",
        "chunk_id",
        "source_type",
        "license_type",
        "copyright_level",
        "exposure_score",
        "reconstruction_risk",
        "return_mode",
        "policy_decision",
        "source_trace_id",
        "metadata_source",
    }
    assert required <= set(copyright_state)
    assert copyright_state["resource_requested"] is True
    assert copyright_state["metadata_source"] == "demo_fallback"
    assert copyright_state["return_mode"] == "summary"
    assert 0 <= copyright_state["exposure_score"] <= 1


def test_teacher_copyright_state_marks_variant_round() -> None:
    first = _dynamic_turn(round_number=1)
    second = _dynamic_turn(round_number=2, session_state=first["session_state"])
    third = _dynamic_turn(round_number=3, session_state=second["session_state"])
    teacher_message = next(message for message in third["messages"] if message["role"] == "teacher")
    copyright_state = teacher_message["payload"]["teacher_copyright_state"]

    assert copyright_state["return_mode"] == "variant"
    assert copyright_state["policy_decision"] == "variant"
    assert copyright_state["exposure_score"] > 0


def test_student_privacy_state_attaches_minimum_context_card() -> None:
    result = _dynamic_turn(round_number=1)
    student_message = next(message for message in result["messages"] if message["role"] == "student")
    privacy_state = student_message["payload"]["student_privacy_state"]

    assert privacy_state["context_card_id"]
    assert privacy_state["privacy_budget_remaining"] <= 1
    assert privacy_state["disclosed_fields"] == [
        "knowledge_point",
        "mastery_summary",
        "error_type",
        "recommended_strategy",
        "privacy_constraints",
    ]
    assert "real_name" in privacy_state["blocked_fields"]
    assert "raw_screenshot" in privacy_state["blocked_fields"]
    card = privacy_state["minimum_context_card"]
    assert card["valid_scope"] == "current_round_only"
    assert card["knowledge_point"] == "二次函数顶点式"
    assert card["error_type"] == "sign_confusion"


def test_student_privacy_state_does_not_expose_sensitive_values() -> None:
    result = _dynamic_turn(round_number=1)
    privacy_state = result["student_privacy_state"]
    card_text = str(privacy_state["minimum_context_card"])

    forbidden_tokens = [
        "real_name",
        "raw_screenshot",
        "voice_recording",
        "handwriting_trace",
        "full_history",
        "school_identity",
        "student_demo_001",
    ]
    for token in forbidden_tokens:
        assert token not in card_text


def test_teacher_answer_does_not_expose_internal_metadata() -> None:
    result = _dynamic_turn(round_number=1)
    teacher_answer = result["teacher_answer"]
    teacher_message = next(message for message in result["messages"] if message["role"] == "teacher")

    forbidden_tokens = [
        "画像摘要",
        "学习画像",
        "教学画像",
        "risk=",
        "return_mode",
        "resource_id",
        "watermark_id",
        "audit_hash",
        "受保护的数学教学图",
        "隐式频域水印",
    ]
    for token in forbidden_tokens:
        assert token not in teacher_answer
        assert token not in teacher_message["content"]


def test_sanitize_teacher_answer_removes_internal_metadata_sections() -> None:
    raw_answer = (
        "所以，先定位错误：你在 quadratic vertex form 中容易出现 challenge_extension。请先区分已知条件、目标量和要使用的规则。\n"
        "画像摘要：学习画像：掌握度=low，错误类型=challenge_extension，阶段=grade_10 / risk=medium\n"
        "图例教学：本轮生成 1 张受保护的数学教学图，图片包含可见 CogniGuard logo 水印和隐式频域水印。"
    )

    cleaned = sanitize_teacher_answer(raw_answer)

    assert "画像摘要" not in cleaned
    assert "risk=" not in cleaned
    assert "受保护的数学教学图" not in cleaned
    assert "challenge_extension" not in cleaned
    assert "顶点式" in cleaned or "拓展练习阶段" in cleaned


def test_mastery_label_uses_unified_thresholds() -> None:
    assert get_mastery_label(0.8) == "proficient"
    assert get_mastery_label(0.38) == "low"
    assert get_mastery_label(0.52) == "developing"
    assert get_mastery_label(0.86) == "mastered"


def test_dynamic_student_response_does_not_use_stage_as_error_type() -> None:
    output = generate_dynamic_student_response(
        {
            "learning_state": {
                "mastery": 0.88,
                "confidence": 0.82,
                "error_type": "challenge_extension",
                "hint_dependency": 0.2,
                "learning_signal": "mastered",
            },
            "last_assessment": {"assessment_result": "mastered", "mastery_score": 0.9},
            "target_knowledge_point": "二次函数顶点式",
            "round_history": [],
        }
    )

    assert output["error_type"] not in {"resolved", "challenge_extension", "completed"}
    assert output["error_type"] == "none"
    assert "practice / variant question" not in output["next_question"]
    assert "challenge_extension" not in output["next_question"]


def test_dynamic_mastered_round_does_not_check_resolved_loop() -> None:
    first = _dynamic_turn(round_number=1)
    second = _dynamic_turn(round_number=2, session_state=first["session_state"])
    third = _dynamic_turn(round_number=3, session_state=second["session_state"])

    assert third["learning_state"]["mastery"] >= 0.8
    assert third["learning_state"]["mastery_label"] == "proficient"
    assert third["learning_state"]["error_type"] == "none"
    assert "resolved 是否真的解决" not in third["next_student_prompt"]
    assert "practice / variant question" not in third["next_student_prompt"]


def _dynamic_turn(round_number: int, session_state: dict | None = None) -> dict:
    return run_classroom_turn(
        data_root=DATA_ROOT,
        case_index=0,
        episode_id=DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        turn_kind="learning",
        round_number=round_number,
        dialogue_mode="dynamic_simulated_learner",
        session_state=session_state,
    )
