"""Education and software probes through the real ReleaseGate. In-memory receipts only."""

from __future__ import annotations

from contextlib import contextmanager

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry, RegistryHolder
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.release_gate import ReleaseGate, ReleaseRequest, UnitRelease
from protection.student_profile.src.fopd.secret_targets import attribute_target

NOW = 10.0


class MemoryReceiptStore:
    """Process-local receipt log. Enough for ReleaseGate, not a second store."""

    def __init__(self) -> None:
        self.receipts: list[dict] = []

    @contextmanager
    def release_section(self):
        yield

    def reserve(self, **kwargs) -> str:
        receipt_id = f"r{len(self.receipts) + 1}"
        self.receipts.append(
            {
                "receipt_id": receipt_id,
                "resource_id": kwargs["resource_id"],
                "unit_id": kwargs["unit_id"],
                "recipient_principal_id": kwargs["recipient_principal_id"],
                "status": "reserved",
            }
        )
        return receipt_id

    def commit(self, receipt_id: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = "delivered"

    def cancel(self, receipt_id: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = "cancelled"

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset]:
        held: dict[str, set[tuple[str, str]]] = {}
        for row in self.receipts:
            if row["status"] not in ("reserved", "delivered"):
                continue
            pair = (row["resource_id"], row["unit_id"])
            if pair not in units:
                continue
            held.setdefault(row["recipient_principal_id"], set()).add(pair)
        return {name: frozenset(pairs) for name, pairs in held.items()}


def _request(principal: str, resource_id: str, unit_id: str, purpose: str, org: str) -> ReleaseRequest:
    return ReleaseRequest(
        recipient_principal_id=principal,
        acting_org_id=org,
        agent_principal_id="agent-1",
        session_id="x3-e2e",
        purpose=purpose,
        units=(UnitRelease(resource_id, unit_id, f"text-{unit_id}"),),
        now=NOW,
    )


def education_probe() -> dict:
    registry = AccessRegistry(
        [
            AssetOwnership("pack-a", "teacher", "school", 1),
            AssetOwnership("profile:stu_001", "teacher", "school", 1),
        ],
        [
            Membership("teacher", "school", "teacher"),
            Membership("s1", "school", "student"),
            Membership("s2", "school", "student"),
            Membership("stranger", "school", "student"),
        ],
        [
            AccessGrant("s1", "pack-a", "education", 1),
            AccessGrant("s2", "pack-a", "education", 1),
            AccessGrant("s1", "profile:stu_001", "tutoring", 1),
            AccessGrant("s2", "profile:stu_001", "tutoring", 1),
        ],
    )
    targets = TargetRegistry(
        [
            ProtectedTarget(
                "pack-a/solution",
                "teacher",
                "school",
                (frozenset({("pack-a", "u1"), ("pack-a", "u2")}),),
                kind="teaching_asset",
            ),
            attribute_target(
                "stu_001",
                "attendance_risk",
                [["p2", "p4"]],
                owner_principal_id="teacher",
                org_id="school",
            ),
        ]
    )
    gate = ReleaseGate(
        MemoryReceiptStore(),
        access_registry=registry,
        target_registry=targets,
        coalition_k=2,
    )
    first = gate.evaluate_and_reserve(_request("s1", "pack-a", "u1", "education", "school"))
    committed = gate.commit(first, NOW) if first.allowed else False
    second = gate.evaluate_and_reserve(_request("s2", "pack-a", "u2", "education", "school"))
    stranger = gate.evaluate_and_reserve(_request("stranger", "pack-a", "u1", "education", "school"))
    signal = gate.evaluate_and_reserve(_request("s1", "profile:stu_001", "p2", "tutoring", "school"))
    signal_committed = gate.commit(signal, NOW) if signal.allowed else False
    attribute = gate.evaluate_and_reserve(_request("s2", "profile:stu_001", "p4", "tutoring", "school"))
    return {
        "teaching_one_unit_allowed": first.allowed,
        "teaching_one_unit_committed": committed,
        "teaching_completing_unit_reason": second.reason,
        "stranger_reason": stranger.reason,
        "attribute_one_signal_allowed": signal.allowed,
        "attribute_one_signal_committed": signal_committed,
        "attribute_completing_reason": attribute.reason,
        "attribute_kind": targets.get("stu_001/attendance_risk").kind,
    }


def software_probe() -> dict:
    registry = AccessRegistry(
        [
            AssetOwnership("svc-key", "platform", "lab", 1),
            AssetOwnership("svc-readme", "platform", "lab", 1),
        ],
        [
            Membership("platform", "lab", "admin"),
            Membership("e1", "lab", "student"),
        ],
        [
            AccessGrant("e1", "svc-key", "review", 1),
            AccessGrant("e1", "svc-readme", "review", 1),
        ],
    )
    targets = TargetRegistry(
        [
            ProtectedTarget(
                "svc-key-secret",
                "platform",
                "lab",
                (frozenset({("svc-key", "token"), ("svc-key", "runbook")}),),
            )
        ]
    )
    holder = RegistryHolder(registry)
    gate = ReleaseGate(
        MemoryReceiptStore(),
        access_registry=registry,
        target_registry=targets,
        coalition_k=2,
        registry_holder=holder,
    )
    reserved = gate.evaluate_and_reserve(_request("e1", "svc-key", "runbook", "review", "lab"))
    holder.replace(registry.with_policy_version("svc-key", 2))
    commit_after_bump = gate.commit(reserved, NOW) if reserved.allowed else False
    denied = gate.evaluate_and_reserve(_request("e1", "svc-key", "runbook", "review", "lab"))
    readme_registry = AccessRegistry(
        [
            AssetOwnership("svc-key", "platform", "lab", 2),
            AssetOwnership("svc-readme", "platform", "lab", 1),
        ],
        [
            Membership("platform", "lab", "admin"),
            Membership("e1", "lab", "student"),
        ],
        [
            AccessGrant("e1", "svc-key", "review", 1),
            AccessGrant("e1", "svc-readme", "review", 1),
        ],
    )
    readme_gate = ReleaseGate(
        MemoryReceiptStore(),
        access_registry=readme_registry,
        target_registry=TargetRegistry(
            [
                ProtectedTarget(
                    "svc-readme-note",
                    "platform",
                    "lab",
                    (frozenset({("svc-readme", "intro"), ("svc-readme", "rest")}),),
                )
            ]
        ),
        coalition_k=2,
    )
    readme = readme_gate.evaluate_and_reserve(_request("e1", "svc-readme", "intro", "review", "lab"))
    return {
        "runbook_reserved": reserved.allowed,
        "commit_after_policy_bump": commit_after_bump,
        "key_after_bump_reason": denied.reason,
        "readme_still_allowed": readme.allowed,
    }
