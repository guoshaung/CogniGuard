"""Shadow decisions for uncertain provenance.

The production release path is not called. Authorization uses
`AccessRegistry.is_authorized`. Coalition checks use `check_release` on
store knowledge plus holdings attested by a trusted log or ideal evidence.
A watermark or fingerprint never adds a holding, never confirms a hop, and
never creates a grant.
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.source_evidence import SourceEvidence

UNTRUSTED_TYPES = frozenset({"fingerprint", "watermark"})
JOINT_ACCEPT = frozenset({"signed_credential", "trusted_log", "ideal"})
UnitRef = tuple[str, str]


@dataclass(frozen=True, slots=True)
class IssuanceBinding:
    """One issuance. Revocation here does not revoke any other issuance."""

    issuance_id: str
    resource_id: str
    grantee_principal_id: str
    units: tuple[UnitRef, ...] = ()
    purposes: tuple[str, ...] = ()
    revoked: bool = False


@dataclass(frozen=True, slots=True)
class ShadowRequest:
    principal_id: str
    resource_id: str
    purpose: str
    acting_org_id: str
    release_units: tuple[UnitRef, ...] = ()
    now: float = 0.0


@dataclass(frozen=True, slots=True)
class ShadowDecision:
    allowed: bool
    reason: str
    source_status: str
    trusted_issuance_ids: tuple[str, ...]
    authorizing_issuance_ids: tuple[str, ...]
    coalition_safe: bool | None
    charged_budget: bool
    confirmed_propagation: bool
    changes_production_path: bool
    evidence_ids: tuple[str, ...]
    dropped_issuance_ids: tuple[str, ...] = ()


def _resources(request: ShadowRequest) -> tuple[str, ...]:
    found = [request.resource_id]
    for resource_id, _unit_id in request.release_units:
        if resource_id not in found:
            found.append(resource_id)
    return tuple(found)


def _registry_ok(registry, request: ShadowRequest, resource_id: str) -> bool:
    return bool(
        registry.is_authorized(
            request.principal_id,
            resource_id,
            request.purpose,
            request.acting_org_id,
            request.now,
        )
    )


def untrusted_candidate_ids(evidence) -> tuple[str, ...]:
    found: list[str] = []
    for row in evidence:
        if row.evidence_type not in UNTRUSTED_TYPES:
            continue
        for issuance_id in row.candidate_issuance_ids:
            if issuance_id not in found:
                found.append(issuance_id)
    return tuple(found)


def untrusted_mismatch(evidence, bindings) -> bool:
    """True when an untrusted row asserts holdings that miss a bound issuance."""
    for row in evidence:
        if row.evidence_type not in UNTRUSTED_TYPES or not row.holdings_asserted:
            continue
        for issuance_id in row.candidate_issuance_ids:
            binding = bindings.get(issuance_id)
            if binding is None:
                continue
            matched = frozenset(row.matched_knowledge_units)
            if not matched & frozenset(binding.units):
                return True
    return False


def _claims_subject(
    row: SourceEvidence,
    bindings,
    request: ShadowRequest,
    needed: set[str],
) -> bool:
    """True when this row names one of the requester's issuances."""
    for issuance_id in row.candidate_issuance_ids:
        binding = bindings.get(issuance_id)
        if binding is None or binding.resource_id not in needed:
            continue
        if binding.grantee_principal_id == request.principal_id:
            return True
    return False


def _row_mismatch(binding: IssuanceBinding, rows: tuple[SourceEvidence, ...]) -> bool:
    bound = frozenset(binding.units)
    for row in rows:
        if not row.holdings_asserted:
            continue
        if not frozenset(row.matched_knowledge_units) & bound:
            return True
    return False


def _stale(row: SourceEvidence, registry, resource_id: str) -> bool:
    if row.policy_version <= 0:
        return False
    ownership = registry.owner_of(resource_id)
    if ownership is None:
        return True
    return int(ownership.policy_version) != int(row.policy_version)


