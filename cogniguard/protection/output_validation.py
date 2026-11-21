"""Content checks at the final delivery boundary, using trusted domain context.

This is deterministic matching, not a semantic privacy/grounding proof. Domain
owners supply forbidden private values, original protected resources and the
actual approved excerpts. None of these permissions come from generated text.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

SAFE_OUTPUT_REPLACEMENT = (
    "回答未通过隐私、版权或来源校验，已停止展示。请换一种不涉及受保护信息的提问方式。"
)


def _normalized(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKC", value).casefold()
        if unicodedata.category(character) != "Cf"
    )


def _compact(value: str) -> str:
    return "".join(character for character in _normalized(value) if character.isalnum())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", _normalized(value))


def _private_strings(values: Any) -> Iterable[str]:
    if isinstance(values, str):
        yield values
    elif isinstance(values, Mapping):
        for value in values.values():
            yield from _private_strings(value)
    elif isinstance(values, Iterable):
        for value in values:
            yield from _private_strings(value)


def _private_hit(text: str, value: str) -> bool:
    needle = _normalized(value).strip()
    # Do not treat short numeric scores as identifying private facts. Long
    # digit strings (phone/account/student identifiers) remain protected.
    numeric_score = re.fullmatch(r"[\d\s.,+%/-]+", needle) and len(re.sub(r"\D", "", needle)) < 6
    if len(_compact(needle)) < 2 or numeric_score:
        return False
    if needle.isascii() and len(_compact(needle)) < 8:
        return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", _normalized(text)) is not None
    return _compact(needle) in _compact(text)


@dataclass(frozen=True)
class OutputValidationPolicy:
    """Require substantial distinctive overlap; short public formulas are exempt.

    A contiguous match of 64 characters / 12 tokens needs 80% coverage of the
    shorter text. A 128-character / 24-token contiguous fragment is independently
    substantial even in a much longer answer. These are explicit heuristics;
    they do not detect all paraphrases or prove that a fact is public.
    """

    min_copy_chars: int = 64
    min_copy_tokens: int = 12
    overlap_threshold: float = 0.8
    substantial_fragment_chars: int = 128
    substantial_fragment_tokens: int = 24

    def __post_init__(self):
        if not 0 < self.overlap_threshold <= 1:
            raise ValueError("overlap_threshold must be in (0, 1]")
        for value in (
            self.min_copy_chars,
            self.min_copy_tokens,
            self.substantial_fragment_chars,
            self.substantial_fragment_tokens,
        ):
            if value <= 0:
                raise ValueError("Output overlap lengths must be positive")


@dataclass(frozen=True)
class OutputValidationResult:
    allowed: bool
    decision: str
    text: str
    reasons: tuple[str, ...]
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        # Never echo the rejected candidate, matched secrets or original chunks.
        return {
            "allowed": self.allowed,
            "decision": self.decision,
            "reasons": list(self.reasons),
            "evidence": dict(self.evidence),
            "delivered_content_hash": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
        }


def _source_ids(chunks: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(chunk[key]) for chunk in chunks for key in ("resource_id", "chunk_id") if chunk.get(key)
    }


def _claimed_ids(text: str) -> set[str]:
    patterns = (
        r"(?:resource_id|chunk_id|source_id)\s*[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9_.:/-]+)",
        r"[\[【](?:source|resource|citation|cite|来源|资源)\s*[:：]\s*([^\]】]+)",
        r"(?:^|[\n\s])(?:source|resource|来源|资源)\s*[:：]\s*([A-Za-z0-9_.:/-]+)",
    )
    return {
        token
        for pattern in patterns
        for match in re.findall(pattern, text, re.IGNORECASE)
        for token in re.split(r"[,，;；\s]+", match.strip())
        if token
    }


def _significant_overlap(answer: str, original: str, policy: OutputValidationPolicy) -> bool:
    for left, right, minimum, substantial in (
        (
            _compact(answer),
            _compact(original),
            policy.min_copy_chars,
            policy.substantial_fragment_chars,
        ),
        (
            _tokens(answer),
            _tokens(original),
            policy.min_copy_tokens,
            policy.substantial_fragment_tokens,
        ),
    ):
        if min(len(left), len(right)) < minimum:
            continue
        match = SequenceMatcher(None, left, right, autojunk=False).find_longest_match()
        if match.size >= substantial or (
            match.size >= minimum
            and match.size / min(len(left), len(right)) >= policy.overlap_threshold
        ):
            return True
    return False


def validate_output(
    text: str,
    *,
    private_values: Iterable[Any] = (),
    protected_resources: Iterable[Mapping[str, Any]] = (),
    approved_chunks: Iterable[Mapping[str, Any]] = (),
    approved_source_ids: Iterable[str] | None = None,
    claimed_source_ids: Iterable[str] = (),
    guardrail_adapter: Any = None,
    policy: OutputValidationPolicy | None = None,
) -> OutputValidationResult:
    """Validate a candidate; rejection returns a safe replacement, never raw text.

    `approved_chunks` must be the exact excerpts released by C²-RAG, rather than
    original retrieved documents. `private_values` is the MM-FOPD owner's set of
    unapproved identifying strings. Checks do not consume domain budgets.
    """
    if not isinstance(text, str):
        raise TypeError("Final output must be a string")
    policy = policy or OutputValidationPolicy()
    originals, approved = list(protected_resources), list(approved_chunks)
    reasons = []
    private_hits = sum(_private_hit(text, value) for value in set(_private_strings(private_values)))
    if private_hits:
        reasons.append("private_profile_value_reproduced")

    # Remove only trusted, exactly approved content before looking for originals.
    # Normalization also prevents spacing/case evasion for long approved quotes.
    remaining = _normalized(text)
    approved_texts = sorted(
        (str(chunk.get("content") or chunk.get("text") or "") for chunk in approved),
        key=len,
        reverse=True,
    )
    for excerpt in approved_texts:
        if excerpt:
            remaining = remaining.replace(_normalized(excerpt), " [approved excerpt] ")
    copied_count = sum(
        _significant_overlap(remaining, str(resource.get("content") or ""), policy)
        for resource in originals
        if resource.get("content")
    )
    if copied_count:
        reasons.append("unapproved_protected_resource_reproduced")

    allowed_ids = (
        _source_ids(approved) if approved_source_ids is None else set(map(str, approved_source_ids))
    )
    claims = set(map(str, claimed_source_ids)) | _claimed_ids(text)
    unapproved_claims = claims - allowed_ids
    if unapproved_claims:
        reasons.append("unapproved_source_claim")

    if guardrail_adapter is not None:
        try:
            check = guardrail_adapter.check_output(text, {"surface": "final_delivery"})
            if check.get("decision") not in {"allow", "disabled"}:
                reasons.append("generic_output_policy_rejected")
        except Exception:
            reasons.append("generic_output_check_unavailable")

    allowed = not reasons
    return OutputValidationResult(
        allowed=allowed,
        decision="allow" if allowed else "refuse",
        text=text if allowed else SAFE_OUTPUT_REPLACEMENT,
        reasons=tuple(reasons),
        evidence={
            "candidate_content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "private_value_match_count": private_hits,
            "protected_resource_match_count": copied_count,
            "unapproved_source_claim_count": len(unapproved_claims),
            "min_copy_chars": policy.min_copy_chars,
            "min_copy_tokens": policy.min_copy_tokens,
            "overlap_threshold": policy.overlap_threshold,
        },
    )
