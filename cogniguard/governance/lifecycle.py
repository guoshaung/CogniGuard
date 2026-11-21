from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .audit import AuditLedger
from .capability import CapabilityPolicy
from .evidence import EvidenceEnvelope
from .trust import TrustState


@dataclass(slots=True)
class LifecycleDecision:
    action: Literal["allow", "sanitize", "degrade", "quarantine", "refuse", "block"]
    reasons: list[str] = field(default_factory=list)
    allowed_payload: dict[str, Any] = field(default_factory=dict)
    rollback_required: bool = False


class LifecycleGuard:
    """Coordinates domain evidence without owning domain budgets or algorithms."""

    def __init__(self, capabilities: CapabilityPolicy, audit: AuditLedger | None = None) -> None:
        self.capabilities = capabilities
        self.audit = audit or AuditLedger()
        self.trust_by_session: dict[str, TrustState] = {}

    def evaluate(
        self, envelope: EvidenceEnvelope, *, audit_valid: bool = True
    ) -> LifecycleDecision:
        reasons: list[str] = []
        if not self.capabilities.allows(envelope):
            decision = LifecycleDecision("block", ["capability_denied"], {}, True)
            self._commit(envelope, decision, audit_valid)
            return decision

        if (
            envelope.boundary.trust_level == "untrusted_data"
            and envelope.boundary.instruction_permission
        ):
            reasons.append("untrusted_context_cannot_issue_instructions")

        evidences = list(envelope.evidence.values())
        exhausted = any(bool(item.constraints.get("budget_exhausted")) for item in evidences)
        invalid_source = any(item.provenance.get("valid") is False for item in evidences)
        max_risk = max((item.risk_score for item in evidences), default=0.0)

        if not audit_valid or invalid_source:
            action = "refuse"
            reasons.append("audit_or_provenance_invalid")
        elif exhausted or max_risk >= 0.85:
            action = "quarantine"
            reasons.append("domain_constraint_requires_quarantine")
        elif reasons or max_risk >= 0.55:
            action = "degrade"
            reasons.append("cross_domain_risk_conflict")
        elif max_risk >= 0.30:
            action = "sanitize"
            reasons.append("moderate_combined_risk")
        else:
            action = "allow"

        rollback = action in {"quarantine", "refuse", "block"}
        decision = LifecycleDecision(
            action, reasons, dict(envelope.payload) if not rollback else {}, rollback
        )
        self._commit(envelope, decision, audit_valid)
        return decision

    def _commit(
        self, envelope: EvidenceEnvelope, decision: LifecycleDecision, audit_valid: bool
    ) -> None:
        trust = self.trust_by_session.setdefault(envelope.session_id, TrustState())
        provenance_valid = all(
            item.provenance.get("valid", True) for item in envelope.evidence.values()
        )
        trust.update(
            audit_valid=audit_valid,
            provenance_valid=provenance_valid,
            rollback=decision.rollback_required,
        )
        self.audit.append(
            {
                "request_id": envelope.request_id,
                "session_id": envelope.session_id,
                "round_id": envelope.round_id,
                "action": decision.action,
                "reasons": decision.reasons,
                "trust": trust.score,
            }
        )
