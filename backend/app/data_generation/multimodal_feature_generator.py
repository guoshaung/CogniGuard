from __future__ import annotations

import random
from typing import Any


EMOTION_STATES = ("confused", "neutral", "anxious", "confident")


class MultimodalFeatureGenerator:
    """Creates raw simulated feature signals and low-exposure semantics."""

    def __init__(self, seed: int = 20260526) -> None:
        self.rng = random.Random(seed)

    def generate_audio_features(self, accuracy: float) -> dict[str, Any]:
        struggle = 1.0 - accuracy
        pause_count = self.rng.randint(0, 3) + int(struggle * 6)
        speech_rate = round(self.rng.uniform(80, 145) - struggle * 24, 2)
        hesitation_score = round(min(1.0, self.rng.uniform(0.05, 0.45) + struggle * 0.5), 3)
        confidence_score = round(max(0.05, self.rng.uniform(0.45, 0.9) - struggle * 0.55), 3)
        return {
            "pause_count": pause_count,
            "speech_rate": speech_rate,
            "hesitation_score": hesitation_score,
            "confidence_score": confidence_score,
            "repeated_reading_count": self.rng.randint(0, 1) + int(struggle * 3),
        }

    def generate_emotion_signals(self, accuracy: float) -> dict[str, Any]:
        if accuracy < 0.35:
            emotion_state = self.rng.choice(("confused", "anxious"))
        elif accuracy > 0.75:
            emotion_state = self.rng.choice(("confident", "neutral"))
        else:
            emotion_state = self.rng.choice(EMOTION_STATES)

        frustration_base = {
            "confused": 0.62,
            "anxious": 0.72,
            "neutral": 0.32,
            "confident": 0.18,
        }[emotion_state]
        attention_base = {
            "confused": 0.58,
            "anxious": 0.52,
            "neutral": 0.68,
            "confident": 0.82,
        }[emotion_state]
        return {
            "emotion_state": emotion_state,
            "emotion_confidence": round(self.rng.uniform(0.62, 0.96), 3),
            "attention_level": round(_clamp(attention_base + self.rng.uniform(-0.12, 0.12)), 3),
            "frustration_level": round(
                _clamp(frustration_base + self.rng.uniform(-0.14, 0.14)), 3
            ),
        }

    def generate_handwriting_trace(self, accuracy: float) -> dict[str, Any]:
        point_count = self.rng.randint(24, 54)
        x = self.rng.uniform(12, 30)
        y = self.rng.uniform(20, 42)
        points = []
        for idx in range(point_count):
            x += self.rng.uniform(2.0, 8.5)
            y += self.rng.uniform(-3.2, 3.2)
            points.append({"x": round(x, 2), "y": round(y, 2), "t": idx * self.rng.randint(55, 110)})

        hesitation_count = self.rng.randint(0, 2) + int((1.0 - accuracy) * 4)
        pause_points = sorted(self.rng.sample(range(point_count), k=min(hesitation_count, point_count)))
        return {
            "coordinate_points": points,
            "writing_duration": round(self.rng.uniform(18.0, 95.0) + hesitation_count * 4.8, 2),
            "pause_points": pause_points,
            "erase_count": self.rng.randint(0, 1) + int((1.0 - accuracy) * 3),
            "stroke_speed_mean": round(self.rng.uniform(0.42, 1.55) - (1.0 - accuracy) * 0.22, 3),
            "hesitation_segments": [
                {
                    "start_point": point,
                    "end_point": min(point + self.rng.randint(1, 4), point_count - 1),
                }
                for point in pause_points
            ],
        }

    def build_local_features(
        self,
        history: dict[str, Any],
        image_path: str,
        audio_feature_path: str,
        emotion_signal_path: str,
        handwriting_trace_path: str,
        audio_features: dict[str, Any],
        emotion_signals: dict[str, Any],
        handwriting_trace: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "student_hash": history["student_hash"],
            "task_id": history["task_id"],
            "knowledge_point": history["knowledge_point"],
            "wrong_answer_image_path": image_path,
            "audio_feature_path": audio_feature_path,
            "emotion_signal_path": emotion_signal_path,
            "handwriting_trace_path": handwriting_trace_path,
            "feature_summary": {
                "accuracy": history["accuracy"],
                "pause_count": audio_features["pause_count"],
                "hesitation_score": audio_features["hesitation_score"],
                "emotion_state": emotion_signals["emotion_state"],
                "attention_level": emotion_signals["attention_level"],
                "erase_count": handwriting_trace["erase_count"],
                "hesitation_segment_count": len(handwriting_trace["hesitation_segments"]),
            },
        }

    def build_educational_semantics(
        self,
        history: dict[str, Any],
        audio_features: dict[str, Any],
        emotion_signals: dict[str, Any],
        handwriting_trace: dict[str, Any],
    ) -> dict[str, Any]:
        current_error_type = str((history.get("common_error_types") or ["unknown"])[0])
        learning_signal = _learning_signal(history, audio_features, emotion_signals, handwriting_trace)
        possible_cause = _possible_cause(current_error_type, learning_signal)
        strategy = _strategy_for_signal(learning_signal, current_error_type)
        return {
            "student_hash": history["student_hash"],
            "task_id": history["task_id"],
            "knowledge_point": history["knowledge_point"],
            "current_error_type": current_error_type,
            "learning_signal": learning_signal,
            "possible_cause": possible_cause,
            "suggested_teaching_strategy": strategy,
            "profile_update_candidate": {
                "candidate_type": "short_term_learning_evidence",
                "knowledge_point": history["knowledge_point"],
                "evidence": learning_signal,
                "requires_tpcs_approval": True,
            },
        }


def _learning_signal(
    history: dict[str, Any],
    audio: dict[str, Any],
    emotion: dict[str, Any],
    handwriting: dict[str, Any],
) -> str:
    if (
        history["accuracy"] < 0.45
        or audio["hesitation_score"] > 0.58
        or emotion["frustration_level"] > 0.65
        or handwriting["erase_count"] >= 3
    ):
        return "high_hesitation_with_conceptual_error"
    if history["accuracy"] > 0.75 and emotion["emotion_state"] == "confident":
        return "stable_mastery_signal"
    return "partial_understanding_needs_scaffold"


def _possible_cause(error_type: str, learning_signal: str) -> str:
    if "sign" in error_type or "shift" in error_type or "reverse" in error_type:
        return "symbol_direction_confusion"
    if "balance" in error_type or "ratio" in error_type:
        return "procedure_rule_not_internalized"
    if learning_signal == "high_hesitation_with_conceptual_error":
        return "working_memory_load_and_rule_selection_difficulty"
    return "incomplete_transfer_to_new_problem"


def _strategy_for_signal(learning_signal: str, error_type: str) -> str:
    if learning_signal == "stable_mastery_signal":
        return "brief_confirmation_then_extension_question"
    if "visual" in error_type or "shift" in error_type or "graph" in error_type:
        return "visual_scaffold_then_symbolic_reasoning"
    if learning_signal == "high_hesitation_with_conceptual_error":
        return "micro_step_scaffold_with_error_contrast"
    return "guided_practice_with_targeted_hint"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
