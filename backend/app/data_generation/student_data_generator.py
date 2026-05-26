from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .multimodal_feature_generator import MultimodalFeatureGenerator
from .profile_generator import ProfileGenerator
from .wrong_answer_image_generator import WrongAnswerImageGenerator


RAW_FOLDERS = (
    "images",
    "audio_features",
    "handwriting_traces",
    "emotion_signals",
    "history",
)
PROCESSED_FOLDERS = (
    "local_features",
    "educational_semantics",
    "profile_cards",
)


class SyntheticStudentDataGenerator:
    """Generates privacy-separated synthetic multimodal student data."""

    def __init__(
        self,
        output_root: str | Path = "data",
        student_count: int = 30,
        seed: int = 20260526,
    ) -> None:
        self.output_root = Path(output_root)
        self.student_count = student_count
        self.seed = seed
        self.profile_generator = ProfileGenerator(seed=seed)
        self.feature_generator = MultimodalFeatureGenerator(seed=seed + 1)
        self.image_generator = WrongAnswerImageGenerator(seed=seed + 2)

    def generate(self) -> dict[str, Any]:
        self._ensure_folders()
        manifest_rows = []

        for index in range(self.student_count):
            metadata = self.profile_generator.generate_basic_metadata(index)
            task_id = f"task_{index + 1:04d}"
            history = self.profile_generator.generate_learning_history(
                metadata["student_hash"], task_id=task_id
            )
            current_error = self.profile_generator.current_error_for(history)
            question = self.profile_generator.question_for(history["knowledge_point"])

            image_path = self.image_generator.generate_image(
                self.output_root / "raw" / "images" / f"{task_id}.png",
                student_hash=metadata["student_hash"],
                task_id=task_id,
                knowledge_point=history["knowledge_point"],
                question=question,
                error_type=current_error,
            )

            audio_path = self.output_root / "raw" / "audio_features" / f"{task_id}.json"
            emotion_path = self.output_root / "raw" / "emotion_signals" / f"{task_id}.json"
            handwriting_path = (
                self.output_root / "raw" / "handwriting_traces" / f"{task_id}.json"
            )

            audio_features = self.feature_generator.generate_audio_features(
                history["accuracy"]
            )
            emotion_signals = self.feature_generator.generate_emotion_signals(
                history["accuracy"]
            )
            handwriting_trace = self.feature_generator.generate_handwriting_trace(
                history["accuracy"]
            )

            raw_history = {
                "metadata": metadata,
                "history": history,
                "wrong_answer_image": {
                    "image_path": image_path,
                    "exposure_rule": "raw_image_path_only; agents must not receive image bytes",
                },
            }
            local_features = self.feature_generator.build_local_features(
                history=history,
                image_path=image_path,
                audio_feature_path=str(audio_path),
                emotion_signal_path=str(emotion_path),
                handwriting_trace_path=str(handwriting_path),
                audio_features=audio_features,
                emotion_signals=emotion_signals,
                handwriting_trace=handwriting_trace,
            )
            educational_semantics = self.feature_generator.build_educational_semantics(
                history=history,
                audio_features=audio_features,
                emotion_signals=emotion_signals,
                handwriting_trace=handwriting_trace,
            )
            context_card = self._build_context_card(
                metadata=metadata,
                history=history,
                educational_semantics=educational_semantics,
            )

            self._write_json(self.output_root / "raw" / "history" / f"{task_id}.json", raw_history)
            self._write_json(
                audio_path,
                {"student_hash": metadata["student_hash"], "task_id": task_id, **audio_features},
            )
            self._write_json(
                emotion_path,
                {"student_hash": metadata["student_hash"], "task_id": task_id, **emotion_signals},
            )
            self._write_json(
                handwriting_path,
                {"student_hash": metadata["student_hash"], "task_id": task_id, **handwriting_trace},
            )
            self._write_json(
                self.output_root / "processed" / "local_features" / f"{task_id}.json",
                local_features,
            )
            self._write_json(
                self.output_root
                / "processed"
                / "educational_semantics"
                / f"{task_id}.json",
                educational_semantics,
            )
            self._write_json(
                self.output_root / "processed" / "profile_cards" / f"{task_id}.json",
                context_card,
            )

            manifest_rows.append(
                {
                    "student_hash": metadata["student_hash"],
                    "task_id": task_id,
                    "knowledge_point": history["knowledge_point"],
                    "raw_history_path": str(
                        self.output_root / "raw" / "history" / f"{task_id}.json"
                    ),
                    "profile_card_path": str(
                        self.output_root
                        / "processed"
                        / "profile_cards"
                        / f"{task_id}.json"
                    ),
                }
            )

        profile_cards_jsonl = (
            self.output_root / "processed" / "profile_cards" / "profile_cards.jsonl"
        )
        self._write_jsonl(profile_cards_jsonl, self._read_profile_cards())
        manifest = {
            "student_count": self.student_count,
            "privacy_rule": (
                "Raw multimodal data remains under data/raw. Agents may only "
                "receive data from data/processed/profile_cards."
            ),
            "raw_root": str(self.output_root / "raw"),
            "processed_root": str(self.output_root / "processed"),
            "profile_cards_jsonl": str(profile_cards_jsonl),
            "rows": manifest_rows,
        }
        self._write_json(self.output_root / "processed" / "manifest.json", manifest)
        return manifest

    def _build_context_card(
        self,
        metadata: dict[str, Any],
        history: dict[str, Any],
        educational_semantics: dict[str, Any],
    ) -> dict[str, Any]:
        disclosure_score = _disclosure_score(history, educational_semantics)
        return {
            "context_card_id": f"card_{history['task_id']}",
            "student_hash": metadata["student_hash"],
            "task_id": history["task_id"],
            "knowledge_point": educational_semantics["knowledge_point"],
            "current_error_type": educational_semantics["current_error_type"],
            "learner_state_summary": _learner_state_summary(
                history, educational_semantics
            ),
            "suggested_teaching_strategy": educational_semantics[
                "suggested_teaching_strategy"
            ],
            "allowed_profile_fields": [
                "student_hash",
                "task_id",
                "knowledge_point",
                "current_error_type",
                "learner_state_summary",
                "suggested_teaching_strategy",
            ],
            "forbidden_profile_fields": [
                "student_id",
                "raw_multimodal_data",
                "wrong_answer_image_path",
                "audio_features",
                "emotion_signals",
                "handwriting_trace",
                "full_learning_history",
                "long_term_student_profile",
            ],
            "privacy_level": "MM-FOPD-minimum-context",
            "disclosure_score": disclosure_score,
            "retention_policy": {
                "profile_card_ttl_days": 30,
                "raw_data_ttl_days": 7,
                "requires_tpcs_profile_update_approval": True,
            },
        }

    def _ensure_folders(self) -> None:
        for folder in RAW_FOLDERS:
            (self.output_root / "raw" / folder).mkdir(parents=True, exist_ok=True)
        for folder in PROCESSED_FOLDERS:
            (self.output_root / "processed" / folder).mkdir(parents=True, exist_ok=True)

    def _read_profile_cards(self) -> list[dict[str, Any]]:
        cards = []
        card_dir = self.output_root / "processed" / "profile_cards"
        for path in sorted(card_dir.glob("task_*.json")):
            cards.append(json.loads(path.read_text(encoding="utf-8")))
        return cards

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _learner_state_summary(
    history: dict[str, Any], educational_semantics: dict[str, Any]
) -> str:
    if history["accuracy"] < 0.45:
        base = "unstable understanding with frequent errors"
    elif history["accuracy"] > 0.75:
        base = "mostly stable understanding with occasional checks needed"
    else:
        base = "partial understanding that benefits from guided practice"
    return f"{base}; signal={educational_semantics['learning_signal']}"


def _disclosure_score(
    history: dict[str, Any], educational_semantics: dict[str, Any]
) -> float:
    score = 0.18
    score += 0.08 if history["accuracy"] < 0.45 else 0.04
    score += 0.06 if "high_hesitation" in educational_semantics["learning_signal"] else 0.03
    return round(min(0.65, score), 3)
