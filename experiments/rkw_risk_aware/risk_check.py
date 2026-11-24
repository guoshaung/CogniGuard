"""Verify risk counterfactuals against the existing pe-1.0 decision kernel."""
import argparse
from itertools import combinations
from pathlib import Path
import sys

from pilot import dump


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.contract.resolve()))
    from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
    from cogniguard.governance.principals import AssetOwnership, Membership
    from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
    from cogniguard.provenance.decision import CapdPolicy
    from cogniguard.provenance.schema import DisclosureRequest, EvidenceType, VerificationStatus, VerifiedEvidence
    from cogniguard.provenance.state import SecurityState

    source, owner, org = "r0-source", "teacher", "school"
    units = {name: (source, name) for name in "abcde"}
    requester, holder = "requester", "downstream"
    access = AccessRegistry([AssetOwnership(source, owner, org)],
                            [Membership(requester, org, "student")],
                            [AccessGrant(requester, source, "study", 1)])
    target = TargetRegistry([ProtectedTarget(source, owner, org, (frozenset(units[x] for x in "abc"),))])
    request = DisclosureRequest("fixed-dev-request", requester, "study", org, (units["c"],), 0.0)

    def allowed(k, held, extra):
        state = SecurityState({holder: frozenset(units[x] for x in held)}, enforced_budget_f=0)
        evidence = VerifiedEvidence("pe-1.0", "counterfactual", EvidenceType.RETRIEVAL,
                                    VerificationStatus.VERIFIED, "r0-fixture", holder,
                                    frozenset(units[x] for x in extra))
        state.apply(evidence)
        decision = CapdPolicy(access, target, k, 0, "dyn_knowledge").decide(request, state)
        assert decision.trusted_event_credits == 0
        return decision.allowed

    scenarios = []
    for k, held in ((2, ""), (2, "a"), (1, "a")):
        base = allowed(k, held, "")
        gains = {"".join(group): int(base and not allowed(k, held, group))
                 for count in (1, 2) for group in combinations("abd", count)}
        scenarios.append(dict(k=k, held=held, base_allowed=base, gains=gains))
    assert scenarios[0]["gains"]["a"] == scenarios[0]["gains"]["b"] == 0
    assert scenarios[0]["gains"]["ab"] == 1
    assert scenarios[1]["gains"]["b"] == 1 and scenarios[1]["gains"]["d"] == 0
    assert scenarios[2]["gains"]["b"] == 0
    optimum = max(scenarios[0]["gains"].items(), key=lambda pair: pair[1])
    assert optimum == ("ab", 1)
    dump(args.out / "risk_checks.json", {"contract": "pe-1.0", "cases": scenarios,
                                         "exact_joint_budget_2": optimum, "fixture_only": True})
    print("R0 CA-PD checks passed, including strict complementarity and zero credit.")


if __name__ == "__main__":
    main()

