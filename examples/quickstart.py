"""Synthetic governance decisions; no model, external service or file input."""

import json

from cogniguard import (
    CapabilityGrant,
    CapabilityPolicy,
    ContextBoundary,
    DomainEvidence,
    EvidenceEnvelope,
    LifecycleGuard,
    Principal,
    Purpose,
)


def run_example() -> dict:
    # Trusted application configuration grants this capability. A retrieved
    # document or a model response must never create grants on its own.
    policy = CapabilityPolicy(
        [
            CapabilityGrant("agent", "teaching", frozenset({"education"})),
        ]
    )
    guard = LifecycleGuard(policy)
    cases = {
        "allow": {"valid_source": True, "budget_exhausted": False},
        "refuse": {"valid_source": False, "budget_exhausted": False},
        "quarantine": {"valid_source": True, "budget_exhausted": True},
    }
    decisions = {}
    for name, case in cases.items():
        envelope = EvidenceEnvelope(
            request_id=f"request-{name}",
            session_id=f"session-{name}",
            round_id="1",
            principal=Principal("teaching-agent", "agent"),
            destination="teaching",
            purpose=Purpose("education"),
            boundary=ContextBoundary("synthetic-retrieval", "untrusted_data", False),
            payload={"question": "Explain 2 + 2."},
            evidence={
                "privacy": DomainEvidence(
                    "privacy",
                    0.1,
                    constraints={"budget_exhausted": case["budget_exhausted"]},
                ),
                "provenance": DomainEvidence(
                    "provenance",
                    0.1,
                    provenance={"valid": case["valid_source"]},
                ),
            },
        )
        # The guard coordinates supplied evidence. This example does not run a
        # detector, authenticate a user, execute rollback or invoke an agent.
        decision = guard.evaluate(envelope, audit_valid=guard.audit.verify())
        decisions[name] = {
            "action": decision.action,
            "reasons": decision.reasons,
            "allowed_payload": decision.allowed_payload,
            "rollback_required": decision.rollback_required,
        }
    return {"decisions": decisions, "audit_valid": guard.audit.verify()}


if __name__ == "__main__":
    print(json.dumps(run_example(), indent=2))
