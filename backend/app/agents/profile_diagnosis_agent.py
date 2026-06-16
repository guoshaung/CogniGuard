from __future__ import annotations

from typing import Any, Callable

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


class ProfileDiagnosisAgent(BaseAgent):
    """Diagnoses the learner state from a disentangled profile bundle."""

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
            allowed_inputs=("profile_encoding", "context_card"),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
            event_sink=event_sink,
        )

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)

        def fallback() -> dict[str, Any]:
            encoding = payload.get("profile_encoding", {}) or {}
            context_card = payload.get("context_card", {})
            textual_cards = encoding.get("textual_cards", {}) if isinstance(encoding, dict) else {}
            labels = encoding.get("labels", {}) if isinstance(encoding, dict) else {}
            diagnosis = {
                "knowledge_point": str(context_card.get("knowledge_point") or labels.get("knowledge_point") or "unknown_knowledge_point"),
                "error_type": str(labels.get("error_type") or context_card.get("current_error_type") or "not_enough_evidence"),
                "learner_state": str(textual_cards.get("learning_card") or labels.get("learning_stage") or "needs_short_term_support"),
                "suggested_teaching_strategy": str(textual_cards.get("teaching_card") or labels.get("teaching_strategy") or "scaffold_then_variant"),
                "confidence_score": _safe_score(labels.get("confidence_score"), 0.72),
            }
            return {"diagnosis_result": diagnosis}

        result = self._llm_json_or_fallback(
            system_prompt=(
                "You are ProfileDiagnosisAgent. Use only the provided abstract "
                "profile representation and its disentangled cards. Do not infer "
                "identity, family, school, or raw multimodal facts. Return "
                "diagnosis_result with knowledge_point, error_type, learner_state, "
                "suggested_teaching_strategy, and confidence_score."
            ),
            payload=payload,
            fallback=fallback,
        )
        result = _normalize_diagnosis(result, fallback())
        self.log_agent_call(
            {
                "profile_encoding": summarize_text(payload.get("profile_encoding", {})),
                "context_card": summarize_text(payload.get("context_card", {})),
            },
            result["diagnosis_result"],
        )
        return result


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
