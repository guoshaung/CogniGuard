"""Organization membership and asset ownership. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str


@dataclass(frozen=True)
class Membership:
    principal_id: str
    org_id: str
    role: Literal["teacher", "student", "admin", "agent"]


@dataclass(frozen=True)
class AssetOwnership:
    resource_id: str
    owner_principal_id: str
    org_id: str
    policy_version: int = 1


def same_org(membership_a: Membership, membership_b: Membership) -> bool:
    return membership_a.org_id == membership_b.org_id
