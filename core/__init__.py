"""CogniGuard 的共享保护核心与研究执行工具。"""
"""CogniGuard framework-neutral core."""

from .governance import (
    AuditLedger,
    CapabilityGrant,
    CapabilityPolicy,
    ContextBoundary,
    DomainEvidence,
    EvidenceEnvelope,
    LifecycleDecision,
    LifecycleGuard,
    Principal,
    Purpose,
    TrustState,
)

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