def shadow_decide(
    evidence,
    request: ShadowRequest,
    registry,
    bindings,
    *,
    target_registry=None,
    knowledge: dict | None = None,
    k: int = 2,
    accept_types=JOINT_ACCEPT,
    fallback_registry: bool = True,
    apply_untrusted_veto: bool = False,
) -> ShadowDecision:
    """Return a shadow decision. `changes_production_path` is always False.

    `fallback_registry` uses the current grant only when no accepted row claims
    one of the requester's own issuances. An untrusted watermark can veto a
    trusted issuance only when `apply_untrusted_veto` is set. It still cannot
    grant, confirm a hop, or add a holding.
    """
    rows = tuple(evidence)
    accept = frozenset(accept_types)
    needed = set(_resources(request))
    base = {name: frozenset(units) for name, units in (knowledge or {}).items()}
    accepted = tuple(row for row in rows if row.evidence_type in accept)
    trusted = tuple(row for row in accepted if row.is_trusted_event())

    trusted_ids: list[str] = []
    for row in trusted:
        for issuance_id in row.trusted_issuance_ids():
            if issuance_id not in trusted_ids:
                trusted_ids.append(issuance_id)

    dropped: list[str] = []
    usable: list[str] = []
    vetoed: list[str] = []
    mismatched: list[str] = []
    for issuance_id in trusted_ids:
        binding = bindings.get(issuance_id)
        named = tuple(row for row in trusted if issuance_id in row.candidate_issuance_ids)
        rejected = (
            binding is None
            or binding.revoked
            or binding.grantee_principal_id != request.principal_id
            or binding.resource_id not in needed
            or (binding.purposes and request.purpose not in binding.purposes)
            or any(_stale(row, registry, binding.resource_id) for row in named)
        )
        if rejected or binding is None:
            dropped.append(issuance_id)
            continue
        if _row_mismatch(binding, named):
            mismatched.append(issuance_id)
            dropped.append(issuance_id)
            continue
        named_rows = tuple(row for row in rows if issuance_id in row.candidate_issuance_ids)
        if apply_untrusted_veto and untrusted_mismatch(named_rows, {issuance_id: binding}):
            vetoed.append(issuance_id)
            dropped.append(issuance_id)
            continue
        if not _registry_ok(registry, request, binding.resource_id):
            dropped.append(issuance_id)
            continue
        usable.append(issuance_id)

    covered = {bindings[issuance_id].resource_id for issuance_id in usable}
    claims = any(_claims_subject(row, bindings, request, needed) for row in accepted)
    use_fallback = fallback_registry and not claims and not usable
    if usable and covered >= needed:
        auth_allowed = True
        auth_reason = "ok"
    elif use_fallback and all(_registry_ok(registry, request, item) for item in needed):
        auth_allowed = True
        auth_reason = "ok"
    elif mismatched or vetoed:
        auth_allowed = False
        auth_reason = "mismatch"
    elif any(row.verification_status == "conflict" for row in accepted):
        auth_allowed = False
        auth_reason = "conflict"
    elif trusted_ids or claims:
        auth_allowed = False
        auth_reason = "unauthorized"
    elif any(row.evidence_type in UNTRUSTED_TYPES for row in rows) and not fallback_registry:
        auth_allowed = False
        auth_reason = "untrusted_evidence"
    elif not rows and not fallback_registry:
        auth_allowed = False
        auth_reason = "unknown_source"
    elif use_fallback:
        auth_allowed = False
        auth_reason = "unauthorized"
    else:
        auth_allowed = False
        auth_reason = "unknown_source"

    revoked_sibling = any(
        (binding := bindings.get(issuance_id)) is not None and binding.revoked
        for issuance_id in trusted_ids
    )
    candidates = untrusted_candidate_ids(rows)
    if auth_allowed and use_fallback and not usable:
        status = "registry"
    elif len(usable) > 1:
        status = "multiple"
    elif len(usable) == 1 and revoked_sibling:
        status = "independent_grant"
    elif len(usable) == 1:
        status = "unique"
    elif auth_reason == "mismatch" or untrusted_mismatch(rows, bindings):
        status = "mismatch"
    elif auth_reason == "conflict":
        status = "conflict"
    elif len(candidates) > 1:
        status = "multiple"
    elif auth_reason == "unauthorized":
        status = "unauthorized"
    else:
        status = "unknown"

    merged = {name: set(units) for name, units in base.items()}
    confirmed = any(row.confirms_propagation() for row in trusted)
    for row in trusted:
        if row.evidence_type not in {"trusted_log", "ideal"} or not row.holder_principal_id:
            continue
        holder = merged.setdefault(row.holder_principal_id, set())
        holder.update(row.trusted_units())

    coalition_safe: bool | None = None
    allowed = auth_allowed
    reason = auth_reason
    if target_registry is not None:
        verdict = check_release(
            target_registry,
            request.principal_id,
            request.release_units,
            {name: frozenset(units) for name, units in merged.items()},
            k,
        )
        coalition_safe = verdict.safe
        if allowed and not verdict.safe:
            allowed = False
            reason = "reconstruction"

    return ShadowDecision(
        allowed=allowed,
        reason=reason,
        source_status=status,
        trusted_issuance_ids=tuple(trusted_ids),
        authorizing_issuance_ids=tuple(usable),
        coalition_safe=coalition_safe,
        charged_budget=False,
        confirmed_propagation=confirmed,
        changes_production_path=False,
        evidence_ids=tuple(row.evidence_id for row in rows),
        dropped_issuance_ids=tuple(dropped),
    )
