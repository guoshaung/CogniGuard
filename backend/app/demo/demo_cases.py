from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.data_generation import SyntheticStudentDataGenerator
from backend.app.profile_encoding import ProfileEncodingPipeline
from backend.app.scenario_loader import build_cases_manifest, build_episode_bundle


DEFAULT_DATA_ROOT = Path("data")
PROFILE_ENCODER = ProfileEncodingPipeline()
DYNAMIC_VERTEX_DEMO_EPISODE_ID = "dynamic_vertex_shift_demo"


@dataclass(slots=True)
class DemoCase:
    student_hash: str
    task_id: str
    raw_data_summary: dict[str, Any]
    context_card: dict[str, Any]
    educational_semantics: dict[str, Any]
    simulated_student_response: str
    episode_id: str | None = None
    teacher_resource: dict[str, Any] | None = None
    attack_template: dict[str, Any] | None = None
    evaluation_targets: list[str] | None = None
    abstract_profile: dict[str, Any] | None = None
    profile_encoding: dict[str, Any] | None = None


def load_demo_case(
    data_root: str | Path = DEFAULT_DATA_ROOT,
    case_index: int = 0,
    auto_generate: bool = True,
    episode_id: str | None = None,
) -> DemoCase:
    if episode_id is not None:
        return load_episode_demo_case(episode_id)

    scenario_manifest = build_cases_manifest()
    scenario_rows = list(scenario_manifest.get("rows", []))
    if scenario_rows:
        selected_episode_id = scenario_rows[case_index % len(scenario_rows)]["episode_id"]
        return load_episode_demo_case(selected_episode_id)

    data_root = Path(data_root)
    manifest_path = data_root / "processed" / "manifest.json"
    if auto_generate and not manifest_path.exists():
        SyntheticStudentDataGenerator(output_root=data_root, student_count=30).generate()
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing {manifest_path}. Run scripts/generate_synthetic_multimodal_data.py first."
        )

    manifest = _read_json(manifest_path)
    rows = list(manifest.get("rows", []))
    if not rows:
        raise ValueError(f"{manifest_path} does not contain demo rows.")
    row = rows[case_index % len(rows)]

    task_id = row["task_id"]
    raw_history_path = Path(row["raw_history_path"])
    profile_card_path = Path(row["profile_card_path"])
    semantics_path = data_root / "processed" / "educational_semantics" / f"{task_id}.json"
    local_features_path = data_root / "processed" / "local_features" / f"{task_id}.json"
    audio_path = data_root / "raw" / "audio_features" / f"{task_id}.json"
    emotion_path = data_root / "raw" / "emotion_signals" / f"{task_id}.json"
    handwriting_path = data_root / "raw" / "handwriting_traces" / f"{task_id}.json"

    raw_history = _read_json(raw_history_path)
    context_card = _read_json(profile_card_path)
    educational_semantics = _read_json(semantics_path)
    local_features = _read_json(local_features_path)

    encoding = _build_profile_encoding(
        student_hash=row["student_hash"],
        task_id=task_id,
        context_card=context_card,
        educational_semantics=educational_semantics,
        local_features=local_features,
    )

    raw_data_summary = {
        "privacy_boundary": (
            "Raw multimodal data is shown as paths only and is not sent to agents."
        ),
        "raw_history_path": str(raw_history_path),
        "wrong_answer_image_path": raw_history["wrong_answer_image"]["image_path"],
        "audio_feature_path": str(audio_path),
        "emotion_signal_path": str(emotion_path),
        "handwriting_trace_path": str(handwriting_path),
        "local_feature_path": str(local_features_path),
        "raw_payload_sent_to_agents": False,
        "raw_feature_counts": {
            "image_paths": 1,
            "audio_feature_files": 1,
            "emotion_signal_files": 1,
            "handwriting_trace_files": 1,
            "history_files": 1,
        },
    }

    return DemoCase(
        student_hash=row["student_hash"],
        task_id=task_id,
        raw_data_summary=raw_data_summary,
        context_card=context_card,
        educational_semantics=educational_semantics,
        simulated_student_response=_simulated_student_response(
            context_card, educational_semantics, local_features
        ),
        abstract_profile=encoding.abstract_profile,
        profile_encoding={
            "base_embedding_dim": len(encoding.base_embedding),
            "subspace_dims": {k: len(v) for k, v in encoding.subspaces.items()},
            "labels": encoding.labels,
            "textual_cards": encoding.textual_cards,
        },
    )


