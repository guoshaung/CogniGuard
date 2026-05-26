from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.data_generation import SyntheticStudentDataGenerator


DEFAULT_DATA_ROOT = Path("data")


@dataclass(slots=True)
class DemoCase:
    """One synthetic student case split by privacy boundary."""

    student_hash: str
    task_id: str
    raw_data_summary: dict[str, Any]
    context_card: dict[str, Any]
    educational_semantics: dict[str, Any]
    simulated_student_response: str


def load_demo_case(
    data_root: str | Path = DEFAULT_DATA_ROOT,
    case_index: int = 0,
    auto_generate: bool = True,
) -> DemoCase:
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
