from __future__ import annotations

import re
from typing import Any, Callable

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


class ProfileDiagnosisAgent(BaseAgent):
    """Diagnoses the learner state from an MM-FOPD minimum context card only."""

    def __init__(
        self,
        llm_client: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            agent_id="profile_diagnosis_agent",
            agent_name="ProfileDiagnosisAgent",
            role=(
                "Diagnose the learner's current knowledge state, error type, "
                "learning preference, and short-term learning difficulty."
            ),
            allowed_inputs=("context_card",),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
            event_sink=event_sink,
        )

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)

        def fallback() -> dict[str, Any]:
            context_card = payload["context_card"]
            context_text = _context_to_text(context_card)
            diagnosis = {
                "knowledge_point": _extract_field(
                    context_card, context_text, ("knowledge_point", "knowledge")
                ),
                "error_type": _extract_from_text(
                    context_text,
                    ("common_error", "error_type", "常见错误", "错误类型"),
                    default="not_enough_evidence",
                ),
                "learner_state": _extract_from_text(
                    context_text,
                    ("learner_state", "mastery_state", "相关掌握状态", "学习状态"),
                    default="needs_short_term_support",
                ),
                "suggested_teaching_strategy": _extract_from_text(
                    context_text,
                    ("suggested_teaching_strategy", "recommended_strategy", "推荐策略"),
                    default=_strategy_from_context(context_text),
                ),
                "confidence_score": _confidence_from_context(context_text),
            }
            return {"diagnosis_result": diagnosis}

        result = self._llm_json_or_fallback(
            system_prompt=(
                "You are ProfileDiagnosisAgent. Use only the MM-FOPD minimum "
                "context card. Do not infer identity, family, school, or raw "
                "multimodal facts. Return diagnosis_result with knowledge_point, "
                "error_type, learner_state, suggested_teaching_strategy, and "
                "confidence_score."
            ),
            payload=payload,
            fallback=fallback,
        )
        result = _normalize_diagnosis(result, fallback())
        self.log_agent_call(
            {"context_card": summarize_text(payload["context_card"])},
            result["diagnosis_result"],
        )
        return result


def _context_to_text(context_card: Any) -> str:
    if isinstance(context_card, dict):
        parts = [f"{key}: {value}" for key, value in context_card.items()]
        return "\n".join(parts)
    return str(context_card or "")


def _extract_field(context_card: Any, text: str, keys: tuple[str, ...]) -> str:
    if isinstance(context_card, dict):
        for key in keys:
            value = context_card.get(key)
            if value:
                return str(value)
    return _extract_from_text(text, keys, default="unknown_knowledge_point")


def _extract_from_text(text: str, labels: tuple[str, ...], default: str) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]\s*([^\n;；]+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return default


def _strategy_from_context(text: str) -> str:
    lowered = text.lower()
    if "图像" in text or "visual" in lowered:
        return "visual_scaffold_then_symbolic_reasoning"
    if "不稳定" in text or "unstable" in lowered:
        return "step_by_step_scaffold_with_error_check"
    return "concise_explanation_with_guided_practice"


def _confidence_from_context(text: str) -> float:
    signals = sum(
        1
        for token in ("知识点", "knowledge", "错误", "error", "策略", "state")
        if token in text
    )
    return min(0.9, 0.45 + signals * 0.1)


def _normalize_diagnosis(
    result: dict[str, Any], fallback_result: dict[str, Any]
) -> dict[str, Any]:
    diagnosis = result.get("diagnosis_result")
    if not isinstance(diagnosis, dict):
        return fallback_result

    base = fallback_result["diagnosis_result"]
    normalized = {
        "knowledge_point": str(diagnosis.get("knowledge_point") or base["knowledge_point"]),
        "error_type": str(diagnosis.get("error_type") or base["error_type"]),
        "learner_state": str(diagnosis.get("learner_state") or base["learner_state"]),
        "suggested_teaching_strategy": str(
            diagnosis.get("suggested_teaching_strategy")
            or base["suggested_teaching_strategy"]
        ),
        "confidence_score": _safe_score(
            diagnosis.get("confidence_score"), base["confidence_score"]
        ),
    }
    return {"diagnosis_result": normalized}


def _safe_score(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