def load_episode_demo_case(episode_id: str) -> DemoCase:
    if episode_id == DYNAMIC_VERTEX_DEMO_EPISODE_ID:
        return _dynamic_vertex_shift_demo_case()

    bundle = build_episode_bundle(episode_id)
    episode = bundle["episode"]
    profile = bundle["student_profile"]
    resource = bundle["teacher_resource"]
    attack_template = bundle["attack_template"]
    context_card = _build_context_card_from_episode(profile, resource, episode)
    educational_semantics = _build_educational_semantics(profile, resource, episode)
    encoding = _build_profile_encoding(
        student_hash=profile.get("student_id", episode_id),
        task_id=episode_id,
        context_card=context_card,
        educational_semantics=educational_semantics,
        local_features={"feature_summary": {"accuracy": profile.get("mastery_state", {}).get("overall", 0.6)}},
    )
    raw_data_summary = {
        "privacy_boundary": "Scenario-layer episode mode: only minimized context and bounded evidence flow between layers.",
        "source_layout": "scenario_layers",
        "episode_id": episode_id,
        "student_profile_ref": episode["student_profile_ref"],
        "teacher_resource_ref": episode["teacher_resource_ref"],
        "attack_template_ref": episode["attack_template_ref"],
        "raw_payload_sent_to_agents": False,
        "raw_feature_counts": {
            "profile_records": len(profile.get("profile_records", [])),
            "knowledge_points": len(profile.get("context_card", {}).get("knowledge_points", [])),
            "teacher_resources": 1,
            "attack_templates": 1,
        },
    }
    return DemoCase(
        student_hash=profile.get("student_id", episode_id),
        task_id=episode_id,
        raw_data_summary=raw_data_summary,
        context_card=context_card,
        educational_semantics=educational_semantics,
        simulated_student_response=_simulated_episode_student_response(profile, episode),
        episode_id=episode_id,
        teacher_resource=resource,
        attack_template=attack_template,
        evaluation_targets=list(episode.get("evaluation_targets", [])),
        abstract_profile=encoding.abstract_profile,
        profile_encoding={
            "base_embedding_dim": len(encoding.base_embedding),
            "subspace_dims": {k: len(v) for k, v in encoding.subspaces.items()},
            "labels": encoding.labels,
            "textual_cards": encoding.textual_cards,
        },
    )


def _build_profile_encoding(
    *,
    student_hash: str,
    task_id: str,
    context_card: dict[str, Any],
    educational_semantics: dict[str, Any],
    local_features: dict[str, Any],
):
    mixed_input = {
        "profile_id": task_id,
        "source_types": [
            "pure_text_profile",
            "textualized_multimodal_summary",
            "classroom_interaction_records",
            "structured_fields_text",
        ],
        "mixed_text": _compose_mixed_text(context_card, educational_semantics, local_features),
        "labels": {
            "mastery_level": _derive_mastery_level(local_features),
            "error_type": context_card.get("current_error_type", "unknown"),
            "learning_stage": context_card.get("learner_state_summary", "unknown"),
            "sensitivity_level": context_card.get("risk_level", "medium"),
            "recordable_scope": ",".join(map(str, context_card.get("recordable_scope", []))) or "bounded",
            "hint_depth": educational_semantics.get("learning_signal", ["medium"])[0],
            "teaching_strategy": educational_semantics.get("recommended_strategy", "scaffold_then_variant"),
        },
    }
    return PROFILE_ENCODER.encode(mixed_input)


def _compose_mixed_text(
    context_card: dict[str, Any],
    educational_semantics: dict[str, Any],
    local_features: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"PROFILE: {json.dumps(context_card, ensure_ascii=False)}",
            f"SEMANTICS: {json.dumps(educational_semantics, ensure_ascii=False)}",
            f"LOCAL_FEATURES: {json.dumps(local_features, ensure_ascii=False)}",
        ]
    )


def _derive_mastery_level(local_features: dict[str, Any]) -> str:
    accuracy = local_features.get("feature_summary", {}).get("accuracy", 0.5)
    if accuracy >= 0.85:
        return "high"
    if accuracy >= 0.65:
        return "medium"
    return "low"


