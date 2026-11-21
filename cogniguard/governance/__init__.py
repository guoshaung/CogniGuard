"""Framework-neutral CogniGuard governance primitives.

Domain policy belongs to MM-FOPD, C²-RAG, and HSW-ST.  This package only
coordinates evidence, capabilities, trust, audit, context boundaries, and
lifecycle rollback.
"""

from .audit import AuditLedger
from .capability import CapabilityGrant, CapabilityPolicy
from .evidence import ContextBoundary, DomainEvidence, EvidenceEnvelope, Principal, Purpose
from .lifecycle import LifecycleDecision, LifecycleGuard
from .trust import TrustState

__all__ = [
    "AuditLedger",
    "CapabilityGrant",
    "CapabilityPolicy",
    "ContextBoundary",
    "DomainEvidence",
    "EvidenceEnvelope",
    "LifecycleDecision",
    "LifecycleGuard",
    "Principal",
    "Purpose",
    "TrustState",
]
