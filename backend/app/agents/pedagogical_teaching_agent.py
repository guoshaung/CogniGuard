from __future__ import annotations

from typing import Any

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


class PedagogicalTeachingAgent(BaseAgent):
    """Generates protected teaching responses from minimum approved context."""

    def __init__(self, llm_client: Any | None = None) -> None:
        super().__init__(
            agent_id="pedagogical_teaching_agent",
            agent_name="PedagogicalTeachingAgent",
            role=(
                "Generate explanations, hints, scaffolded teaching steps, and "
                "guided responses from approved minimum context and C2-RAG snippets."
            ),
            allowed_inputs=(
                "context_card",
                "diagnosis_result",
                "controlled_resource_snippets",
            ),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
        )

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)

        def fallback() -> dict[str, Any]:
            diagnosis = payload["diagnosis_result"]
            snippets = payload["controlled_resource_snippets"]
            knowledge_point = str(diagnosis.get("knowledge_point", "the concept"))
            strategy = str(
                diagnosis.get(
                    "suggested_teaching_strategy",
                    "step_by_step_scaffold_with_error_check",
                )
            )
            snippet_text = _join_snippets(snippets)

            answer = (
                f"Let's work on {knowledge_point} with a scaffolded path.\n"
                "1. First, identify the key form or rule in the problem.\n"
                "2. Next, compare each known condition with that rule.\n"
                "3. Then solve one small step at a time and check the common "
                "mistake before moving on.\n"
                f"Approved resource cue: {snippet_text}\n"
                "Try explaining the next step in your own words before seeing "
                "another example."
            )
            return {
                "teaching_answer": answer,
                "teaching_strategy_used": strategy,
            }

        result = self._llm_json_or_fallback(
            system_prompt=(
                "You are PedagogicalTeachingAgent. Use only the minimum context "
                "card, diagnosis_result, and C2-RAG controlled snippets. Do not "
                "reproduce full teacher resources or reveal private profile data. "
                "Return teaching_answer and teaching_strategy_used."
            ),
            payload=payload,
            fallback=fallback,
        )
        result = _normalize_teaching(result, fallback())
        self.log_agent_call(
            {
                "context_card": summarize_text(payload["context_card"]),
                "snippet_count": len(payload["controlled_resource_snippets"]),
            },
            {"teaching_answer": summarize_text(result["teaching_answer"])},
        )
        return result


def _join_snippets(snippets: Any) -> str:
    if not isinstance(snippets, list) or not snippets:
        return "No protected resource snippet was needed."
    contents = []
    for snippet in snippets[:3]:
        if isinstance(snippet, dict):
            mode = snippet.get("return_mode", "summary")
            content = summarize_text(snippet.get("content", ""), 160)
            contents.append(f"[{mode}] {content}")
    return " ".join(contents) if contents else "No protected resource snippet was needed."


def _normalize_teaching(
    result: dict[str, Any], fallback_result: dict[str, Any]
) -> dict[str, Any]:
    answer = result.get("teaching_answer")
    strategy = result.get("teaching_strategy_used")
    if not answer or not strategy:
        return fallback_result
    return {
        "teaching_answer": str(answer),
        "teaching_strategy_used": str(strategy),
    }