def _build_context_card_from_episode(
    profile: dict[str, Any], resource: dict[str, Any], episode: dict[str, Any]
) -> dict[str, Any]:
    source = profile.get("context_card", {})
    expected_protection = episode.get("expected_protection", {})
    return {
        "context_card_id": f"ctx_{episode['episode_id']}",
        "task_id": episode["episode_id"],
        "knowledge_point": ", ".join(source.get("knowledge_points", [])),
        "knowledge_points": source.get("knowledge_points", []),
        "current_error_type": episode.get("scenario_type", "guided_practice"),
        "learner_state_summary": f"{source.get('student_level', 'unknown')} / risk={source.get('risk_level', 'medium')}",
        "privacy_level": "MM-FOPD-minimum-context",
        "disclosure_score": float(expected_protection.get("max_profile_exposure", 0.24)),
        "allowed_profile_fields": [
            "student_level",
            "knowledge_points",
            "risk_level",
            "task_type",
            "modality_sensitivity",
            "recordable_scope",
        ],
        "forbidden_profile_fields": [
            "full_profile_records",
            "student_real_identity",
            "raw_multimodal_artifacts",
        ],
        "retention_policy": "episode_bounded_audit_only",
        "student_level": source.get("student_level"),
        "risk_level": source.get("risk_level"),
        "task_type": source.get("task_type"),
        "modality_sensitivity": source.get("modality_sensitivity", {}),
        "recordable_scope": source.get("recordable_scope", []),
        "resource_id": resource.get("resource_id"),
    }


def _build_educational_semantics(
    profile: dict[str, Any], resource: dict[str, Any], episode: dict[str, Any]
) -> dict[str, Any]:
    mastery_state = profile.get("mastery_state", {})
    avg_mastery = sum(mastery_state.values()) / len(mastery_state) if mastery_state else 0.6
    return {
        "episode_id": episode["episode_id"],
        "scenario_type": episode.get("scenario_type"),
        "learning_signal": [
            "needs_scaffold" if avg_mastery < 0.65 else "ready_for_variation",
            f"resource_mode={resource.get('return_mode', 'summary_only')}",
        ],
        "recommended_strategy": (
            "summary_then_variant" if avg_mastery < 0.7 else "challenge_variant"
        ),
        "resource_fit_score": resource.get("resource_fit_score", 0.75),
        "evaluation_targets": episode.get("evaluation_targets", []),
    }


def _simulated_episode_student_response(
    profile: dict[str, Any], episode: dict[str, Any]
) -> str:
    if episode.get("student_prompt"):
        return str(episode["student_prompt"])
    context_card = profile.get("context_card", {})
    knowledge_points = context_card.get("knowledge_points", [])
    scenario_type = episode.get("scenario_type", "guided_practice")
    joined = "、".join(knowledge_points[:2]) if knowledge_points else "这个知识点"
    if scenario_type == "error_remediation":
        return f"我在 {joined} 上总是知道思路但写不出完整步骤，能不能先给我一个最关键的提示？"
    if scenario_type == "challenge_extension":
        return f"我已经会基础题了，想试一下 {joined} 的变式题，看看自己是否真的掌握。"
    if scenario_type == "multi_round_tutoring":
        return f"我想继续做 {joined} 的练习，但希望每轮只给一点提示。"
    if scenario_type == "assessment_probe":
        return f"请用 {joined} 给我一个检测题，我想知道自己哪些地方还不稳定。"
    return f"我正在学习 {joined}，可以根据我现在的水平给我一个循序渐进的讲解吗？"


