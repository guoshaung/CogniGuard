"""Evaluate two candidate blocks against the actual CA-PD policy."""
import itertools
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.provenance.decision import CapdPolicy
from cogniguard.provenance.schema import DisclosureRequest
from cogniguard.provenance.state import SecurityState

def evaluate(source):
    units = [(source, str(i)) for i in range(4)]
    access = AccessRegistry([AssetOwnership(source, "teacher", "school")],
                            [Membership("requester", "school", "student")],
                            [AccessGrant("requester", source, "study", 1)])
    targets = TargetRegistry([ProtectedTarget(source, "teacher", "school",
                                              (frozenset(units[i] for i in (0, 1, 3)),))])
    request = DisclosureRequest("pilot", "requester", "study", "school", (units[3],), 0.)
    def decision(indices):
        state = SecurityState({"downstream": frozenset(units[i] for i in indices)}, enforced_budget_f=0)
        return CapdPolicy(access, targets, 2, 0, "dyn_knowledge").decide(request, state).allowed
    # Counterfactual holdings are injected as trusted fixture receipts to test the policy.
    before = decision(())
    scores = {"".join(map(str, indices)): int(before and not decision(indices))
              for size in (1, 2) for indices in itertools.combinations(range(3), size)}
    return scores

output = {source: evaluate(source) for source in ("rectangle", "speed")}
for scores in output.values():
    assert scores == {"0":0,"1":0,"2":0,"01":1,"02":0,"12":0}
Path(sys.argv[2]).write_text(json.dumps(output,indent=2)+"\n",encoding="utf8",newline="\n")
