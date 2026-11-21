from __future__ import annotations

import hashlib
import inspect
import json
import math
from typing import Any, Callable

from cogniguard.protection.retrieval import inspect_candidate_resources, retrieval_context
from cogniguard.runtime.protection_context import charge_domain_budget, register_retrieval_context

from cogniguard.agents.roles.base import COMMON_FORBIDDEN_INPUTS, BaseAgent, summarize_text

SAFE_RETURN_MODES = ("summary", "outline", "snippet", "quote", "variant")
FORBIDDEN_RETURN_MODES = ("full", "raw", "original", "verbatim_full")


class CopyrightAwareResourceAgent(BaseAgent):
    """Retrieves only C2-RAG controlled snippets for downstream teaching."""

    def __init__(
        self,
        c2rag_service: Any | None = None,
        llm_client: Any | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        max_total_exposure: float = 0.6,
        max_snippets: int = 3,
        retrieval_guard: Any | None = None,
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
            event_sink=event_sink,
        )
        self.c2rag_service = c2rag_service
        self.max_total_exposure = max_total_exposure
        self.max_snippets = max_snippets
        self.retrieval_guard = retrieval_guard
        self.last_retrieval_context: dict[str, Any] = retrieval_context([], [])

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
        charge_domain_budget("copyright", sum(item["exposure_cost"] for item in snippets))
        # Do not truncate, rewrite or relabel a domain release after its hash
        # and exposure were committed. An original request constrains the modes
        # sent to C2-RAG above; C2-RAG still owns its actual allow/refuse result.
        self.last_retrieval_context["approved_chunks"] = retrieval_context([], snippets)[
            "approved_chunks"
        ]
        self.last_retrieval_context["approved_source_ids"] = list(
            dict.fromkeys(item["resource_id"] for item in snippets)
        )
        register_retrieval_context(
            protected_resources=self.last_retrieval_context["protected_resources"],
            approved_chunks=self.last_retrieval_context["approved_chunks"],
            approved_source_ids=self.last_retrieval_context["approved_source_ids"],
            evidence=self.last_retrieval_context["retrieval_evidence"],
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
        self.last_retrieval_context = retrieval_context([], [])
        inspected_before_release = False

        def inspect_candidates(candidates):
            nonlocal inspected_before_release
            original = list(candidates)
            inspection = inspect_candidate_resources(original, guard=self.retrieval_guard)
            context = retrieval_context(original, [], evidence=inspection.evidence)
            self.last_retrieval_context["protected_resources"].extend(
                context["protected_resources"]
            )
            self.last_retrieval_context["retrieval_evidence"] = dict(inspection.evidence)
            inspected_before_release = True
            return list(inspection.resources)

        if self.c2rag_service is None:
            return inspect_candidates(
                [
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
            )

        if hasattr(self.c2rag_service, "retrieve"):
            retrieve = self.c2rag_service.retrieve
            kwargs = {
                "teaching_request": payload["teaching_request"],
                "knowledge_point": payload["knowledge_point"],
                "allowed_return_modes": safe_modes,
            }
            if "candidate_inspector" in inspect.signature(retrieve).parameters:
                kwargs["candidate_inspector"] = inspect_candidates
            retrieved = retrieve(**kwargs)
        elif callable(self.c2rag_service):
            retrieved = self.c2rag_service(payload, safe_modes)
        else:
            retrieved = []

        released = list(retrieved or [])
        # Also verify the bytes actually returned by the service. Rendering may
        # introduce an instruction after a candidate callback; a release is now
        # bound, so a required rewrite means quarantine rather than mutation.
        inspection = inspect_candidate_resources(released, guard=self.retrieval_guard)
        if not inspected_before_release:
            self.last_retrieval_context = retrieval_context(
                released, [], evidence=inspection.evidence
            )
        else:
            self.last_retrieval_context["retrieval_evidence"].update(
                {
                    "release_decision": inspection.evidence["decision"],
                    "release_checked_count": len(released),
                }
            )
        if inspection.evidence["decision"] == "block" or inspection.evidence["sanitized_count"]:
            return []
        return released

    def _normalize_snippets(
        self, snippets: list[dict[str, Any]], safe_modes: list[str]
    ) -> list[dict[str, Any]]:
        controlled: list[dict[str, Any]] = []
        exposure_total = 0.0

        for index, snippet in enumerate(snippets):
            if len(controlled) >= self.max_snippets:
                break

            return_mode = str(snippet.get("return_mode") or safe_modes[0])
            if return_mode not in safe_modes or return_mode not in SAFE_RETURN_MODES:
                continue

            exposure_cost = _safe_float(snippet.get("exposure_cost"), 0.1)
            if not math.isfinite(exposure_cost) or exposure_cost < 0:
                continue
            if exposure_total + exposure_cost > self.max_total_exposure:
                continue

            content = str(snippet.get("content") or "")
            declared_hash = snippet.get("controlled_output_hash")
            trace_hash = (snippet.get("source_trace") or {}).get("controlled_output_hash")
            digest = hashlib.sha256(
                json.dumps(
                    content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            if any(value and value != digest for value in (declared_hash, trace_hash)):
                continue

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
                    "source_type": str(snippet.get("source_type") or "teacher_resource_repository"),
                    "license_type": str(snippet.get("license_type") or "course_limited_license"),
                    "source_trace_id": str(snippet.get("source_trace_id") or ""),
                    "policy_reason": str(snippet.get("policy_reason") or ""),
                    "quote_span_hash": snippet.get("quote_span_hash"),
                    "controlled_output_hash": snippet.get("controlled_output_hash"),
                    "resource_provenance_commitment": snippet.get("resource_provenance_commitment"),
                    "retrieval_trace": list(snippet.get("retrieval_trace") or []),
                    "source_trace": dict(snippet.get("source_trace") or {}),
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


def _requests_original_resource(teaching_request: Any) -> bool:
    text = str(teaching_request).lower()
    return (
        "original teacher question bank" in text
        or "original question bank" in text
        or "exactly" in text
        or "full original" in text
        or "verbatim" in text
    )


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
