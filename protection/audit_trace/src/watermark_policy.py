from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class WatermarkEvidence:
    watermark_id: str
    detected: bool
    z_score: float
    term_keeping_rate: float
    formula_keeping_rate: float
    number_keeping_rate: float
    trace_binding_id: str
    repaired_placeholder_count: int = 0
    provenance_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WatermarkPolicy:
    """HSW-ST-owned watermark policy and recovery state."""

    clean_delta: float = 1.5
    elevated_delta: float = 1.75
    high_delta: float = 2.0
    recovery_by_watermark: dict[str, dict[str, Any]] = field(default_factory=dict)

    def select_strength(self, output_risk: float) -> float:
        if output_risk >= 0.75:
            return self.high_delta
        if output_risk >= 0.35:
            return self.elevated_delta
        return self.clean_delta

    def register(self, evidence: WatermarkEvidence, *, answer_hash: str, sources: list[dict[str, Any]]) -> None:
        self.recovery_by_watermark[evidence.watermark_id] = {
            "answer_hash": answer_hash,
            "sources": list(sources),
            "trace_binding_id": evidence.trace_binding_id,
            "provenance_valid": evidence.provenance_valid,
        }

    def recover_source(self, watermark_id: str) -> dict[str, Any] | None:
        value = self.recovery_by_watermark.get(watermark_id)
        return dict(value) if value else None

