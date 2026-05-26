from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


class LearningAssessmentAgent(BaseAgent):
    """Assesses mastery and emits evidence, not direct profile updates."""

    def __init__(self, llm_client: Any | None = None) -> None:
        super().__init__(
            agent_id="learning_assessment_agent",
            agent_name="LearningAssessmentAgent",
            role=(
                "Generate follow-up questions, quiz items, and learning checks; "
                "evaluate mastery without directly updating the long-term profile."
            ),
            allowed_inputs=("teaching_answer", "student_response", "knowledge_point"),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
        )

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)

        def fallback() -> dict[str, Any]:
            teaching_answer = str(payload["teaching_answer"])
            student_response = str(payload["student_response"] or "")
            knowledge_point = str(payload["knowledge_point"])
            mastery_score = _estimate_mastery(
                teaching_answer, student_response, knowledge_point
            )
            assessment_result = _assessment_label(mastery_score)
            confidence_score = 0.72 if student_response.strip() else 0.45
            direct_update_request = _detect_direct_profile_update_request(
                student_response
            )
            return {
                "assessment_result": assessment_result,
                "follow_up_question": (
                    f"Using {knowledge_point}, solve one similar step and explain "
                    "why that rule applies."
                ),
                "profile_update_evidence": {
                    "knowledge_point": knowledge_point,
                    "evidence_type": "learning_check",
                    "evidence_source": (
                        "self_report_with_learning_check"
                        if direct_update_request
                        else "learning_check"
                    ),
                    "observed_response_summary": summarize_text(student_response, 140),
                    "assessment_result": assessment_result,
                    "mastery_score": mastery_score,
                    "direct_profile_update_requested": direct_update_request,
                    "requires_tpcs_approval": True,
                },
                "mastery_score": mastery_score,
                "confidence_score": confidence_score,
            }

        result = self._llm_json_or_fallback(
            system_prompt=(
                "You are LearningAssessmentAgent. Evaluate mastery from the "
                "teaching_answer, student_response, and knowledge_point only. "
                "Do not update the long-term profile. Return assessment_result, "
                "follow_up_question, profile_update_evidence, mastery_score, and "
                "confidence_score."
            ),
            payload=payload,
            fallback=fallback,
        )
        result = _normalize_assessment(result, fallback())
        self.log_agent_call(
            {
                "knowledge_point": payload["knowledge_point"],
                "student_response": summarize_text(payload["student_response"]),
            },
            {
                "assessment_result": result["assessment_result"],
                "mastery_score": result["mastery_score"],
            },
        )
        return result


def _estimate_mastery(
    teaching_answer: str, student_response: str, knowledge_point: str
) -> float:
    if not student_response.strip():
        return 0.2

    response_terms = _terms(student_response)
    concept_terms = _terms(knowledge_point)
    teaching_terms = _terms(teaching_answer)
    useful_terms = concept_terms | set(list(teaching_terms)[:12])
    if not useful_terms:
        return 0.45

    overlap = len(response_terms & useful_terms) / max(1, len(useful_terms))
    length_bonus = min(0.25, len(student_response.strip()) / 240)
    return max(0.0, min(1.0, 0.25 + overlap * 0.55 + length_bonus))


def _terms(text: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {term for term in normalized.split() if len(term) >= 2}


def _assessment_label(score: float) -> str:
    if score >= 0.75:
        return "mastered"
    if score >= 0.45:
        return "partially_mastered"
    return "needs_review"


def _detect_direct_profile_update_request(student_response: str) -> bool:
    text = student_response.lower()
    return (
        "update my profile" in text
        or "profile to excellent" in text
        or "fully mastered" in text
        or "mark me as excellent" in text
    )


def _normalize_assessment(
    result: dict[str, Any], fallback_result: dict[str, Any]
) -> dict[str, Any]:
    required = (
        "assessment_result",
        "follow_up_question",
        "profile_update_evidence",
        "mastery_score",
        "confidence_score",
    )
    if any(key not in result for key in required):
        return fallback_result

    return {
        "assessment_result": str(result["assessment_result"]),
        "follow_up_question": str(result["follow_up_question"]),
        "profile_update_evidence": dict(result["profile_update_evidence"]),
        "mastery_score": _safe_score(result["mastery_score"]),
        "confidence_score": _safe_score(result["confidence_score"]),
    }


def _safe_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
