"""Shadow decisions. These tests do not reserve a receipt or open MySQL."""

from __future__ import annotations

from pathlib import Path

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.source_evidence import SourceEvidence
from cogniguard.governance.source_state import (
    IssuanceBinding,
    ShadowRequest,
    shadow_decide,
)
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

NOW = 10.0
UNIT_A = ("doc", "a")
UNIT_B = ("doc", "b")


def _registry(expires_at: float | None = None, version: int = 1) -> AccessRegistry:
    return AccessRegistry(
        [
            AssetOwnership("doc", "owner", "alpha", version),
            AssetOwnership("readme", "owner", "alpha", 1),
        ],
        [Membership("u2", "alpha", "student"), Membership("u5", "alpha", "student")],
        [
            AccessGrant("u2", "doc", "education", 1, expires_at=expires_at),
            AccessGrant("u5", "doc", "education", 1),
            AccessGrant("u2", "readme", "review", 1),
        ],
    )


def _bindings() -> dict[str, IssuanceBinding]:
    return {
        "iss-live": IssuanceBinding("iss-live", "doc", "u2", (UNIT_A, UNIT_B), ("education",)),
        "iss-old": IssuanceBinding(
            "iss-old", "doc", "u2", (UNIT_A,), ("education",), revoked=True
        ),
        "iss-other": IssuanceBinding("iss-other", "doc", "u5", (UNIT_A,), ("education",)),
        "iss-partner": IssuanceBinding("iss-partner", "doc", "partner", (UNIT_B,), ("education",)),
    }


def _request(
    principal: str = "u2",
    purpose: str = "education",
    units: tuple = (UNIT_A,),
) -> ShadowRequest:
    return ShadowRequest(principal, "doc", purpose, "alpha", tuple(units), NOW)


def _evidence(evidence_type: str, issuance_id: str, **overrides) -> SourceEvidence:
    payload = {
        "evidence_id": overrides.pop("evidence_id", f"ev-{evidence_type}"),
        "evidence_type": evidence_type,
        "artifact_id": "art",
        "candidate_issuance_ids": [issuance_id] if issuance_id else [],
        "matched_knowledge_units": [list(UNIT_A)],
        "confidence": overrides.pop("confidence", 0.4),
        "verification_status": overrides.pop("verification_status", "verified"),
        "trusted_event_id": overrides.pop("trusted_event_id", None),
        "policy_version": overrides.pop("policy_version", 1),
    }
    if "units" in overrides:
        payload["matched_knowledge_units"] = [list(unit) for unit in overrides.pop("units")]
    payload.update(overrides)
    return SourceEvidence.from_dict(payload)


def _targets() -> TargetRegistry:
    target = ProtectedTarget("secret", "owner", "alpha", (frozenset({UNIT_A, UNIT_B}),))
    return TargetRegistry([target])


