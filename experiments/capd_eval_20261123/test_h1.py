"""H1 is an implementation check: capd blocks a coalition it is large enough to see."""

from __future__ import annotations

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.capd_eval_20261123.arms import Capd, NoDefense
from experiments.capd_eval_20261123.metrics import Decision, crr
from experiments.capd_eval_20261123.workload import generate_requests


def _decisions(arm, requests) -> tuple[Decision, ...]:
    recorded = []
    for request in requests:
        selected = arm.select(request.recipient_id, request.candidates)
        recorded.append(
            Decision(request.recipient_id, request.role, request.group_id, selected, 0.0)
        )
    return tuple(recorded)


def test_crr_is_zero_when_k_covers_the_group() -> None:
    witness = frozenset({("course", "a"), ("course", "b")})
    targets = (ProtectedTarget("only", "owner", "org", (witness,)),)
    registry = TargetRegistry(targets)
    requests = generate_requests(
        targets,
        student_count=2,
        coalition_sizes=(2,),
        seed=0,
        complete_ratio=0.0,
    )
    requested = {item.unit for item in requests if item.role == "coalition"}
    assert requested == set(witness)
    assert crr(registry, _decisions(NoDefense(), requests)) == 1.0
    for k in (2, 4):
        assert crr(registry, _decisions(Capd(registry, k, price_lambda=0.0), requests)) == 0.0
