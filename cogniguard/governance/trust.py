from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TrustState:
    score: float = 1.0
    violations: int = 0

    def update(self, *, audit_valid: bool, provenance_valid: bool, rollback: bool) -> float:
        penalty = (
            (0.30 if not audit_valid else 0.0)
            + (0.20 if not provenance_valid else 0.0)
            + (0.15 if rollback else 0.0)
        )
        if penalty:
            self.violations += 1
        else:
            self.score = min(1.0, self.score + 0.02)
        self.score = max(0.0, self.score - penalty)
        return self.score
