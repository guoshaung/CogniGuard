"""Grant checks against a fixed ownership and membership registry."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock

from cogniguard.governance.principals import AssetOwnership, Membership


@dataclass(frozen=True)
class AccessGrant:
    grantee_principal_id: str
    resource_id: str
    purpose: str
    policy_version: int
    expires_at: float | None = None


class AccessRegistry:
    """Snapshots of ownership, membership, and grants. No mutation methods."""

    def __init__(
        self,
        ownerships: list[AssetOwnership],
        memberships: list[Membership],
        grants: list[AccessGrant],
    ) -> None:
        seen: set[str] = set()
        for ownership in ownerships:
            if ownership.resource_id in seen:
                raise ValueError(ownership.resource_id)
            seen.add(ownership.resource_id)
        self._ownerships = tuple(ownerships)
        self._memberships = tuple(memberships)
        self._grants = tuple(grants)

    def owner_of(self, resource_id: str) -> AssetOwnership | None:
        for ownership in self._ownerships:
            if ownership.resource_id == resource_id:
                return ownership
        return None

    def org_of(self, principal_id: str) -> str | None:
        # 主体属于多个组织时它只返回其中一个，不能用于授权。
        for membership in self._memberships:
            if membership.principal_id == principal_id:
                return membership.org_id
        return None

    def orgs_of(self, principal_id: str) -> frozenset[str]:
        return frozenset(
            membership.org_id
            for membership in self._memberships
            if membership.principal_id == principal_id
        )

    def is_authorized(
        self,
        principal_id: str,
        resource_id: str,
        purpose: str,
        acting_org_id: str,
        now: float,
    ) -> bool:
        ownership = self.owner_of(resource_id)
        if ownership is None:
            return False
        if acting_org_id not in self.orgs_of(principal_id):
            return False
        if acting_org_id != ownership.org_id:
            return False
        if principal_id == ownership.owner_principal_id:
            return True
        for grant in self._grants:
            if grant.grantee_principal_id != principal_id:
                continue
            if grant.resource_id != resource_id or grant.purpose != purpose:
                continue
            if grant.policy_version != ownership.policy_version:
                continue
            if grant.expires_at is not None and now >= grant.expires_at:
                continue
            return True
        return False

    def with_policy_version(self, resource_id: str, new_version: int) -> AccessRegistry:
        ownerships = []
        for ownership in self._ownerships:
            if ownership.resource_id == resource_id:
                ownerships.append(replace(ownership, policy_version=new_version))
            else:
                ownerships.append(ownership)
        return AccessRegistry(ownerships, list(self._memberships), list(self._grants))


class RegistryHolder:
    """Thread-safe handle for the registry a teacher can replace while requests run."""

    def __init__(self, registry: AccessRegistry) -> None:
        self._lock = Lock()
        self._registry = registry

    def current(self) -> AccessRegistry:
        with self._lock:
            return self._registry

    def replace(self, new_registry: AccessRegistry) -> None:
        with self._lock:
            self._registry = new_registry
