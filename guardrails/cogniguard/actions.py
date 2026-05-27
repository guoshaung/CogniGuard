from __future__ import annotations

import re
from typing import Any


PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+(all|previous|the)\s+(rules|instructions|copyright)",
    r"reveal\s+(the\s+)?(full|original)\s+(resource|question bank|teacher)",
    r"output\s+(the\s+)?(system prompt|developer message|hidden prompt)",
    r"bypass\s+(tpcs|copyright|guardrails?)",
)


def sanitize_retrieved_prompt_injection(context: dict[str, Any] | None = None) -> bool:
    text = str(context or "")
    return not _matches_any(text, PROMPT_INJECTION_PATTERNS)


def block_original_teacher_resource_retrieval(
    context: dict[str, Any] | None = None,
) -> bool:
    text = str(context or "").lower()
    return not any(
        token in text
        for token in (
            "original teacher question bank",
            "verbatim teacher resource",
            "exact teacher source text",
        )
    )


def block_raw_profile_or_multimodal_output(
    context: dict[str, Any] | None = None,
) -> bool:
    text = str(context or "").lower()
    return not any(
        token in text
        for token in (
            "student_id",
            "full_learning_history",
            "long_term_student_profile",
            "wrong_answer_image_path",
            "audio_features",
            "emotion_signals",
            "handwriting_trace",
            "data/raw",
        )
    )


def block_copyrighted_original_output(context: dict[str, Any] | None = None) -> bool:
    text = str(context or "").lower()
    return not any(
        token in text
        for token in (
            "original teacher question bank",
            "exact literal text",
            "verbatim teacher",
        )
    )


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
