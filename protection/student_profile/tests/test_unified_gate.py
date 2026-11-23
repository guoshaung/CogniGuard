"""One release gate protects a teaching asset and a student attribute together."""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.runtime.release_gate import ReleaseGate, ReleaseRequest, UnitRelease
from protection.student_profile.src.fopd.secret_targets import attribute_target


class MemoryReceiptStore:
    """In-process receipt log. Reserved and delivered rows both count as held."""

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
            }
        )
        return receipt_id

    def commit(self, receipt_id: str) -> None:
        for row in self.receipts:
            if row["receipt_id"] == receipt_id:
                row["status"] = "delivered"

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset[tuple[str, str]]]:
        held: dict[str, set[tuple[str, str]]] = {}
        for row in self.receipts:
            if row["status"] not in ("reserved", "delivered"):
                continue
            pair = (row["resource_id"], row["unit_id"])
            if pair not in units:
                continue
            held.setdefault(row["recipient_principal_id"], set()).add(pair)
        return {name: frozenset(pairs) for name, pairs in held.items()}


def _request(recipient: str, resource_id: str, unit_id: str) -> ReleaseRequest:
    return ReleaseRequest(
        recipient_principal_id=recipient,
        acting_org_id="school",
        agent_principal_id="agent-1",
        session_id="session-1",
        purpose="tutoring",
        units=(UnitRelease(resource_id, unit_id, f"text-{unit_id}"),),
        now=1.0,
    )


def _registry() -> TargetRegistry:
    teaching = ProtectedTarget(
        "pack-a/solution",
        "teacher",
        "org",
        (frozenset({("pack-a", "u1"), ("pack-a", "u2")}),),
        kind="teaching_asset",
    )
    student = attribute_target(
        "stu_001",
        "attendance_risk",
        [["p2", "p4"]],
        owner_principal_id="owner",
        org_id="org",
    )
    return TargetRegistry([teaching, student])


def test_one_gate_refuses_coalitions_and_allows_a_single_unit() -> None:
    gate = ReleaseGate(MemoryReceiptStore(), target_registry=_registry(), coalition_k=2)

    held_asset = gate.evaluate_and_reserve(_request("A", "pack-a", "u1"))
    assert held_asset.allowed is True
    assert gate.commit(held_asset, 1.0) is True
    denied_asset = gate.evaluate_and_reserve(_request("B", "pack-a", "u2"))
    assert denied_asset.reason == "reconstruction"

    held_signal = gate.evaluate_and_reserve(_request("A", "profile:stu_001", "p2"))
    assert held_signal.allowed is True
    assert gate.commit(held_signal, 1.0) is True
    denied_attribute = gate.evaluate_and_reserve(_request("B", "profile:stu_001", "p4"))
    assert denied_attribute.reason == "reconstruction"

    # C holds nothing yet, and nobody holds the other member of either witness.
    fresh_asset = gate.evaluate_and_reserve(_request("C", "pack-a", "u1"))
    assert fresh_asset.allowed is True
    assert fresh_asset.reason == "ok"
    fresh_attribute = gate.evaluate_and_reserve(_request("C", "profile:stu_001", "p2"))
    assert fresh_attribute.allowed is True
    assert fresh_attribute.reason == "ok"

    gate.coalition_k = 1
    assert gate.evaluate_and_reserve(_request("B", "pack-a", "u2")).reason == "ok"
    assert gate.evaluate_and_reserve(_request("B", "profile:stu_001", "p4")).reason == "ok"


def test_attribute_target_rejects_empty_groups_and_marks_the_kind() -> None:
    with pytest.raises(ValueError):
        attribute_target(
            "stu_001",
            "attendance_risk",
            [],
            owner_principal_id="owner",
            org_id="org",
        )
    with pytest.raises(ValueError):
        attribute_target(
            "stu_001",
            "attendance_risk",
            [["p2"], []],
            owner_principal_id="owner",
            org_id="org",
        )

    target = attribute_target(
        "stu_001",
        "attendance_risk",
        [["p2", "p4"]],
        owner_principal_id="owner",
        org_id="org",
    )
    assert target.kind == "student_attribute"
    assert target.domain_size == 2
