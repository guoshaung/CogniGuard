"""Grant checks against a fixed ownership and membership registry."""

from __future__ import annotations

from dataclasses import dataclass, replace

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
        self._ownerships = tuple(ownerships)
        self._memberships = tuple(memberships)
        self._grants = tuple(grants)

    def owner_of(self, resource_id: str) -> AssetOwnership | None:
        for ownership in self._ownerships:
            if ownership.resource_id == resource_id:
                return ownership
        return None

    def org_of(self, principal_id: str) -> str | None:
        for membership in self._memberships:
            if membership.principal_id == principal_id:
                return membership.org_id
        return None

    def is_authorized(self, principal_id: str, resource_id: str, purpose: str, now: float) -> bool:
        ownership = self.owner_of(resource_id)
        if ownership is None:
            return False
        org_id = self.org_of(principal_id)
        if org_id is None or org_id != ownership.org_id:
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
