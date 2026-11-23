"""capd_rel. The check stays in this directory and calls check_release."""

from __future__ import annotations

from itertools import combinations

from cogniguard.governance.reconstruction import check_release
from cogniguard.runtime.release_gate import Candidate, ReleaseGate, ReleaseRequest

from experiments.capd_eval_20261123.memstore import MemoryDisclosureStore


class RelReleaseGate(ReleaseGate):
    """ReleaseGate whose coalition check only sees registered groups.

    A release is unsafe when any combination of the recipient's group plus at
    most m - 1 other groups can finish a witness. m at least as large as the
    number of groups therefore sees every registered student, which is the
    capd_any check.
    """

    def __init__(self, store, target_registry, coalition_k: int, m: int, groups: dict[str, str]) -> None:
        if m < 1:
            raise ValueError("m must be at least 1")
        super().__init__(
            store,
            target_registry=target_registry,
            coalition_k=coalition_k,
        )
        self.m = m
        self.registered = dict(groups)
        members: dict[str, set[str]] = {}
        for student, group in self.registered.items():
            members.setdefault(group, set()).add(student)
        self.members = {
            group: frozenset(people) for group, people in members.items()
        }
        self.group_ids = tuple(sorted(self.members))

    def _coalition_allows(self, req: ReleaseRequest, knowledge: dict) -> bool:
        if self.target_registry is None or self.coalition_k is None:
            return True
        recipient = req.recipient_principal_id
        if recipient not in self.registered:
            raise ValueError(recipient)
        for name in knowledge:
            if name not in self.registered:
                raise ValueError(name)
        home = self.registered[recipient]
        others = tuple(group for group in self.group_ids if group != home)
        extra_limit = min(self.m - 1, len(others))
        release = frozenset((unit.resource_id, unit.unit_id) for unit in req.units)
        for size in range(extra_limit + 1):
            for extra in combinations(others, size):
                allowed = set(self.members[home])
                for group in extra:
                    allowed.update(self.members[group])
                restricted = {
                    name: units
                    for name, units in knowledge.items()
                    if name in allowed
                }
                verdict = check_release(
                    self.target_registry,
                    recipient,
                    release,
                    restricted,
                    self.coalition_k,
                )
                if not verdict.safe:
                    return False
        return True


class CapdRel:
    """capd_rel(k, m). Distance pricing stays at lambda 0."""

    def __init__(
        self,
        target_registry,
        coalition_k: int,
        m: int,
        groups: dict[str, str],
        *,
        price_lambda: float = 0.0,
        price_decay: float = 1.0,
    ) -> None:
        self.store = MemoryDisclosureStore()
        self.gate = RelReleaseGate(
            self.store,
            target_registry,
            coalition_k,
            m,
            groups,
        )
        self.price_lambda = price_lambda
        self.price_decay = price_decay
        self._now = 0.0

    def select(self, recipient_id: str, candidates: tuple[Candidate, ...]) -> Candidate:
        self._now += 1.0
        chosen, decision = self.gate.select_and_reserve(
            ReleaseRequest(
                recipient_principal_id=recipient_id,
                acting_org_id="lab",
                agent_principal_id="capd-e3a",
                session_id=recipient_id,
                purpose="learning",
                units=(),
                now=self._now,
            ),
            candidates,
            price_lambda=self.price_lambda,
            decay=self.price_decay,
        )
        self.gate.commit(decision, self._now)
        if chosen is None or chosen.name == "refuse":
            return next(candidate for candidate in candidates if candidate.name == "refuse")
        return chosen
