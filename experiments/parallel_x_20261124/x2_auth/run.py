"""X2: derived objects, revocation, and dynamic authorization.

Deterministic counterexample plus a 5-seed dev scan. No network, no model.
"""

from __future__ import annotations

# Frozen before any simulation. Do not retune these after seeing rates.
PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0

import json
import random
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry, RegistryHolder
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.release_gate import ReleaseGate, ReleaseRequest, UnitRelease

# Fixed decision-cost model, milliseconds. Wall-clock on these checks is noise.
COST_SNAPSHOT_MS = 0.01
COST_IS_AUTHORIZED_MS = 0.05
COST_EDGE_MS = 0.01
COST_VERSION_MS = 0.02
COST_LABEL_MS = 0.03
COST_DERIVED_SHORTCUT_MS = 0.02

ORG = "org-synth"
OWNER = "owner-synth"
SUBJECT_S = "subject-s"
SUBJECT_R = "subject-r"
SUBJECT_T = "subject-t"
AGENT = "agent-synth"
ASSET_A = "asset-a"
ASSET_B = "asset-b"
DERIVED_A = "derived-a"
PURPOSE_TUTORING = "tutoring"
PURPOSE_GRADING = "grading"

BASELINES = ("B0", "B1", "B2", "B3", "B4")
METHODS = BASELINES + ("ours",)