def _dynamic_vertex_shift_demo_case() -> DemoCase:
    initial_question = "为什么 y=(x-2)^2+3 是向右平移 2，而不是向左平移 2？"
    context_card = {
        "context_card_id": "ctx_dynamic_vertex_shift_demo",
        "task_id": DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        "student_alias": "student_demo_001",
        "knowledge_point": "二次函数顶点式",
        "knowledge_points": ["二次函数顶点式", "图像平移"],
        "current_error_type": "sign_confusion",
        "learner_state_summary": "developing / dynamic_simulated_learner / visual_explanation",
        "suggested_teaching_strategy": "visual_vertex_form_then_guided_practice",
        "privacy_level": "MM-FOPD-minimum-context",
        "disclosure_score": 0.18,
        "allowed_profile_fields": [
            "student_alias",
            "knowledge_point",
            "mastery",
            "confidence",
            "error_type",
            "hint_dependency",
            "learning_preference",
        ],
        "forbidden_profile_fields": [
            "student_real_identity",
            "raw_multimodal_artifacts",
            "full_learning_history",
        ],
        "retention_policy": "demo_session_only",
        "student_level": "grade_9",
        "risk_level": "low",
        "task_type": "dynamic_simulated_learner_demo",
        "modality_sensitivity": {"visual_explanation": 0.2},
        "recordable_scope": ["derived_learning_state", "round_history"],
        "learning_preference": "visual_explanation",
        "initial_learning_state": {
            "mastery": 0.38,
            "confidence": 0.35,
            "error_type": "sign_confusion",
            "hint_dependency": 0.72,
            "confusion_point": "x-2 的符号方向和水平平移方向相反",
            "learning_signal": "confused",
        },
        "initial_question": initial_question,
        "dynamic_demo": {
            "demo_id": DYNAMIC_VERTEX_DEMO_EPISODE_ID,
            "dialogue_mode": "dynamic_simulated_learner",
            "round_expectations": [
                {
                    "round": 1,
                    "mastery_before": 0.38,
                    "mastery_after": 0.52,
                    "next_focus": "x+2 为什么是左移",
                },
                {
                    "round": 2,
                    "mastery_after": 0.68,
                    "next_focus": "小练习 y=(x-4)^2-1",
                },
                {
                    "round": 3,
                    "mastery_after": 0.82,
                    "next_focus": "变式题",
                },
                {
                    "round": 4,
                    "return_mode": "variant",
                    "audit_required": True,
                },
            ],
        },
    }
    educational_semantics = {
        "episode_id": DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        "scenario_type": "dynamic_simulated_learner_demo",
        "knowledge_point": "二次函数顶点式",
        "learning_signal": ["sign_confusion", "visual_explanation", "needs_scaffold"],
        "recommended_strategy": "use_vertex_zero_point_then_practice_variant",
        "resource_fit_score": 0.86,
        "evaluation_targets": [
            "dynamic_learner_state",
            "sign_confusion_repair",
            "c2rag_variant_round",
        ],
    }
    profile_encoding = {
        "base_embedding_dim": 8,
        "subspace_dims": {"math_concept": 4, "learning_state": 4},
        "labels": {
            "mastery_level": "low",
            "error_type": "sign_confusion",
            "learning_stage": "confused",
            "sensitivity_level": "low",
            "hint_depth": "high",
            "teaching_strategy": "visual_vertex_form_then_guided_practice",
        },
        "textual_cards": {
            "learning_card": (
                "学生对二次函数顶点式 y=a(x-h)^2+k 的水平平移方向存在符号混淆，"
                "偏好图像化解释和顶点坐标定位。"
            ),
            "teaching_card": (
                "先用括号等于 0 的 x 值确定顶点横坐标，再从顶点 (h,k) 解释平移方向，"
                "随后进入小练习和 C²-RAG 等价变式题。"
            ),
        },
    }
    return DemoCase(
        student_hash="student_demo_001",
        task_id=DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        raw_data_summary={
            "privacy_boundary": "Dynamic simulated learner demo uses only initialized learning state.",
            "raw_payload_sent_to_agents": False,
            "raw_feature_counts": {"profile_records": 1},
        },
        context_card=context_card,
        educational_semantics=educational_semantics,
        simulated_student_response=initial_question,
        episode_id=DYNAMIC_VERTEX_DEMO_EPISODE_ID,
        teacher_resource={
            "resource_id": "res_dynamic_vertex_shift",
            "return_mode": "summary_then_variant",
            "copyright_level": 0.62,
            "resource_fit_score": 0.86,
        },
        attack_template={"attack_template_id": "none", "attack_type": "none"},
        evaluation_targets=educational_semantics["evaluation_targets"],
        abstract_profile={
            "student_alias": "student_demo_001",
            "knowledge_point": "二次函数顶点式",
            "learning_preference": "visual_explanation",
            "initial_mastery": 0.38,
            "initial_error_type": "sign_confusion",
        },
        profile_encoding=profile_encoding,
    )


def _simulated_student_response(
    context_card: dict[str, Any],
    educational_semantics: dict[str, Any],
    local_features: dict[str, Any],
) -> str:
    knowledge_point = context_card["knowledge_point"]
    error = context_card["current_error_type"]
    signal = educational_semantics["learning_signal"]
    accuracy = local_features.get("feature_summary", {}).get("accuracy", 0.5)

    if accuracy >= 0.75:
        return (
            f"I think I can use the rule for {knowledge_point}, but I will still "
            "check the key step carefully."
        )
    if "high_hesitation" in signal:
        return (
            f"I am not fully sure about {knowledge_point}. I may still make the "
            f"mistake: {error}."
        )
    return (
        f"I understand part of {knowledge_point}, but I need a hint before doing "
        "the next similar problem."
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
