"""Inspect untrusted candidates before C2-RAG commits release, budgets or hashes.

This module owns instruction isolation only. Domain return modes, exposure costs
and source commitments remain the responsibility of the C2-RAG implementation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter

_TEXT_FIELDS = ("content", "knowledge", "difficulty", "cognitive_level", "resource_type")


class RetrievalBoundaryError(ValueError):
    """The candidate inspection contract could not be verified."""


@dataclass(frozen=True)
class RetrievalInspection:
    """Detached candidates and read-only metadata; no adapter content previews."""

    resources: tuple[Any, ...]
    evidence: Mapping[str, Any]


def inspect_candidate_resources(
    resources: Iterable[Any], *, guard: Any | None = None, context: dict | None = None
) -> RetrievalInspection:
    """Inspect candidate text without mutating input, authorizing release or charging budgets.

    Accepted resources are dict-like candidates or TeacherResource-shaped objects.
    The return container is immutable; each candidate is a detached copy for the
    domain owner to render. Adapter metadata may never replace domain policy.
    """
    originals = tuple(resources)
    copies = [deepcopy(dict(item) if isinstance(item, Mapping) else item) for item in originals]
    chunks = []
    positions = []
    for index, candidate in enumerate(copies):
        for name in _TEXT_FIELDS:
            value = (
                candidate.get(name)
                if isinstance(candidate, dict)
                else getattr(candidate, name, None)
            )
            if isinstance(value, str) and value:
                positions.append((index, name))
                chunks.append({"chunk_id": f"candidate-{index}-{name}", "content": value})
    if not copies:
        return RetrievalInspection(
            (),
            MappingProxyType(
                {
                    "decision": "allow",
                    "candidate_count": 0,
                    "accepted_count": 0,
                    "sanitized_count": 0,
                    "matched_policy": "none",
                }
            ),
        )
    from cogniguard.runtime.protection_context import active_protection

    frame = active_protection()
    if frame is not None and frame.nemo_colang is not None:
        allowed = all(frame.nemo_colang.check("retrieval", chunk["content"]) for chunk in chunks)
        frame.evidence.append({"stage": "nemo_retrieval", "decision": "allow" if allowed else "block"})
        if not allowed:
            return RetrievalInspection((), MappingProxyType({
                "decision": "block", "candidate_count": len(originals), "accepted_count": 0,
                "sanitized_count": 0, "matched_policy": "nemo_retrieval",
            }))
    adapter = guard if guard is not None else NeMoGuardrailsAdapter("", enabled=True)
    inspection_context = {
        **(context or {}),
        "source_trust": "untrusted_external_content",
        "boundary": "candidate_before_c2rag_release",
    }
    result = adapter.check_retrieved_chunks(deepcopy(chunks), inspection_context)
    if not isinstance(result, dict) or result.get("decision") not in {"allow", "sanitize", "block"}:
        raise RetrievalBoundaryError("Invalid retrieval inspection decision")
    decision = result["decision"]
    changed = set()
    if decision == "block":
        copies = []
    elif decision == "sanitize":
        sanitized = result.get("sanitized_chunks")
        if not isinstance(sanitized, list) or len(sanitized) != len(chunks):
            raise RetrievalBoundaryError("Sanitized candidates must preserve candidate positions")
        for (index, name), original, item in zip(positions, chunks, sanitized):
            if not isinstance(item, dict) or item.get("chunk_id") != original["chunk_id"]:
                raise RetrievalBoundaryError("Sanitized candidate identity mismatch")
            text = item.get("content")
            if not isinstance(text, str):
                raise RetrievalBoundaryError("Sanitized candidate text must be a string")
            if text != original["content"]:
                changed.add(index)
            if isinstance(copies[index], dict):
                copies[index][name] = text
            else:
                setattr(copies[index], name, text)
    evidence = MappingProxyType(
        {
            "decision": decision,
            "candidate_count": len(originals),
            "accepted_count": len(copies),
            "sanitized_count": len(changed),
            "matched_policy": str(result.get("matched_policy", "none")),
        }
    )
    return RetrievalInspection(tuple(copies), evidence)


def retrieval_context(
    originals: Iterable[Any], approved: Iterable[Any], *, evidence: Mapping | None = None
) -> dict[str, Any]:
    """Build invocation-local output-validation context, never graph state."""

    def view(item):
        def value(name, default=""):
            return (
                item.get(name, default)
                if isinstance(item, Mapping)
                else getattr(item, name, default)
            )

        return {
            "resource_id": str(value("resource_id")),
            "chunk_id": str(value("chunk_id")),
            "content": str(value("content")),
            "return_mode": str(value("return_mode")),
        }

    protected = [view(item) for item in originals]
    released = [view(item) for item in approved]
    return {
        "protected_resources": protected,
        "approved_chunks": released,
        "approved_source_ids": list(dict.fromkeys(item["resource_id"] for item in released)),
        "retrieval_evidence": dict(evidence or {}),
    }
