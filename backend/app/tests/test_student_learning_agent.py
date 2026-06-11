from __future__ import annotations

from backend.app.agents.mimo_client import build_student_llm_client
from backend.app.agents.student_learning_agent import StudentLearningAgent


def test_student_agent_fallback_responds_and_asks_next_question() -> None:
    agent = StudentLearningAgent()

    result = agent.generate(
        {
            "teacher_answer": "Explain the structure before calculating.",
            "knowledge_point": "arithmetic sequence",
            "current_mastery": 0.55,
            "target_mastery": 0.85,
            "round_number": 3,
            "previous_student_message": "How do I choose the rule?",
            "assessment_feedback": {},
        }
    )

    assert result["student_response"]
    assert result["next_question"]
    assert result["model_role"] == "bounded_weaker_student"
    assert 0 <= result["self_reported_confidence"] <= 1


def test_student_model_can_be_configured_separately(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "test-key")
    monkeypatch.setenv("MIMO_STUDENT_MODEL", "mimo-v2-flash")

    client = build_student_llm_client()

    assert client is not None
    assert client.model == "mimo-v2-flash"
    assert client.max_tokens == 420
