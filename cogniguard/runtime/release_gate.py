"""Domain-independent release gate. Callers pass resource and unit ids as strings."""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from cogniguard.governance.reconstruction import check_release
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
class ReleaseRequest:
    recipient_principal_id: str
    acting_org_id: str
    agent_principal_id: str
    session_id: str
    purpose: str
    units: tuple[UnitRelease, ...]
    now: float


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: Literal["ok", "unauthorized", "reconstruction", "busy"]
    receipt_ids: tuple[str, ...]
    evidence: dict


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
    ) -> None:
        self.store = store
        self.access_registry = access_registry
        self.target_registry = target_registry
        self.coalition_k = coalition_k
        self._lock = _lock_for_store(store)

    def evaluate_and_reserve(self, req: ReleaseRequest) -> GateDecision:
        with self._lock:
            try:
                with self.store.release_section():
                    denied = self._authorization(req)
                    if denied is not None:
                        return denied
                    evidence, denied = self._reconstruction(req)
                    if denied is not None:
                        return denied
                    receipt_ids = tuple(self._reserve_unit(req, unit) for unit in req.units)
                    return GateDecision(True, "ok", receipt_ids, evidence)
            except ReleaseBusy:
                return GateDecision(False, "busy", (), {})

    def commit(self, decision: GateDecision) -> None:
        for receipt_id in decision.receipt_ids:
            self.store.commit(receipt_id)

    def cancel(self, decision: GateDecision) -> None:
        for receipt_id in decision.receipt_ids:
            self.store.cancel(receipt_id)

    def _authorization(self, req: ReleaseRequest) -> GateDecision | None:
        if self.access_registry is None:
            return None
        for unit in req.units:
            if not self.access_registry.is_authorized(
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

    def _reserve_unit(self, req: ReleaseRequest, unit: UnitRelease) -> str:
        return self.store.reserve(
            resource_id=unit.resource_id,
            unit_id=unit.unit_id,
            recipient_principal_id=req.recipient_principal_id,
            acting_org_id=req.acting_org_id,
            agent_principal_id=req.agent_principal_id,
            session_id=req.session_id,
            policy_version=self._policy_version(unit.resource_id),
            content=unit.content,
            created_at=req.now,
            exposure_delta=unit.exposure_delta,
        )

    def _policy_version(self, resource_id: str) -> int:
        if self.access_registry is None:
            return 0
        ownership = self.access_registry.owner_of(resource_id)
        if ownership is None:
            return 0
        return int(ownership.policy_version)
