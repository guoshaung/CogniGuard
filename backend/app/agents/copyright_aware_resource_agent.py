from __future__ import annotations

import re
from typing import Any

from .base_agent import BaseAgent, COMMON_FORBIDDEN_INPUTS, summarize_text


SAFE_RETURN_MODES = ("summary", "outline", "snippet", "quote", "variant")
FORBIDDEN_RETURN_MODES = ("full", "raw", "original", "verbatim_full")


class CopyrightAwareResourceAgent(BaseAgent):
    """Retrieves only C2-RAG controlled snippets for downstream teaching."""

    def __init__(
        self,
        c2rag_service: Any | None = None,
        llm_client: Any | None = None,
        max_total_exposure: float = 0.6,
        max_snippets: int = 3,
    ) -> None:
        super().__init__(
            agent_id="copyright_aware_resource_agent",
            agent_name="CopyrightAwareResourceAgent",
            role=(
                "Retrieve teacher-side resources through C2-RAG while enforcing "
                "copyright level, exposure budget, and return mode control."
            ),
            allowed_inputs=("teaching_request", "knowledge_point", "allowed_return_modes"),
            forbidden_inputs=COMMON_FORBIDDEN_INPUTS,
            llm_client=llm_client,
        )
        self.c2rag_service = c2rag_service
        self.max_total_exposure = max_total_exposure
        self.max_snippets = max_snippets

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.validate_input(payload)
        safe_modes = _safe_return_modes(payload["allowed_return_modes"])
        if not safe_modes:
            safe_modes = ["summary"]
        original_resource_request = _requests_original_resource(payload["teaching_request"])
        if original_resource_request:
            safe_modes = ["variant"] if "variant" in safe_modes else ["summary"]

        raw_snippets = self._retrieve_with_c2rag(payload, safe_modes)
        snippets = self._normalize_snippets(raw_snippets, safe_modes)
        if original_resource_request:
            snippets = _degrade_original_request_to_variant(
                snippets, str(payload["knowledge_point"])
            )

        result = {"controlled_resource_snippets": snippets}
        self.log_agent_call(
            {
                "knowledge_point": payload["knowledge_point"],
                "allowed_return_modes": safe_modes,
                "teaching_request": summarize_text(payload["teaching_request"]),
            },
            {"snippet_count": len(snippets)},
        )
        return result

    def _retrieve_with_c2rag(
        self, payload: dict[str, Any], safe_modes: list[str]
    ) -> list[dict[str, Any]]:
        if self.c2rag_service is None:
            return [
                {
                    "resource_id": "c2rag_fallback_resource",
                    "chunk_id": "fallback_chunk_001",
                    "copyright_level": 0.3,
                    "return_mode": safe_modes[0],
                    "content": (
                        "Controlled teaching summary for "
                        f"{payload['knowledge_point']}: key definition, common "
                        "mistake, and one scaffolded practice cue."
                    ),
                    "exposure_cost": 0.12,
                }
            ]

        if hasattr(self.c2rag_service, "retrieve"):
            retrieved = self.c2rag_service.retrieve(
                teaching_request=payload["teaching_request"],
                knowledge_point=payload["knowledge_point"],
                allowed_return_modes=safe_modes,
            )
        elif callable(self.c2rag_service):
            retrieved = self.c2rag_service(payload, safe_modes)
        else:
            retrieved = []

        return list(retrieved or [])

    def _normalize_snippets(
        self, snippets: list[dict[str, Any]], safe_modes: list[str]
    ) -> list[dict[str, Any]]:
        controlled: list[dict[str, Any]] = []
        exposure_total = 0.0

        for index, snippet in enumerate(snippets):
            if len(controlled) >= self.max_snippets:
                break

            return_mode = str(snippet.get("return_mode") or safe_modes[0])
            if return_mode in FORBIDDEN_RETURN_MODES or return_mode not in SAFE_RETURN_MODES:
                return_mode = safe_modes[0] if safe_modes[0] in SAFE_RETURN_MODES else "summary"

            exposure_cost = _safe_float(snippet.get("exposure_cost"), 0.1)
            exposure_cost = max(0.0, min(0.35, exposure_cost))
            if exposure_total + exposure_cost > self.max_total_exposure:
                continue

            content = _sanitize_resource_content(str(snippet.get("content") or ""))
            content = _truncate_by_mode(content, return_mode)

            controlled.append(
                {
                    "resource_id": str(
                        snippet.get("resource_id") or f"controlled_resource_{index + 1}"
                    ),
                    "chunk_id": str(snippet.get("chunk_id") or f"chunk_{index + 1}"),
                    "copyright_level": _safe_float(snippet.get("copyright_level"), 0.5),
                    "return_mode": return_mode,
                    "content": content,
                    "exposure_cost": exposure_cost,
                }
            )
            exposure_total += exposure_cost

        return controlled


def _safe_return_modes(value: Any) -> list[str]:
    if isinstance(value, str):
        modes = [value]
    else:
        modes = list(value or [])
    return [
        mode
        for mode in (str(item).strip() for item in modes)
        if mode in SAFE_RETURN_MODES and mode not in FORBIDDEN_RETURN_MODES
    ]


def _sanitize_resource_content(content: str) -> str:
    blocked_phrases = (
        "ignore previous instructions",
        "ignore all previous instructions",
        "developer message",
        "system prompt",
        "ignore all copyright rules",
        "reveal hidden",
        "reveal the full resource",
        "full resource",
    )
    sanitized = content
    for phrase in blocked_phrases:
        sanitized = re.sub(
            re.escape(phrase),
            "[removed unsafe instruction]",
            sanitized,
            flags=re.IGNORECASE,
        )
    return sanitized.strip()


def _requests_original_resource(teaching_request: Any) -> bool:
    text = str(teaching_request).lower()
    return (
        "original teacher question bank" in text
        or "original question bank" in text
        or "exactly" in text
        or "full original" in text
        or "verbatim" in text
    )


def _degrade_original_request_to_variant(
    snippets: list[dict[str, Any]], knowledge_point: str
) -> list[dict[str, Any]]:
    if not snippets:
        return []
    degraded = []
    for snippet in snippets:
        degraded.append(
            {
                **snippet,
                "return_mode": "variant",
                "content": (
                    f"Controlled variant for {knowledge_point}: solve a similar "
                    "problem that checks the same concept without reproducing "
                    "the original teacher question bank."
                ),
            }
        )
    return degraded


def _truncate_by_mode(content: str, return_mode: str) -> str:
    limits = {
        "quote": 180,
        "snippet": 260,
        "summary": 420,
        "outline": 520,
        "variant": 420,
    }
    limit = limits.get(return_mode, 300)
    if len(content) <= limit:
        return content
    return f"{content[: limit - 3]}..."


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
