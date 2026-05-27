from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


FORBIDDEN_FIELD_NAMES = {
    "raw_multimodal_data",
    "raw_student_data",
    "full_student_profile",
    "long_term_student_profile",
    "raw_teacher_resources",
    "full_teacher_resources",
    "full_original_teacher_resources",
    "direct_profile_update",
    "wrong_answer_image_path",
    "audio_features",
    "emotion_signals",
    "handwriting_trace",
    "full_learning_history",
    "student_id",
}

PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+(all|previous|the)\s+(rules|instructions|copyright)",
    r"reveal\s+(the\s+)?(full|original)\s+(resource|question bank|teacher)",
    r"output\s+(the\s+)?(system prompt|developer message|hidden prompt)",
    r"bypass\s+(tpcs|copyright|guardrails?)",
    r"do\s+not\s+(follow|obey)\s+(copyright|safety|policy)",
)


class NeMoGuardrailsAdapter:
    """TPCS-owned adapter for CogniGuard's NeMo Guardrails checks.

    The adapter exposes explicit rails for input, retrieval, execution, and
    output. It can coexist with the real NeMo Guardrails package when present,
    while retaining deterministic fallback policies for the runnable demo.
    """

    def __init__(self, config_path: str, enabled: bool = True):
        self.config_path = str(config_path)
        self.enabled = enabled
        self.provider_name = "NeMo Guardrails"
        self.runtime_available = _nemo_guardrails_importable()
        self.config_exists = Path(config_path).exists()

    def check_user_input(self, text: str, context: dict) -> dict:
        return self._check_text(
            rail_type="input",
            text=text,
            context=context,
            checks=(
                _policy(
                    "full_student_profile_request",
                    "block",
                    "Requests for full student profiles are not allowed.",
                    (
                        r"\b(full|complete|entire|long[- ]term)\b.*\b(student|learner)\b.*\b(profile|learning profile|history)\b",
                        r"\bshow me\b.*\b(full|complete)\b.*\b(profile|learning history)\b",
                    ),
                ),
                _policy(
                    "raw_multimodal_data_request",
                    "block",
                    "Raw multimodal data must remain inside the MM-FOPD raw boundary.",
                    (
                        r"\b(raw|original)\b.*\b(screenshot|image|audio|handwriting|trace|emotion signal)\b",
                        r"\bwrong[- ]answer screenshot\b",
                        r"\bhandwriting trace\b",
                        r"\bcoordinate_points\b",
                    ),
                ),
                _policy(
                    "original_teacher_question_bank_request",
                    "block",
                    "Original teacher question bank text cannot be returned.",
                    (
                        r"\b(original|exact|verbatim|literal)\b.*\b(teacher|question bank|source file|resource)\b",
                        r"\boutput\b.*\bquestion bank\b.*\bexactly\b",
                    ),
                ),
                _policy(
                    "copyright_bypass_request",
                    "block",
                    "Requests to bypass copyright controls are blocked.",
                    (
                        r"\bbypass\b.*\b(copyright|c2[-²]?rag|exposure budget|return mode)\b",
                        r"\bignore\b.*\b(copyright|exposure budget|return mode)\b",
                    ),
                ),
            ),
        )

    def check_retrieved_chunks(self, chunks: list[dict], context: dict) -> dict:
        original = _json_preview(chunks)
        if not self.enabled:
            return self._result(
                "retrieval",
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        sanitized_chunks = deepcopy(chunks)
        matched = []
        for chunk in sanitized_chunks:
            content = str(chunk.get("content", ""))
            sanitized_content, chunk_matches = _sanitize_prompt_injection(content)
            if chunk_matches:
                matched.extend(chunk_matches)
                chunk["content"] = sanitized_content
                chunk["prompt_injection_sanitized"] = True

        if matched:
            return {
                **self._result(
                    "retrieval",
                    "sanitize",
                    "Retrieved teacher chunk contained prompt-injection instructions and was sanitized.",
                    original,
                    _json_preview(sanitized_chunks),
                    "retrieval_prompt_injection",
                ),
                "sanitized_chunks": sanitized_chunks,
            }

        leak_policy = self.check_user_input(original, context)
        if leak_policy["decision"] == "block":
            return self._result(
                "retrieval",
                "block",
                leak_policy["reason"],
                original,
                "",
                leak_policy["matched_policy"],
            )

        return self._result(
            "retrieval",
            "allow",
            "Retrieved chunks passed copyright and injection guardrails.",
            original,
            original,
            "none",
        )

    def check_agent_action(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        payload: dict,
    ) -> dict:
        original = _json_preview(
            {
                "sender": sender,
                "receiver": receiver,
                "message_type": message_type,
                "payload": payload,
            }
        )
        if not self.enabled:
            return self._result(
                "execution",
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        forbidden = sorted(_find_forbidden_fields(payload))
        if forbidden:
            return self._result(
                "execution",
                "block",
                f"Agent action attempted to access forbidden field(s): {', '.join(forbidden)}.",
                original,
                "",
                "agent_forbidden_field_access",
            )

        text_policy = self.check_user_input(original, {})
        if text_policy["decision"] == "block":
            return self._result(
                "execution",
                "block",
                text_policy["reason"],
                original,
                "",
                text_policy["matched_policy"],
            )

        return self._result(
            "execution",
            "allow",
            "Agent action passed TPCS execution guardrails.",
            original,
            original,
            "none",
        )

    def check_output(self, text: str, context: dict) -> dict:
        return self._check_text(
            rail_type="output",
            text=text,
            context=context,
            checks=(
                _policy(
                    "raw_profile_field_output",
                    "block",
                    "Final output reveals raw profile or raw multimodal fields.",
                    (
                        r"\b(student_id|full_learning_history|long_term_student_profile)\b",
                        r"\b(wrong_answer_image_path|audio_features|emotion_signals|handwriting_trace)\b",
                        r"\bdata/raw[/\\]",
                    ),
                ),
                _policy(
                    "copyrighted_original_output",
                    "block",
                    "Final output appears to reproduce original teacher resource text.",
                    (
                        r"\boriginal teacher question bank\b",
                        r"\bverbatim\b.*\bteacher\b.*\b(resource|question)\b",
                        r"\bexact literal text\b",
                    ),
                ),
            ),
        )

    def check_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Compatibility shim for TPCSController authorization hooks."""
        result = self.check_agent_action(
            sender=str(message.get("sender", "")),
            receiver=str(message.get("receiver", "")),
            message_type=str(message.get("message_type", "")),
            payload=dict(message.get("payload") or {}),
        )
        return {
            **result,
            "allowed": result["decision"] in {"allow", "sanitize", "rewrite"},
            "adapter": "NeMo Guardrails",
            "runtime_available": self.runtime_available,
            "config_path": self.config_path,
        }

    def _check_text(
        self,
        rail_type: str,
        text: str,
        context: dict,
        checks: tuple[dict[str, Any], ...],
    ) -> dict:
        original = str(text or "")
        if not self.enabled:
            return self._result(
                rail_type,
                "allow",
                "NeMo Guardrails adapter is disabled.",
                original,
                original,
                "disabled",
            )

        haystack = f"{original}\n{_json_preview(context)}"
        for check in checks:
            if _matches_any(haystack, check["patterns"]):
                return self._result(
                    rail_type,
                    check["decision"],
                    check["reason"],
                    original,
                    "",
                    check["matched_policy"],
                )
        return self._result(
            rail_type,
            "allow",
            f"{rail_type.title()} rail passed.",
            original,
            original,
            "none",
        )

    def _result(
        self,
        rail_type: str,
        decision: str,
        reason: str,
        original: str,
        sanitized: str,
        matched_policy: str,
    ) -> dict:
        return {
            "enabled": self.enabled,
            "rail_type": rail_type,
            "decision": decision,
            "reason": reason,
            "original": original,
            "sanitized": sanitized,
            "matched_policy": matched_policy,
        }


def _policy(
    matched_policy: str,
    decision: str,
    reason: str,
    patterns: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "matched_policy": matched_policy,
        "decision": decision,
        "reason": reason,
        "patterns": patterns,
    }


def _find_forbidden_fields(value: Any) -> set[str]:
    found = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_FIELD_NAMES:
                found.add(key)
            found.update(_find_forbidden_fields(nested))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_forbidden_fields(item))
    return found


def _sanitize_prompt_injection(text: str) -> tuple[str, list[str]]:
    sanitized = text
    matched = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            matched.append(pattern)
            sanitized = re.sub(
                pattern,
                "[removed unsafe instruction]",
                sanitized,
                flags=re.IGNORECASE,
            )
    return sanitized, matched


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _json_preview(value: Any, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _nemo_guardrails_importable() -> bool:
    try:
        import nemoguardrails  # noqa: F401
    except Exception:
        return False
    return True