class MemoryReceiptStore:
    """In-process receipt log with the methods ReleaseGate.commit calls."""

    def __init__(self) -> None:
        self.receipts: list[dict] = []

    @contextmanager
    def release_section(self):
        yield

    def reserve(
        self,
        *,
        resource_id: str,
        unit_id: str,
        recipient_principal_id: str,
        acting_org_id: str,
        agent_principal_id: str,
        session_id: str,
        policy_version: int,
        content: str,
        created_at: float,
        exposure_delta: float = 0.0,
    ) -> str:
        receipt_id = f"r{len(self.receipts) + 1}"
        self.receipts.append(
            {
                "receipt_id": receipt_id,
                "resource_id": resource_id,
                "unit_id": unit_id,
                "recipient_principal_id": recipient_principal_id,
                "status": "reserved",
                "policy_version": policy_version,
            }
        )
        return receipt_id

    def commit(self, receipt_id: str) -> None:
        self._set(receipt_id, "delivered")

    def cancel(self, receipt_id: str) -> None:
        self._set(receipt_id, "cancelled")

    def _set(self, receipt_id: str, status: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = status
                return
        raise KeyError(receipt_id)


class World:
    def __init__(self, principals: list[tuple[str, str]], assets: list[str], grants: list[AccessGrant], owner: str) -> None:
        self.owner = owner
        self.principals = principals
        self.memberships = [Membership(principal_id, ORG, role) for principal_id, role in principals]
        self.memberships.append(Membership(AGENT, ORG, "agent"))
        self.resource_ids = list(assets)
        self.grant_list = list(grants)
        owns = [AssetOwnership(asset, owner, ORG, 1) for asset in assets]
        self.registry = AccessRegistry(owns, self.memberships, self.grant_list)
        self.holder = RegistryHolder(self.registry)
        self.store = MemoryReceiptStore()
        self.gate = ReleaseGate(self.store, registry_holder=self.holder)
        self.parents: dict[str, tuple[str, ...]] = {asset: () for asset in assets}
        self.labels: dict[str, tuple[int, str]] = {asset: (1, PURPOSE_TUTORING) for asset in assets}
        self.clearance = {owner: 2}
        for principal_id, _role in principals:
            self.clearance.setdefault(principal_id, 1)
        self.snapshot = self._snapshot()
        self.memory: dict[str, set[str]] = {}
        self.cache: set[str] = set()
        self.reservations: dict[str, object] = {}
        self.tasks: dict[str, tuple[str, str, str]] = {}

    def _snapshot(self) -> dict[tuple[str, str, str], bool]:
        shot: dict[tuple[str, str, str], bool] = {}
        principals = [principal_id for principal_id, _role in self.principals]
        for principal in principals:
            for asset in list(self.resource_ids):
                if self.parents.get(asset, ()) != ():
                    continue
                shot[(principal, asset, PURPOSE_TUTORING)] = self.registry.is_authorized(
                    principal, asset, PURPOSE_TUTORING, ORG, 0.0
                )
        return shot


def install(world: World, owns: list[AssetOwnership], grants: list[AccessGrant]) -> None:
    world.resource_ids = [item.resource_id for item in owns]
    world.grant_list = list(grants)
    world.registry = AccessRegistry(owns, world.memberships, world.grant_list)
    world.holder.replace(world.registry)


def anchors_of(world: World, object_id: str) -> tuple[str, ...]:
    """Source assets a derived object still depends on. A source is its own anchor."""
    found: list[str] = []
    stack = [object_id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        parents = world.parents[current]
        if not parents:
            found.append(current)
        else:
            stack.extend(parents)
    return tuple(found)


def normative_allows(world: World, principal: str, object_id: str, purpose: str, now: float) -> bool:
    """Lawful iff every source anchor currently authorizes this principal and purpose.

    A copied grant on a derived id is not an independent right. Memory is not decided here.
    """
    return all(
        world.registry.is_authorized(principal, anchor, purpose, ORG, now)
        for anchor in anchors_of(world, object_id)
    )


def b0_allows(world: World, principal: str, object_id: str, purpose: str, now: float) -> tuple[bool, float, str]:
    allowed = all(
        world.snapshot.get((principal, anchor, purpose), False) for anchor in anchors_of(world, object_id)
    )
    return allowed, COST_SNAPSHOT_MS, "snapshot_t0"


def b1_allows(world: World, principal: str, object_id: str, purpose: str, now: float) -> tuple[bool, float, str]:
    # Derived objects are ordinary data: the live grant is not consulted for them.
    if world.parents[object_id]:
        return True, COST_DERIVED_SHORTCUT_MS, "derived_uncontrolled"
    allowed = world.registry.is_authorized(principal, object_id, purpose, ORG, now)
    return allowed, COST_IS_AUTHORIZED_MS, "live_grant"


def b2_allows(world: World, principal: str, object_id: str, purpose: str, now: float) -> tuple[bool, float, str]:
    """Dynamic ACL plus dependency propagation. Revoking an anchor marks dependents unauthorized."""
    nodes = anchors_of(world, object_id)
    allowed = all(world.registry.is_authorized(principal, node, purpose, ORG, now) for node in nodes)
    cost = (COST_IS_AUTHORIZED_MS + COST_EDGE_MS) * len(nodes)
    return allowed, cost, "dependency_propagation"


def cross_module_coordinator(
    world: World, principal: str, object_id: str, purpose: str, now: float
) -> tuple[bool, float, str]:
    """Candidate coordinator.

    Not developed further: on these cases B2 already stops every unlawful delivery
    and every unlawful execution, so this function is exactly B2.
    """
    allowed, cost, _reason = b2_allows(world, principal, object_id, purpose, now)
    return allowed, cost, "coordinator_eq_b2"


def b4_allows(world: World, principal: str, object_id: str, purpose: str, now: float) -> tuple[bool, float, str]:
    level, label_purpose = world.labels[object_id]
    clearance = world.clearance.get(principal, 0)
    allowed = clearance >= level and purpose == label_purpose
    return allowed, COST_LABEL_MS, "label_inherit"


LIVE = {
    "B0": b0_allows,
    "B1": b1_allows,
    "B2": b2_allows,
    "B4": b4_allows,
    "ours": cross_module_coordinator,
}


def _request(principal: str, object_id: str, purpose: str, now: float) -> ReleaseRequest:
    unit = "summary-1" if world_is_derived(object_id) else "unit-1"
    return ReleaseRequest(
        recipient_principal_id=principal,
        acting_org_id=ORG,
        agent_principal_id=AGENT,
        session_id="session-synth",
        purpose=purpose,
        units=(UnitRelease(object_id, unit, f"synthetic-content-{object_id}"),),
        now=now,
    )


def world_is_derived(object_id: str) -> bool:
    return object_id.startswith("derived") or object_id.startswith("d-")


def b3_fresh(world: World, principal: str, object_id: str, purpose: str, now: float) -> tuple[bool, float, str]:
    """New read or cache serve: reserve that object id, then commit-time recheck."""
    decision = world.gate.evaluate_and_reserve(_request(principal, object_id, purpose, now))
    cost = COST_IS_AUTHORIZED_MS + COST_VERSION_MS
    if not decision.allowed:
        return False, cost, f"gate:{decision.reason}"
    if not world.gate.commit(decision, now):
        return False, cost, "gate:commit_cancel"
    return True, cost, "gate:ok"


def reserve_task(world: World, task_id: str, principal: str, object_id: str, purpose: str, now: float) -> None:
    decision = world.gate.evaluate_and_reserve(_request(principal, object_id, purpose, now))
    world.reservations[task_id] = decision
    world.tasks[task_id] = (principal, object_id, purpose)


def b3_commit(world: World, task_id: str, now: float) -> tuple[bool, float, str]:
    decision = world.reservations[task_id]
    cost = COST_IS_AUTHORIZED_MS + COST_VERSION_MS
    if decision is None or not decision.allowed:
        reason = "gate:not_reserved" if decision is None else f"gate:{decision.reason}"
        return False, cost, reason
    if not world.gate.commit(decision, now):
        return False, cost, "gate:commit_cancel"
    return True, cost, "gate:ok"


def revoke(world: World, resource_id: str) -> None:
    current = world.registry.owner_of(resource_id)
    if current is None:
        raise RuntimeError(resource_id)
    world.registry = world.registry.with_policy_version(resource_id, current.policy_version + 1)
    world.holder.replace(world.registry)


def change_purpose(world: World, resource_id: str, grantee: str, new_purpose: str) -> None:
    current = world.registry.owner_of(resource_id)
    if current is None:
        raise RuntimeError(resource_id)
    new_version = current.policy_version + 1
    bumped = world.registry.with_policy_version(resource_id, new_version)
    owns = []
    for resource in world.resource_ids:
        found = bumped.owner_of(resource)
        if found is None:
            raise RuntimeError(resource)
        owns.append(found)
    grants = [
        grant
        for grant in world.grant_list
        if not (grant.resource_id == resource_id and grant.grantee_principal_id == grantee)
    ]
    grants.append(AccessGrant(grantee, resource_id, new_purpose, new_version))
    install(world, owns, grants)


def derive(world: World, new_id: str, sources: tuple[str, ...], principal: str, purpose: str) -> None:
    owns = []
    for resource in world.resource_ids:
        found = world.registry.owner_of(resource)
        if found is None:
            raise RuntimeError(resource)
        owns.append(found)
    owns.append(AssetOwnership(new_id, world.owner, ORG, 1))
    grants = list(world.grant_list)
    # Derivation copies a grant onto the new id. That copy does not track the parent's version.
    grants.append(AccessGrant(principal, new_id, purpose, 1))
    install(world, owns, grants)
    world.parents[new_id] = sources
    world.labels[new_id] = (1, purpose)


def record(
    world: World,
    events: list[dict],
    *,
    case: str,
    phase: str,
    right: str,
    kind: str,
    principal: str,
    object_id: str,
    purpose: str,
    now: float,
    scored: bool,
    tags: list[str],
    task_id: str | None = None,
) -> None:
    if not scored:
        events.append(
            {
                "case": case,
                "phase": phase,
                "right": right,
                "kind": kind,
                "principal": principal,
                "object_id": object_id,
                "purpose": purpose,
                "now": now,
                "scored": False,
                "tags": tags,
                "ground_truth_allow": None,
                "retained": True,
                "allow": {},
                "latency_ms": {},
                "reason": {},
            }
        )
        return
    ground = normative_allows(world, principal, object_id, purpose, now)
    allow: dict[str, bool] = {}
    latency: dict[str, float] = {}
    reason: dict[str, str] = {}
    for name, function in LIVE.items():
        bit, cost, why = function(world, principal, object_id, purpose, now)
        allow[name] = bit
        latency[name] = cost
        reason[name] = why
    if kind == "exec":
        if task_id is None:
            raise RuntimeError("exec event needs a task")
        bit, cost, why = b3_commit(world, task_id, now)
    else:
        bit, cost, why = b3_fresh(world, principal, object_id, purpose, now)
    allow["B3"] = bit
    latency["B3"] = cost
    reason["B3"] = why
    events.append(
        {
            "case": case,
            "phase": phase,
            "right": right,
            "kind": kind,
            "principal": principal,
            "object_id": object_id,
            "purpose": purpose,
            "now": now,
            "scored": True,
            "tags": tags,
            "task_id": task_id,
            "ground_truth_allow": ground,
            "allow": allow,
            "latency_ms": latency,
            "reason": reason,
        }
    )


def classroom() -> World:
    principals = [
        (OWNER, "teacher"),
        (SUBJECT_S, "student"),
        (SUBJECT_R, "student"),
        (SUBJECT_T, "student"),
    ]
    grants = [
        AccessGrant(SUBJECT_S, ASSET_A, PURPOSE_TUTORING, 1),
        AccessGrant(SUBJECT_T, ASSET_B, PURPOSE_TUTORING, 1),
    ]
    return World(principals, [ASSET_A, ASSET_B], grants, OWNER)


def run_deterministic() -> tuple[list[dict], dict]:
    events: list[dict] = []

    lawful = classroom()
    record(
        lawful, events,
        case="lawful_tutoring", phase="T1", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=ASSET_A, purpose=PURPOSE_TUTORING, now=1.0,
        scored=True, tags=["still_authorized"],
    )
    derive(lawful, DERIVED_A, (ASSET_A,), SUBJECT_S, PURPOSE_TUTORING)
    record(
        lawful, events,
        case="lawful_tutoring", phase="T1", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=1.0,
        scored=True, tags=["still_authorized"],
    )
    lawful.cache.add(DERIVED_A)
    record(
        lawful, events,
        case="lawful_tutoring", phase="T2", right="controlled_cache", kind="cache",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=2.0,
        scored=True, tags=["still_authorized"],
    )
    reserve_task(lawful, "lawful-tool", SUBJECT_S, DERIVED_A, PURPOSE_TUTORING, 2.0)
    record(
        lawful, events,
        case="lawful_tutoring", phase="T5", right="future_execution", kind="exec",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True, tags=["still_authorized", "queued_tool_at_t5"], task_id="lawful-tool",
    )
    record(
        lawful, events,
        case="lawful_tutoring", phase="T1", right="future_read", kind="read",
        principal=SUBJECT_T, object_id=ASSET_B, purpose=PURPOSE_TUTORING, now=1.0,
        scored=True, tags=["still_authorized"],
    )
    record(
        lawful, events,
        case="lawful_tutoring", phase="T1", right="future_read", kind="read",
        principal=OWNER, object_id=ASSET_A, purpose=PURPOSE_TUTORING, now=1.0,
        scored=True, tags=["still_authorized"],
    )

    race = classroom()
    derive(race, DERIVED_A, (ASSET_A,), SUBJECT_S, PURPOSE_TUTORING)
    reserve_task(race, "tool-a", SUBJECT_S, ASSET_A, PURPOSE_TUTORING, 1.0)
    reserve_task(race, "tool-d", SUBJECT_S, DERIVED_A, PURPOSE_TUTORING, 2.0)
    reserve_task(race, "tool-owner", OWNER, ASSET_A, PURPOSE_TUTORING, 1.0)
    race.cache.add(DERIVED_A)
    race.memory.setdefault(SUBJECT_S, set()).add(ASSET_A)
    record(
        race, events,
        case="already_obtained_knowledge", phase="T1", right="already_obtained_knowledge",
        kind="memory", principal=SUBJECT_S, object_id=ASSET_A, purpose=PURPOSE_TUTORING,
        now=1.0, scored=False, tags=["already_obtained_knowledge"],
    )
    revoke(race, ASSET_A)
    record(
        race, events,
        case="revoke_between_reserve_and_commit", phase="T5", right="future_execution",
        kind="exec", principal=SUBJECT_S, object_id=ASSET_A, purpose=PURPOSE_TUTORING,
        now=5.0, scored=True, tags=["revoke_between_reserve_and_commit"], task_id="tool-a",
    )
    record(
        race, events,
        case="queued_tool_on_derived", phase="T5", right="future_execution", kind="exec",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True,
        tags=["revoke_between_reserve_and_commit", "queued_tool_at_t5"],
        task_id="tool-d",
    )
    record(
        race, events,
        case="owner_inflight_after_epoch", phase="T5", right="future_execution", kind="exec",
        principal=OWNER, object_id=ASSET_A, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True, tags=["still_authorized", "epoch_recheck"], task_id="tool-owner",
    )
    record(
        race, events,
        case="cache_s_after_revoke", phase="T4", right="controlled_cache", kind="cache",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["controlled_cache"],
    )
    record(
        race, events,
        case="r_reads_derived_after_revoke", phase="T4", right="controlled_cache", kind="cache",
        principal=SUBJECT_R, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["r_requests_d_after_revoke"],
    )
    record(
        race, events,
        case="r_reads_derived_after_revoke", phase="T4", right="future_read", kind="read",
        principal=SUBJECT_R, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["r_requests_d_after_revoke"],
    )
    record(
        race, events,
        case="future_read_source_after_revoke", phase="T4", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=ASSET_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["future_read"],
    )
    record(
        race, events,
        case="future_read_derived_after_revoke", phase="T4", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["future_read"],
    )
    record(
        race, events,
        case="r_reads_source_after_revoke", phase="T4", right="future_read", kind="read",
        principal=SUBJECT_R, object_id=ASSET_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["future_read"],
    )
    record(
        race, events,
        case="unrelated_grant_after_revoke", phase="T5", right="future_read", kind="read",
        principal=SUBJECT_T, object_id=ASSET_B, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True, tags=["still_authorized"],
    )
    probe = memory_probe()

    purpose = classroom()
    derive(purpose, DERIVED_A, (ASSET_A,), SUBJECT_S, PURPOSE_TUTORING)
    reserve_task(purpose, "tool-purpose", SUBJECT_S, DERIVED_A, PURPOSE_TUTORING, 2.0)
    purpose.cache.add(DERIVED_A)
    change_purpose(purpose, ASSET_A, SUBJECT_S, PURPOSE_GRADING)
    record(
        purpose, events,
        case="purpose_change", phase="T5", right="future_execution", kind="exec",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True, tags=["purpose_change", "queued_tool_at_t5"], task_id="tool-purpose",
    )
    record(
        purpose, events,
        case="purpose_change", phase="T4", right="controlled_cache", kind="cache",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_TUTORING, now=4.0,
        scored=True, tags=["purpose_change"],
    )
    record(
        purpose, events,
        case="purpose_change", phase="T5", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=ASSET_A, purpose=PURPOSE_GRADING, now=5.0,
        scored=True, tags=["still_authorized", "purpose_change"],
    )
    record(
        purpose, events,
        case="purpose_change", phase="T5", right="future_read", kind="read",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_GRADING, now=5.0,
        scored=True, tags=["still_authorized", "purpose_change"],
    )
    record(
        purpose, events,
        case="purpose_change", phase="T5", right="controlled_cache", kind="cache",
        principal=SUBJECT_S, object_id=DERIVED_A, purpose=PURPOSE_GRADING, now=5.0,
        scored=True, tags=["still_authorized", "purpose_change"],
    )
    record(
        purpose, events,
        case="purpose_change", phase="T5", right="future_read", kind="read",
        principal=SUBJECT_T, object_id=ASSET_B, purpose=PURPOSE_TUTORING, now=5.0,
        scored=True, tags=["still_authorized"],
    )
    return events, probe


def memory_probe() -> dict:
    """S already holds the unit. Reconstruction staying unsafe is not an access bug."""
    targets = TargetRegistry(
        [
            ProtectedTarget(
                "synthetic-witness-a",
                OWNER,
                ORG,
                (frozenset({(ASSET_A, "unit-1")}),),
            )
        ]
    )
    knowledge = {SUBJECT_S: frozenset({(ASSET_A, "unit-1")})}
    verdict = check_release(targets, SUBJECT_S, [(ASSET_A, "unit-1")], knowledge, 1)
    return {
        "safe": verdict.safe,
        "violation_count": len(verdict.violations),
        "counted_as_safety_violation": False,
        "note": "S already learned asset-a. The access system is not required to unlearn it.",
    }


def assert_invariants(events: list[dict], probe: dict) -> None:
    required = {
        "revoke_between_reserve_and_commit",
        "purpose_change",
        "r_requests_d_after_revoke",
        "queued_tool_at_t5",
        "already_obtained_knowledge",
    }
    seen: set[str] = set()
    for event in events:
        seen.update(event["tags"])
    missing = required - seen
    if missing:
        raise SystemExit(f"missing required situations: {sorted(missing)}")
    if probe["counted_as_safety_violation"] or probe["safe"] or probe["violation_count"] < 1:
        raise SystemExit(f"memory probe should be unsafe and unscored: {probe}")
    memory = [event for event in events if event["right"] == "already_obtained_knowledge"]
    if len(memory) != 1 or any(event["scored"] for event in memory):
        raise SystemExit("already-obtained knowledge must be retained and not scored")
    scored = [event for event in events if event["scored"]]
    if not scored:
        raise SystemExit("no scored events")
    for event in scored:
        if event["allow"]["B2"] != event["ground_truth_allow"]:
            raise SystemExit(f"B2 diverged from the normative grant check: {event['case']}")
        if event["allow"]["ours"] != event["allow"]["B2"]:
            raise SystemExit(f"coordinator diverged from B2: {event['case']}")
    derived_exec = [
        event
        for event in scored
        if event["task_id"] == "tool-d"
        and event["ground_truth_allow"] is False
        and event["allow"]["B3"] is True
        and event["allow"]["B2"] is False
    ]
    source_exec = [
        event
        for event in scored
        if event["task_id"] == "tool-a"
        and event["ground_truth_allow"] is False
        and event["allow"]["B3"] is False
    ]
    r_delivery = [
        event
        for event in scored
        if "r_requests_d_after_revoke" in event["tags"] and event["allow"]["B1"] is True and event["allow"]["B2"] is False
    ]
    if not derived_exec or not source_exec or not r_delivery:
        raise SystemExit("expected B3 hole on derived commit, B3 cancel on source commit, and B1 delivery to R")
    owner_exec = next(event for event in scored if event["task_id"] == "tool-owner")
    if owner_exec["ground_truth_allow"] is not True or owner_exec["allow"]["B3"] is not False:
        raise SystemExit("owner in-flight release should stay lawful and be cancelled by the version recheck")
    if owner_exec["reason"]["B3"] != "gate:commit_cancel":
        raise SystemExit(f"owner cancel reason was {owner_exec['reason']['B3']}")


def score(events: list[dict], methods: tuple[str, ...] = METHODS) -> dict[str, dict]:
    scored = [event for event in events if event["scored"]]
    unlawful = [event for event in scored if event["ground_truth_allow"] is False]
    lawful = [event for event in scored if event["ground_truth_allow"] is True]
    rows = {}
    for name in methods:
        violations = sum(1 for event in unlawful if event["allow"][name])
        successes = sum(1 for event in lawful if event["allow"][name])
        false_rejects = len(lawful) - successes
        latency_values = [event["latency_ms"][name] for event in scored]
        mean_latency = sum(latency_values) / len(latency_values)
        rows[name] = {
            "violation_count": violations,
            "unlawful_count": len(unlawful),
            "violation_rate": violations / len(unlawful) if unlawful else 0.0,
            "task_success_count": successes,
            "lawful_count": len(lawful),
            "task_success": successes / len(lawful) if lawful else 0.0,
            "false_reject_count": false_rejects,
            "false_reject_rate": false_rejects / len(lawful) if lawful else 0.0,
            "mean_latency_ms": mean_latency,
        }
    return rows


def rights_table(events: list[dict]) -> dict[str, dict[str, dict]]:
    scored = [event for event in events if event["scored"]]
    rights = ("controlled_cache", "future_read", "future_execution")
    table: dict[str, dict[str, dict]] = {}
    for right in rights:
        subset = [event for event in scored if event["right"] == right and event["ground_truth_allow"] is False]
        table[right] = {}
        for name in METHODS:
            violations = sum(1 for event in subset if event["allow"][name])
            table[right][name] = {
                "violations": violations,
                "unlawful": len(subset),
                "rate": (violations / len(subset)) if subset else 0.0,
            }
    return table


def strength_key(name: str, row: dict) -> tuple:
    return (
        row["violation_rate"],
        -row["task_success"],
        row["false_reject_rate"],
        row["mean_latency_ms"],
        name,
    )


def security_matches(events: list[dict], left: str, right: str) -> bool:
    for event in events:
        if not event["scored"]:
            continue
        if event["ground_truth_allow"] is False and event["allow"][left] != event["allow"][right]:
            return False
        if event["allow"][left] != event["allow"][right]:
            return False
    return True


def run_dev_seed(seed: int) -> list[dict]:
    """Five rounds, one action each. Not a cartesian product."""
    rng = random.Random(seed)
    n_subjects = 2 + (seed % 5)
    n_assets = 1 + (seed % 4)
    if n_subjects > 8 or n_assets > 4:
        raise SystemExit("dev scan exceeded the subject or asset cap")
    subjects = [f"scan-s{seed}-{index}" for index in range(n_subjects)]
    assets = [f"scan-a{seed}-{index}" for index in range(n_assets)]
    owner = f"scan-owner-{seed}"
    principals = [(owner, "teacher")] + [(subject, "student") for subject in subjects]
    grants = [
        AccessGrant(subjects[index % n_subjects], assets[index], PURPOSE_TUTORING, 1)
        for index in range(n_assets)
    ]
    world = World(principals, assets, grants, owner)
    events: list[dict] = []
    asset_index = rng.randrange(n_assets)
    asset = assets[asset_index]
    grantee = subjects[asset_index % n_subjects]
    others = [subject for subject in subjects if subject != grantee]
    other = others[rng.randrange(len(others))]
    derived = f"d-{seed}-0"
    record(
        world, events,
        case=f"dev-{seed}", phase="R0", right="future_read", kind="read",
        principal=grantee, object_id=asset, purpose=PURPOSE_TUTORING, now=1.0,
        scored=True, tags=["dev_scan", "still_authorized"],
    )
    derive(world, derived, (asset,), grantee, PURPOSE_TUTORING)
    reserve_task(world, f"dev-task-{seed}", grantee, derived, PURPOSE_TUTORING, 2.0)
    if seed % 2 == 0:
        revoke(world, asset)
        mutate = "revoke"
    else:
        change_purpose(world, asset, grantee, PURPOSE_GRADING)
        mutate = "purpose"
    if seed % 2 == 0:
        record(
            world, events,
            case=f"dev-{seed}", phase="R4", right="future_execution", kind="exec",
            principal=grantee, object_id=derived, purpose=PURPOSE_TUTORING, now=5.0,
            scored=True, tags=["dev_scan", mutate, "queued_tool_at_t5"],
            task_id=f"dev-task-{seed}",
        )
    else:
        record(
            world, events,
            case=f"dev-{seed}", phase="R4", right="controlled_cache", kind="cache",
            principal=other, object_id=derived, purpose=PURPOSE_TUTORING, now=4.0,
            scored=True, tags=["dev_scan", mutate, "r_requests_d_after_revoke"],
        )
    return events


def round6(value: float) -> float:
    return round(value, 6)


def row_public(row: dict) -> dict:
    return {
        "violation_count": row["violation_count"],
        "unlawful_count": row["unlawful_count"],
        "violation_rate": round6(row["violation_rate"]),
        "task_success_count": row["task_success_count"],
        "lawful_count": row["lawful_count"],
        "task_success": round6(row["task_success"]),
        "false_reject_count": row["false_reject_count"],
        "false_reject_rate": round6(row["false_reject_rate"]),
        "mean_latency_ms": round6(row["mean_latency_ms"]),
    }


def failing_trace(events: list[dict]) -> list[dict]:
    trace = []
    for event in events:
        if not event["scored"] or event["ground_truth_allow"] is not False:
            continue
        failed = [name for name in BASELINES if event["allow"][name]]
        if not failed:
            continue
        trace.append(
            {
                "case": event["case"],
                "phase": event["phase"],
                "right": event["right"],
                "kind": event["kind"],
                "principal": event["principal"],
                "object_id": event["object_id"],
                "purpose": event["purpose"],
                "task_id": event.get("task_id"),
                "tags": event["tags"],
                "ground_truth_allow": False,
                "failed_baselines": failed,
                "allow": {name: event["allow"][name] for name in METHODS},
                "reason": {name: event["reason"][name] for name in METHODS},
            }
        )
    return trace


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


def render_result(payload: dict) -> str:
    lines = [
        "# X2 dynamic authorization and derived knowledge",
        "",
        f"Verdict: **{payload['verdict']}**",
        "",
        f"Base SHA: `{payload['base_sha']}`",
        "",
        "Formal experiment: false. Dev scan: true (5 seeds, not used for the verdict).",
        "",
        "## Verdict",
        "",
        payload["notes"],
        "",
        "## Four rights",
        "",
        "Already-obtained knowledge is not a safety violation. S learns asset-a at T1;",
        "reconstruction still reports that witness as completable after revocation, and",
        f"that probe is unscored (safe={payload['memory_probe']['safe']}, counted_as_safety_violation=false).",
        "Controlled cache, future read, and future execution are scored.",
        "",
        "| Right | Unlawful events | B0 | B1 | B2 | B3 | B4 | ours |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for right, methods in payload["rights"].items():
        unlawful = methods["B0"]["unlawful"]
        cells = " | ".join(str(methods[name]["violations"]) for name in METHODS)
        lines.append(f"| {right} | {unlawful} | {cells} |")
    lines.extend(
        [
            "",
            "## Deterministic metrics",
            "",
            "| Method | Unauthorized delivery/execution | Task success | False reject | Mean decision latency ms |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in METHODS:
        row = payload["deterministic"][name]
        lines.append(
            f"| {name} | {row['violation_count']}/{row['unlawful_count']} ({row['violation_rate']:.3f}) "
            f"| {row['task_success_count']}/{row['lawful_count']} ({row['task_success']:.3f}) "
            f"| {row['false_reject_rate']:.3f} | {row['mean_latency_ms']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"Strongest fair baseline: **{payload['strongest_baseline']}**.",
            f"Safety gain (baseline rate - ours rate): {payload['safety_gain']['delta']}.",
            f"Utility change (ours task success - baseline): {payload['utility_change']['delta']}.",
            f"Overhead ratio: {payload['compute_overhead']}.",
            "",
            "Latency is a fixed per-decision cost model in milliseconds, not wall-clock.",
            "",
            "## Failing trace",
            "",
            "B2 and ours deny every unlawful delivery and execution below.",
            "An empty failed_baselines list means every baseline denied it; those rows are omitted.",
            "",
        ]
    )
    if not payload["counterexample"]["failing_trace"]:
        lines.append("No baseline fails the deterministic counterexample.")
    for item in payload["counterexample"]["failing_trace"]:
        allow = " ".join(f"{name}={'Y' if item['allow'][name] else 'N'}" for name in METHODS)
        lines.append(
            f"- {item['phase']} {item['case']} {item['right']} {item['principal']} -> {item['object_id']} "
            f"purpose={item['purpose']} failed={','.join(item['failed_baselines'])} [{allow}]"
        )
    lines.extend(["", "## Decision table", ""])
    lines.append("| Case | Right | Who | Object | Purpose | GT | B0 | B1 | B2 | B3 | B4 | ours |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for event in payload["scored_events"]:
        mark = "allow" if event["ground_truth_allow"] else "deny"
        cells = " | ".join("Y" if event["allow"][name] else "N" for name in METHODS)
        lines.append(
            f"| {event['case']} | {event['right']} | {event['principal']} | {event['object_id']} "
            f"| {event['purpose']} | {mark} | {cells} |"
        )
    dev = payload["dev_scan_metrics"]
    lines.extend(["", "## Dev scan", "", "Seeds 0..4, at most 6 subjects plus an owner, at most 4 assets, 5 rounds. Not formal.", ""])
    lines.append("| Method | Unauthorized rate | Task success | False reject |")
    lines.append("| --- | ---: | ---: | ---: |")
    for name in METHODS:
        row = dev[name]
        lines.append(
            f"| {name} | {row['violation_count']}/{row['unlawful_count']} ({row['violation_rate']:.3f}) "
            f"| {row['task_success']:.3f} | {row['false_reject_rate']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Code reuse",
            "",
            "Called: AccessRegistry.is_authorized, AccessRegistry.with_policy_version, RegistryHolder,",
            "ReleaseGate.evaluate_and_reserve, ReleaseGate.commit, check_release, ProtectedTarget, TargetRegistry.",
            "Mirrored: ReleaseGate._still_authorized is the gate's own commit recheck, not reimplemented.",
            "",
            "## Frozen rule",
            "",
            f"PASS_MIN_ABS_SAFETY_GAIN={PASS_MIN_ABS_SAFETY_GAIN}, MAX_UTILITY_DROP={MAX_UTILITY_DROP}, "
            f"MAX_OVERHEAD_RATIO={MAX_OVERHEAD_RATIO}.",
            "STOP because the strongest fair baseline has zero deterministic safety violations",
            "and the candidate does not change that security decision.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    events, probe = run_deterministic()
    assert_invariants(events, probe)
    rows = score(events)
    dev_events: list[dict] = []
    for seed in range(5):
        dev_events.extend(run_dev_seed(seed))
    dev_rows = score(dev_events)
    for event in dev_events:
        if event["scored"] and event["allow"]["B2"] != event["ground_truth_allow"]:
            raise SystemExit(f"dev scan B2 diverged: {event['case']} {event['phase']}")
    if not security_matches(events, "ours", "B2"):
        raise SystemExit("ours and B2 security decisions differ; the STOP alias is wrong")
    strongest = min(BASELINES, key=lambda name: strength_key(name, rows[name]))
    same_as_strongest = security_matches(events, "ours", strongest)
    base = rows[strongest]
    ours = rows["ours"]
    gain = base["violation_rate"] - ours["violation_rate"]
    utility_drop = base["task_success"] - ours["task_success"]
    overhead_ratio = (
        ours["mean_latency_ms"] / base["mean_latency_ms"] if base["mean_latency_ms"] else float("inf")
    )
    if base["violation_rate"] == 0.0 or same_as_strongest:
        verdict = "STOP"
    elif (
        gain >= PASS_MIN_ABS_SAFETY_GAIN
        and utility_drop <= MAX_UTILITY_DROP
        and overhead_ratio < MAX_OVERHEAD_RATIO
    ):
        verdict = "PASS"
    else:
        verdict = "ANALYZE"
    head = git_head()
    rights = rights_table(events)
    trace = failing_trace(events)
    safety_gain = {
        "metric": "unauthorized_delivery_execution_rate",
        "baseline": round6(base["violation_rate"]),
        "ours": round6(ours["violation_rate"]),
        "delta": round6(base["violation_rate"] - ours["violation_rate"]),
    }
    utility_change = {
        "metric": "task_success_on_still_authorized",
        "baseline": round6(base["task_success"]),
        "ours": round6(ours["task_success"]),
        "delta": round6(ours["task_success"] - base["task_success"]),
    }
    overhead = round6(overhead_ratio)
    notes = (
        "STOP. B2 (dynamic ACL with dependency propagation, rechecked at cache serve, "
        "future read, and queued execution) has zero unauthorized deliveries and executions "
        "on the deterministic cases, and it still allows every still-authorized request. "
        "B3 is the real ReleaseGate reserve plus commit recheck: it cancels an in-flight "
        "release of asset-a when with_policy_version bumps asset-a, including the owner's "
        "still-lawful in-flight release (false reject, fail closed on the epoch). "
        "The same recheck does not stop a summary that was registered as derived-a with a "
        "copied tutoring grant, because commit compares derived-a's own policy version. "
        "B0 keeps the T0 snapshot. B1 re-reads the grant but treats a derived object as "
        "uncontrolled data, so subject-r receives derived-a after revocation. B4 inherits a "
        "static confidentiality label and same-org clearance, so revocation and per-principal "
        "grants are invisible. The candidate cross_module_coordinator is not developed; it "
        "is B2. Dev-scan rates are illustrative only. "
        f"Deterministic B2 violation_rate={base['violation_rate']:.3f}, "
        f"task_success={base['task_success']:.3f}, false_reject={base['false_reject_rate']:.3f}. "
        f"Dev-scan B2 violations={dev_rows['B2']['violation_count']}/{dev_rows['B2']['unlawful_count']}."
    )
    summary = {
        "experiment": "X2",
        "base_sha": head,
        "verdict": verdict,
        "counterexample": {
            "timeline": [
                "T0 subject-s is granted asset-a for tutoring",
                "T1 subject-s reads asset-a, learns it, and derives derived-a",
                "T2 derived-a is cached and a tool on derived-a is reserved",
                "T3 asset-a is revoked or its purpose becomes grading",
                "T4 subject-r requests derived-a",
                "T5 the queued tool commits",
            ],
            "strongest_does_not_fail": True,
            "failing_trace": trace,
            "memory_probe": probe,
        },
        "strongest_baseline": strongest,
        "safety_gain": safety_gain,
        "utility_change": utility_change,
        "false_reject_rate": round6(ours["false_reject_rate"]),
        "compute_overhead": overhead,
        "literature_overlap": "pending-worker-E",
        "code_reuse": [
            "cogniguard.governance.access_policy.AccessRegistry.is_authorized",
            "cogniguard.governance.access_policy.AccessRegistry.with_policy_version",
            "cogniguard.governance.access_policy.RegistryHolder",
            "cogniguard.runtime.release_gate.ReleaseGate.evaluate_and_reserve",
            "cogniguard.runtime.release_gate.ReleaseGate.commit",
            "cogniguard.governance.reconstruction.check_release",
            "cogniguard.governance.targets.ProtectedTarget",
            "cogniguard.governance.targets.TargetRegistry",
        ],
        "dev_scan": True,
        "formal": False,
        "paths": {
            "run": str(ROOT / "run.py"),
            "result": str(ROOT / "RESULT.md"),
            "summary": str(ROOT / "results" / "summary.json"),
        },
        "notes": notes,
    }
    rendered = {
        **summary,
        "deterministic": {name: row_public(rows[name]) for name in METHODS},
        "dev_scan_metrics": {name: row_public(dev_rows[name]) for name in METHODS},
        "rights": rights,
        "memory_probe": probe,
        "scored_events": [
            {
                "case": event["case"],
                "right": event["right"],
                "principal": event["principal"],
                "object_id": event["object_id"],
                "purpose": event["purpose"],
                "ground_truth_allow": event["ground_truth_allow"],
                "allow": event["allow"],
            }
            for event in events
            if event["scored"]
        ],
    }
    result_path = ROOT / "RESULT.md"
    summary_path = ROOT / "results" / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(render_result(rendered), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"verdict={verdict}")
    print(f"strongest={strongest}")
    print(
        "deterministic "
        + " ".join(
            f"{name}:v={rows[name]['violation_rate']:.3f},u={rows[name]['task_success']:.3f},"
            f"fr={rows[name]['false_reject_rate']:.3f},ms={rows[name]['mean_latency_ms']:.3f}"
            for name in METHODS
        )
    )
    print(f"safety_gain={safety_gain['delta']} utility_change={utility_change['delta']} overhead={overhead}")
    print(f"failing_trace_events={len(trace)}")
    for item in trace:
        print(
            f"FAIL {item['phase']} {item['case']} {item['principal']}->{item['object_id']} "
            f"{item['right']} failed={','.join(item['failed_baselines'])}"
        )
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
