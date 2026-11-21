from __future__ import annotations

from cogniguard.governance import (
    AuditLedger,
    CapabilityGrant,
    CapabilityPolicy,
    ContextBoundary,
    DomainEvidence,
    EvidenceEnvelope,
    LifecycleGuard,
    Principal,
    Purpose,
)
from experiments.c2rag_v3.policy_selector import select_copyright_candidate
from protection.audit_trace.src.watermark_policy import WatermarkEvidence, WatermarkPolicy
from protection.common.schemas import ProfileRecord, StudentProfile
from protection.student_profile.src.fopd.privacy_budget import PrivacyBudgetLedger


def test_domain_budgets_are_owned_by_domain_modules() -> None:
    profile = StudentProfile("s1", {}, [ProfileRecord("r1", "mastery", "math", 0.5, 0.9, 0.4)])
    evidence = PrivacyBudgetLedger(1.0).measure_and_commit(profile, ["r1"], "mastery level")
    assert evidence.budget_before == 1.0
    assert evidence.budget_after <= evidence.budget_before

    selection = select_copyright_candidate(
        [
            {"action": "abstractive_summary", "estimated_copyright_cost": 0.1, "residual_copyright_risk": 0.2},
            {"action": "refuse", "estimated_copyright_cost": 0.0, "residual_copyright_risk": 0.0},
        ],
        {"copyright_risk_score": 0.1, "remaining_budget": 0.5, "provenance_valid": True},
    )
    assert selection.action == "abstractive_summary"

    wm_policy = WatermarkPolicy()
    wm_evidence = WatermarkEvidence("wm1", True, 5.0, 1.0, 1.0, 1.0, "trace1")
    wm_policy.register(wm_evidence, answer_hash="abc", sources=[{"resource_id": "res1"}])
    assert wm_policy.recover_source("wm1")["trace_binding_id"] == "trace1"


def test_core_coordinates_evidence_without_domain_budget_logic() -> None:
    capabilities = CapabilityPolicy([
        CapabilityGrant("agent", "model", frozenset({"assist"}))
    ])
    audit = AuditLedger()
    guard = LifecycleGuard(capabilities, audit)
    envelope = EvidenceEnvelope(
        request_id="q1",
        session_id="s1",
        round_id="r1",
        principal=Principal("agent-1", "agent"),
        destination="model",
        purpose=Purpose("assist"),
        boundary=ContextBoundary("retriever", "untrusted_data", False),
        payload={"question": "help"},
        evidence={
            "privacy": DomainEvidence("privacy", 0.2, actual_cost=0.1),
            "knowledge": DomainEvidence("knowledge", 0.6, actual_cost=0.2),
            "provenance": DomainEvidence("provenance", 0.1, provenance={"valid": True}),
        },
    )
    decision = guard.evaluate(envelope)
    assert decision.action == "degrade"
    assert audit.verify()

