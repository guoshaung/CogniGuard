"""Reference DisclosurePolicy: AccessRegistry for authorization, check_release (CA-PD) for
coalition safety. Governance modes are the static / dynamic ablation of PREREG_X3E2E.

| mode              | knowledge layer        | coalition size checked |
|-------------------|------------------------|------------------------|
| static            | receipts               | k + f                  |
| dyn_knowledge     | confirmed              | k + f                  |
| dyn_full          | confirmed              | k + max(f - d, 0)      |
| dyn_conservative  | confirmed+suspected    | k + max(f - d, 0)      |
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniguard.governance.reconstruction import check_release
from cogniguard.provenance.schema import DisclosureDecision, DisclosureRequest

MODES = {
    "static": ("receipts", False),
    "dyn_knowledge": ("confirmed", False),
    "dyn_full": ("confirmed", True),
    "dyn_conservative": ("confirmed+suspected", True),
}


@dataclass
class CapdPolicy:
    access_registry: object
    target_registry: object
    k: int
    f: int
    governance_mode: str = "static"

    def __post_init__(self) -> None:
        if self.governance_mode not in MODES:
            raise ValueError(self.governance_mode)
        if self.k < 1 or self.f < 0:
            raise ValueError("k >= 1 and f >= 0")

    def decide(self, request: DisclosureRequest, state) -> DisclosureDecision:
        layer, use_credits = MODES[self.governance_mode]
        d = state.trusted_event_credits() if use_credits else 0
        k_eff = self.k + max(self.f - d, 0)

        def out(allowed, reason):
            return DisclosureDecision(request.request_id, allowed, reason, self.governance_mode,
                                      k_eff, d, layer)

        for resource in request.resources:
            if not self.access_registry.is_authorized(request.principal_id, resource, request.purpose,
                                                      request.acting_org_id, request.now):
                return out(False, "unauthorized")
        verdict = check_release(self.target_registry, request.principal_id, set(request.release_units),
                                state.knowledge(layer), k_eff)
        return out(verdict.safe, "allow" if verdict.safe else "reconstruction")
