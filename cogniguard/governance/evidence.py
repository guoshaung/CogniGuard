from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Principal:
    principal_id: str
    kind: Literal["user", "agent", "service", "tool"]
    roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Purpose:
    name: str
    data_categories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextBoundary:
    source: str
    trust_level: Literal["trusted_policy", "authenticated", "untrusted_data"]
    instruction_permission: bool = False


@dataclass(slots=True)
class DomainEvidence:
    domain: Literal["privacy", "knowledge", "provenance", "prompt_injection"]
    risk_score: float
    actual_cost: float = 0.0
    constraints: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.risk_score = min(1.0, max(0.0, float(self.risk_score)))
        self.actual_cost = max(0.0, float(self.actual_cost))


@dataclass(slots=True)
class EvidenceEnvelope:
    request_id: str
    session_id: str
    round_id: str
    principal: Principal
    destination: str
    purpose: Purpose
    boundary: ContextBoundary
    payload: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, DomainEvidence] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
