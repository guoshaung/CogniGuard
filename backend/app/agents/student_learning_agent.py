from __future__ import annotations

from typing import Any, Callable

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


class StudentLearningAgent(BaseAgent):
    """Simulates a bounded learner that improves through teacher feedback."""

    def __init__(
        self,
        llm_client: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            agent_id="student_learning_agent",
            agent_name="StudentLearningAgent",
            role=(
                "Act as a slightly weaker learner. Respond to the teacher, expose "
                "one remaining uncertainty, and ask the next useful question."
            ),
            allowed_inputs=(
                "teacher_answer",
                "knowledge_point",
                "current_mastery",
                "target_mastery",
                "round_number",
                "previous_student_message",
                "assessment_feedback",
            ),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
            event_sink=event_sink,
        )

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)

        def fallback() -> dict[str, Any]:
            round_number = int(payload["round_number"])
            knowledge_point = str(payload["knowledge_point"])
            current_mastery = _safe_score(payload["current_mastery"], 0.4)
            confidence = min(0.92, current_mastery + 0.08)
            responses = [
                (
                    f"我先确认一下：处理 {knowledge_point} 时，要先识别题目结构，"
                    "再选择对应规则。我还不确定怎样快速排除容易混淆的条件。"
                ),
                (
                    f"我能按照步骤处理 {knowledge_point} 的基础题了。"
                    "我想再练习一个条件发生变化的例子，看看方法是否仍然成立。"
                ),
                (
                    f"我现在会先解释为什么使用这个规则，再进行计算。"
                    "如果最后结果不合理，我也会回到条件检查是哪一步出错。"
                ),
                (
                    f"我可以独立完成 {knowledge_point} 的变式题，并用自己的话"
                    "说明结构、规则和验算过程。"
                ),
            ]
            questions = [
                "老师，怎样判断哪个条件是核心条件，哪个只是干扰信息？",
                "可以给我一个结构相同但数字和表述都不同的题吗？",
                "我完成后应该用哪两个检查点判断自己的步骤可靠？",
                "请给我一道迁移题，我想在没有完整提示的情况下独立完成。",
            ]
            index = min(len(responses) - 1, max(0, (round_number - 1) // 2))
            return {
                "student_response": responses[index],
                "next_question": questions[index],
                "self_reported_confidence": round(confidence, 3),
                "remaining_uncertainty": (
                    "independent_transfer"
                    if current_mastery >= 0.75
                    else "strategy_selection"
                ),
                "model_role": "bounded_weaker_student",
            }

        result = self._llm_json_or_fallback(
            system_prompt=(
                "You are StudentLearningAgent, a simulated learner using a smaller "
                "model than the teacher. Read the teacher answer, respond as a "
                "student with imperfect but improving understanding, then ask one "
                "specific next question. Never claim mastery without showing a "
                "reasoning step. Return student_response, next_question, "
                "self_reported_confidence, remaining_uncertainty, and model_role."
            ),
            payload=payload,
            fallback=fallback,
        )
        normalized = _normalize_student_output(result, fallback())
        self.log_agent_call(
            {
                "knowledge_point": payload["knowledge_point"],
                "current_mastery": payload["current_mastery"],
                "teacher_answer": summarize_text(payload["teacher_answer"]),
            },
            {
                "student_response": summarize_text(
                    normalized["student_response"]
                ),
                "next_question": normalized["next_question"],
            },
        )
        return normalized


def _normalize_student_output(
    result: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return fallback
    response = str(result.get("student_response") or "").strip()
    question = str(result.get("next_question") or "").strip()
    if not response or not question:
        return fallback
    return {
        "student_response": response,
        "next_question": question,
        "self_reported_confidence": _safe_score(
            result.get("self_reported_confidence"),
            fallback["self_reported_confidence"],
        ),
        "remaining_uncertainty": str(
            result.get("remaining_uncertainty")
            or fallback["remaining_uncertainty"]
        ),
        "model_role": "bounded_weaker_student",
    }


def _safe_score(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
