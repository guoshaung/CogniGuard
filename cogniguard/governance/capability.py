from __future__ import annotations

from dataclasses import dataclass

from .evidence import EvidenceEnvelope


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    principal_kind: str
    destination: str
    purposes: frozenset[str]


class CapabilityPolicy:
    def __init__(self, grants: list[CapabilityGrant] | None = None) -> None:
        self._grants = list(grants or [])

    def register(self, grant: CapabilityGrant) -> None:
        self._grants.append(grant)

    def allows(self, envelope: EvidenceEnvelope) -> bool:
        return any(
            grant.principal_kind == envelope.principal.kind
            and grant.destination == envelope.destination
            and envelope.purpose.name in grant.purposes
            for grant in self._grants
        )