def test_unique_credential_allows_without_touching_production() -> None:
    decision = shadow_decide(
        [_evidence("signed_credential", "iss-live", trusted_event_id=None)],
        _request(),
        _registry(),
        _bindings(),
        target_registry=_targets(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=False,
    )
    assert decision.allowed is True
    assert decision.source_status == "unique"
    assert decision.authorizing_issuance_ids == ("iss-live",)
    assert decision.confirmed_propagation is False
    assert decision.charged_budget is False
    assert decision.changes_production_path is False
    assert decision.coalition_safe is True


def test_multiple_live_issuances_allow() -> None:
    second = IssuanceBinding("iss-also", "doc", "u2", (UNIT_A,), ("education",))
    bindings = _bindings() | {"iss-also": second}
    rows = [
        _evidence("signed_credential", "iss-live", evidence_id="a"),
        _evidence("signed_credential", "iss-also", evidence_id="b"),
    ]
    decision = shadow_decide(
        rows,
        _request(),
        _registry(),
        bindings,
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=False,
    )
    assert decision.allowed is True
    assert decision.source_status == "multiple"


def test_unknown_and_watermark_only_do_not_grant() -> None:
    registry = _registry()
    silent = shadow_decide(
        [],
        _request(),
        registry,
        _bindings(),
        accept_types=frozenset(),
        fallback_registry=False,
    )
    watermark = shadow_decide(
        [_evidence("watermark", "iss-live", confidence=1.0, trusted_event_id="hop")],
        _request(),
        registry,
        _bindings(),
        accept_types=frozenset(),
        fallback_registry=False,
    )
    assert silent.allowed is False
    assert silent.reason == "unknown_source"
    assert silent.source_status == "unknown"
    assert watermark.allowed is False
    assert watermark.reason == "untrusted_evidence"
    assert watermark.confirmed_propagation is False
    assert watermark.charged_budget is False


def test_several_untrusted_candidates_stay_untrusted() -> None:
    row = _evidence("watermark", "iss-live", confidence=0.2)
    extra = SourceEvidence.from_dict(
        {**row.to_dict(), "candidate_issuance_ids": ["iss-live", "iss-other"]}
    )
    decision = shadow_decide(
        [extra],
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset(),
        fallback_registry=False,
    )
    assert decision.allowed is False
    assert decision.source_status == "multiple"


def test_revoked_sibling_does_not_deny_the_live_issuance() -> None:
    rows = [
        _evidence("signed_credential", "iss-old", evidence_id="old"),
        _evidence("signed_credential", "iss-live", evidence_id="live"),
    ]
    decision = shadow_decide(
        rows,
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=False,
    )
    assert decision.allowed is True
    assert decision.source_status == "independent_grant"
    assert decision.authorizing_issuance_ids == ("iss-live",)
    assert "iss-old" in decision.dropped_issuance_ids


def test_a_revoked_record_does_not_deny_another_resource() -> None:
    request = ShadowRequest("u2", "readme", "review", "alpha", (), NOW)
    decision = shadow_decide(
        [_evidence("signed_credential", "iss-old")],
        request,
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
    )
    assert decision.allowed is True
    assert decision.source_status == "registry"


def test_conflict_denies_and_a_second_valid_row_still_allows() -> None:
    conflict = _evidence(
        "signed_credential",
        "iss-live",
        evidence_id="bad",
        verification_status="conflict",
    )
    denied = shadow_decide(
        [conflict],
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
    )
    live = _evidence("signed_credential", "iss-live", evidence_id="live")
    allowed = shadow_decide(
        [conflict, live],
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=False,
    )
    assert denied.allowed is False
    assert denied.reason == "conflict"
    assert denied.source_status == "conflict"
    assert allowed.allowed is True


def test_mismatch_and_watermark_veto_do_not_charge_a_budget() -> None:
    credential = _evidence(
        "signed_credential",
        "iss-live",
        holdings_asserted=True,
        units=(),
    )
    denied = shadow_decide(
        [credential],
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
    )
    watermark = _evidence(
        "watermark",
        "iss-live",
        evidence_id="mark",
        confidence=0.99,
        holdings_asserted=True,
        units=(),
    )
    vetoed = shadow_decide(
        [_evidence("signed_credential", "iss-live", evidence_id="cred"), watermark],
        _request(),
        _registry(),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
        apply_untrusted_veto=True,
    )
    assert denied.reason == "mismatch"
    assert vetoed.reason == "mismatch"
    assert vetoed.charged_budget is False
    assert vetoed.confirmed_propagation is False


def test_expiry_and_policy_version_deny() -> None:
    expired = shadow_decide(
        [_evidence("signed_credential", "iss-live")],
        _request(),
        _registry(expires_at=NOW),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
    )
    bumped = shadow_decide(
        [_evidence("signed_credential", "iss-live")],
        _request(),
        _registry(version=2),
        _bindings(),
        accept_types=frozenset({"signed_credential"}),
        fallback_registry=True,
    )
    assert expired.allowed is False
    assert bumped.allowed is False
    assert bumped.reason == "unauthorized"


def test_watermark_does_not_add_holdings_or_mutate_knowledge() -> None:
    knowledge = {"partner": frozenset()}
    watermark = _evidence(
        "watermark",
        "iss-partner",
        confidence=1.0,
        trusted_event_id="hop",
        holdings_asserted=True,
        units=(UNIT_B,),
        holder_principal_id="partner",
    )
    ignored = shadow_decide(
        [watermark],
        _request(units=(UNIT_A,)),
        _registry(),
        _bindings(),
        target_registry=_targets(),
        knowledge=knowledge,
        accept_types=frozenset(),
        fallback_registry=True,
    )
    log = _evidence(
        "trusted_log",
        "iss-partner",
        evidence_id="log",
        trusted_event_id="hop-9",
        units=(UNIT_B,),
        holder_principal_id="partner",
    )
    caught = shadow_decide(
        [log],
        _request(units=(UNIT_A,)),
        _registry(),
        _bindings(),
        target_registry=_targets(),
        knowledge=knowledge,
        accept_types=frozenset({"trusted_log"}),
        fallback_registry=True,
    )
    assert knowledge == {"partner": frozenset()}
    assert ignored.allowed is True
    assert ignored.coalition_safe is True
    assert ignored.confirmed_propagation is False
    assert caught.allowed is False
    assert caught.reason == "reconstruction"
    assert caught.confirmed_propagation is True
    assert caught.charged_budget is False


def test_shadow_module_does_not_call_the_release_gate() -> None:
    text = Path(__file__).resolve().parents[1].joinpath("governance/source_state.py").read_text()
    assert "evaluate_and_reserve" not in text
    assert "DisclosureStore" not in text
    assert "release_gate" not in text
