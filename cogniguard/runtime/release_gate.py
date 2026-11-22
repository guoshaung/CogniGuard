"""Domain-independent release gate. Callers pass resource and unit ids as strings."""

from __future__ import annotations

import math
import weakref
from dataclasses import dataclass, replace
from threading import Lock
from typing import Literal

from cogniguard.governance.reconstruction import check_release, residual_distance
from cogniguard.runtime.disclosure_store import ReleaseBusy

# One lock per store object. Every gate that shares that object must take it,
# including gates created by different pipelines. The guard lock only protects
# the table itself.
_store_locks: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_store_locks_guard = Lock()


def _lock_for_store(store) -> Lock:
    with _store_locks_guard:
        lock = _store_locks.get(store)
        if lock is None:
            lock = Lock()
            _store_locks[store] = lock
        return lock


@dataclass(frozen=True)
class UnitRelease:
    resource_id: str
    unit_id: str
    content: str
    exposure_delta: float = 0.0


@dataclass(frozen=True)
class Candidate:
    """One way to answer. units may be empty when nothing protected is disclosed."""

    name: str
    units: tuple[UnitRelease, ...]
    utility: float


@dataclass(frozen=True)
class ReleaseRequest:
    recipient_principal_id: str
    acting_org_id: str
    agent_principal_id: str
    session_id: str
    purpose: str
    units: tuple[UnitRelease, ...]
    now: float


@dataclass(frozen=True)
class CommitContext:
    """Who the commit-time authorization check is for. No unit text."""

    recipient_principal_id: str
    purpose: str
    acting_org_id: str


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: Literal["ok", "unauthorized", "reconstruction", "busy", "no_safe_candidate"]
    receipt_ids: tuple[str, ...]
    evidence: dict
    # (resource_id, policy_version) captured for each reserved unit, same order.
    unit_versions: tuple[tuple[str, int], ...] = ()
    commit_context: CommitContext | None = None


def _targets_for_release(registry, release: frozenset):
    found = {}
    for unit in release:
        for target in registry.targets_for_unit(unit):
            found.setdefault(target.target_id, target)
    return tuple(found[target_id] for target_id in sorted(found))


