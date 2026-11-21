"""Optional semantic safety stage for CGC.

The deterministic CGC rules remain the primary policy. This adapter is invoked
only for boundary samples and can load a frozen Hugging Face sequence
classifier or a calibrated local sklearn classifier. It never owns budgets,
permissions, provenance, audit, or rollback.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticSafetyDecision:
    label: str
    risk_score: float
    confidence: float
    model_name: str
    applied: bool


class SemanticSafetyAdapter:
    """Framework-neutral optional semantic classifier.

    `predictor` may be a callable accepting text and returning either a float
    risk score or `{label, risk_score}`. Keeping the predictor injected makes
    model choice reproducible and prevents CGC from silently downloading or
    training a model in production.
    """

    def __init__(self, predictor: Any = None, *, threshold: float = 0.5, model_name: str = "disabled"):
        self.predictor = predictor
        self.threshold = float(threshold)
        self.model_name = model_name

    @property
    def enabled(self) -> bool:
        return self.predictor is not None

    def predict(self, text: str) -> SemanticSafetyDecision:
        if self.predictor is None:
            return SemanticSafetyDecision("unknown", 0.0, 0.0, self.model_name, False)
        raw = self.predictor(str(text or ""))
        if isinstance(raw, dict):
            score = float(raw.get("risk_score", raw.get("score", 0.0)))
            label = str(raw.get("label", "harmful" if score >= self.threshold else "benign"))
        else:
            score = float(raw)
            label = "harmful" if score >= self.threshold else "benign"
        confidence = abs(score - 0.5) * 2.0
        return SemanticSafetyDecision(label, score, confidence, self.model_name, True)

    def decide_boundary(self, text: str) -> dict[str, Any]:
        decision = self.predict(text)
        return {
            "decision": "block" if decision.label == "harmful" else "allow",
            "matched_policy": "semantic_safety_boundary",
            "semantic_safety": decision.__dict__,
        }
