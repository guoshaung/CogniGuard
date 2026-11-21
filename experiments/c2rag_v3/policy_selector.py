from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CopyrightSelection:
    action: str
    reason: str
    score: float
    evaluated: list[dict[str, Any]]


UTILITY = {
    "controlled_quote": 0.90,
    "abstractive_summary": 0.92,
    "generated_variant": 0.76,
    "concept_only": 0.62,
    "minimal_hint": 0.48,
    "refuse": 0.05,
}


def select_copyright_candidate(candidates: list[dict[str, Any]], evidence: dict[str, Any]) -> CopyrightSelection:
    """C²-RAG-owned copyright selection; no cross-domain policy is applied here."""
    risk = float(evidence.get("copyright_risk_score", 0.0))
    remaining = float(evidence.get("remaining_budget", 0.0))
    provenance_valid = bool(evidence.get("provenance_valid", True))
    evaluated: list[dict[str, Any]] = []
    for candidate in candidates:
        action = str(candidate["action"])
        cost = float(candidate["estimated_copyright_cost"])
        residual = float(candidate["residual_copyright_risk"])
        feasible = cost <= remaining + 1e-9
        if candidate.get("provenance_required") and not provenance_valid:
            feasible = False
        score = UTILITY.get(action, 0.0) - 1.35 * residual * (1.0 + 2.0 * risk) - 0.08 * cost
        if not feasible:
            score = float("-inf")
        evaluated.append({**candidate, "feasible": feasible, "copyright_score": score})
    selected = max(evaluated, key=lambda row: row["copyright_score"])
    if selected["copyright_score"] == float("-inf"):
        selected = next(row for row in evaluated if row["action"] == "refuse")
    return CopyrightSelection(str(selected["action"]), "highest-scoring feasible copyright candidate", float(selected["copyright_score"]), evaluated)