class ReleaseGate:
    """Authorize, check reconstruction, and reserve under two locks.

    Gates for the same store object share a process lock. Inside that lock,
    a MySQL named lock covers every connection to the same database, so two
    store objects cannot both pass a coalition test against the same witness.
    """

    def __init__(
        self,
        store,
        access_registry=None,
        target_registry=None,
        coalition_k=None,
        registry_holder=None,
    ) -> None:
        self.store = store
        self.access_registry = access_registry
        self.target_registry = target_registry
        self.coalition_k = coalition_k
        self.registry_holder = registry_holder
        self._lock = _lock_for_store(store)

    def evaluate_and_reserve(self, req: ReleaseRequest) -> GateDecision:
        with self._lock:
            try:
                with self.store.release_section():
                    registry = self._registry()
                    denied = self._authorization(req, registry)
                    if denied is not None:
                        return denied
                    evidence, denied = self._reconstruction(req)
                    if denied is not None:
                        return denied
                    unit_versions = tuple(
                        (unit.resource_id, _policy_version(registry, unit.resource_id))
                        for unit in req.units
                    )
                    receipt_ids = tuple(
                        self._reserve_unit(req, unit, version)
                        for unit, (_, version) in zip(req.units, unit_versions)
                    )
                    return GateDecision(
                        True,
                        "ok",
                        receipt_ids,
                        evidence,
                        unit_versions,
                        CommitContext(
                            req.recipient_principal_id,
                            req.purpose,
                            req.acting_org_id,
                        ),
                    )
            except ReleaseBusy:
                return GateDecision(False, "busy", (), {})

    def select_and_reserve(
        self,
        req_base: ReleaseRequest,
        candidates,
        price_lambda: float = 1.0,
        decay: float = 1.0,
    ) -> tuple[Candidate | None, GateDecision]:
        """Pick the highest-scoring safe candidate and reserve only that one."""
        with self._lock:
            try:
                with self.store.release_section():
                    return self._select_and_reserve(
                        req_base, tuple(candidates), price_lambda, decay
                    )
            except ReleaseBusy:
                return None, GateDecision(False, "busy", (), {})

    def commit(self, decision: GateDecision, now: float) -> bool:
        with self._lock:
            with self.store.release_section():
                registry = self._registry()
                if registry is not None and not _still_authorized(registry, decision, now):
                    for receipt_id in decision.receipt_ids:
                        self.store.cancel(receipt_id)
                    return False
                for receipt_id in decision.receipt_ids:
                    self.store.commit(receipt_id)
                return True

    def cancel(self, decision: GateDecision) -> None:
        for receipt_id in decision.receipt_ids:
            self.store.cancel(receipt_id)

    def _select_and_reserve(
        self,
        req_base: ReleaseRequest,
        candidates: tuple[Candidate, ...],
        price_lambda: float,
        decay: float,
    ) -> tuple[Candidate | None, GateDecision]:
        registry = self._registry()
        authorized: list[tuple[Candidate, ReleaseRequest]] = []
        for candidate in candidates:
            req = replace(req_base, units=candidate.units)
            if self._authorization(req, registry) is not None:
                continue
            authorized.append((candidate, req))
        knowledge = self._knowledge_for(req for _, req in authorized)
        accepted: list[tuple[float, int, str, Candidate, ReleaseRequest]] = []
        for candidate, req in authorized:
            if not self._coalition_allows(req, knowledge):
                continue
            score = candidate.utility - price_lambda * self._release_price(req, knowledge, decay)
            accepted.append((score, len(candidate.units), candidate.name, candidate, req))
        evidence = {
            "candidate_count": len(candidates),
            "accepted_count": len(accepted),
            "selected": "",
        }
        if not accepted:
            return None, GateDecision(False, "no_safe_candidate", (), evidence)
        accepted.sort(key=lambda item: (-item[0], item[1], item[2]))
        _score, _count, _name, candidate, req = accepted[0]
        evidence["selected"] = candidate.name
        unit_versions = tuple(
            (unit.resource_id, _policy_version(registry, unit.resource_id)) for unit in req.units
        )
        receipt_ids = tuple(
            self._reserve_unit(req, unit, version)
            for unit, (_, version) in zip(req.units, unit_versions)
        )
        return candidate, GateDecision(
            True,
            "ok",
            receipt_ids,
            evidence,
            unit_versions,
            CommitContext(req.recipient_principal_id, req.purpose, req.acting_org_id),
        )

    def _knowledge_for(self, requests) -> dict:
        if self.target_registry is None or self.coalition_k is None:
            return {}
        units: set[tuple[str, str]] = set()
        for req in requests:
            release = frozenset((unit.resource_id, unit.unit_id) for unit in req.units)
            for target in _targets_for_release(self.target_registry, release):
                for witness in target.witness_sets:
                    units.update(witness)
        return self.store.holders_of(units)

    def _coalition_allows(self, req: ReleaseRequest, knowledge: dict) -> bool:
        if self.target_registry is None or self.coalition_k is None:
            return True
        release = frozenset((unit.resource_id, unit.unit_id) for unit in req.units)
        verdict = check_release(
            self.target_registry,
            req.recipient_principal_id,
            release,
            knowledge,
            self.coalition_k,
        )
        return verdict.safe

    def _release_price(self, req: ReleaseRequest, knowledge: dict, decay: float) -> float:
        if self.target_registry is None or self.coalition_k is None:
            return 0.0
        release = frozenset((unit.resource_id, unit.unit_id) for unit in req.units)
        distances = residual_distance(
            self.target_registry,
            req.recipient_principal_id,
            release,
            knowledge,
            self.coalition_k,
        )
        total = 0.0
        for target_id, distance in distances.items():
            value = float(self.target_registry.get(target_id).value)
            total += value * math.exp(-decay * distance)
        return total

    def _registry(self):
        if self.registry_holder is not None:
            return self.registry_holder.current()
        return self.access_registry

    def _authorization(self, req: ReleaseRequest, registry) -> GateDecision | None:
        if registry is None:
            return None
        for unit in req.units:
            if not registry.is_authorized(
                req.recipient_principal_id,
                unit.resource_id,
                req.purpose,
                req.acting_org_id,
                req.now,
            ):
                return GateDecision(False, "unauthorized", (), {})
        return None

    def _reconstruction(self, req: ReleaseRequest) -> tuple[dict, GateDecision | None]:
        if self.target_registry is None or self.coalition_k is None:
            return {}, None
        release = frozenset((unit.resource_id, unit.unit_id) for unit in req.units)
        targets = _targets_for_release(self.target_registry, release)
        units: set[tuple[str, str]] = set()
        for target in targets:
            for witness in target.witness_sets:
                units.update(witness)
        knowledge = self.store.holders_of(units)
        verdict = check_release(
            self.target_registry,
            req.recipient_principal_id,
            release,
            knowledge,
            self.coalition_k,
        )
        # Counts only. Holder ids and unit text stay out of the evidence.
        evidence = {
            "target_count": len(targets),
            "violation_count": len(verdict.violations),
        }
        if not verdict.safe:
            return evidence, GateDecision(False, "reconstruction", (), evidence)
        return evidence, None

    def _reserve_unit(self, req: ReleaseRequest, unit: UnitRelease, policy_version: int) -> str:
        return self.store.reserve(
            resource_id=unit.resource_id,
            unit_id=unit.unit_id,
            recipient_principal_id=req.recipient_principal_id,
            acting_org_id=req.acting_org_id,
            agent_principal_id=req.agent_principal_id,
            session_id=req.session_id,
            policy_version=policy_version,
            content=unit.content,
            created_at=req.now,
            exposure_delta=unit.exposure_delta,
        )


def _policy_version(registry, resource_id: str) -> int:
    if registry is None:
        return 0
    ownership = registry.owner_of(resource_id)
    if ownership is None:
        return 0
    return int(ownership.policy_version)


def _still_authorized(registry, decision: GateDecision, now: float) -> bool:
    context = decision.commit_context
    if context is None or len(decision.unit_versions) != len(decision.receipt_ids):
        return not decision.receipt_ids
    for resource_id, policy_version in decision.unit_versions:
        ownership = registry.owner_of(resource_id)
        if ownership is None or int(ownership.policy_version) != int(policy_version):
            return False
        if not registry.is_authorized(
            context.recipient_principal_id,
            resource_id,
            context.purpose,
            context.acting_org_id,
            now,
        ):
            return False
    return True
