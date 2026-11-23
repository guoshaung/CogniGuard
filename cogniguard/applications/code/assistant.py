"""Answer code questions by asking the release gate to pick one candidate."""

from __future__ import annotations

import time
from dataclasses import dataclass

from cogniguard.applications.code.assets import CodeAssets
from cogniguard.runtime.release_gate import Candidate, ReleaseGate, ReleaseRequest, UnitRelease

_REFUSAL = "当前不能提供该函数的实现。"
_FULL_UTILITY = 1.0
_SUMMARY_UTILITY = 0.4


@dataclass(frozen=True)
class CodeReply:
    name: str
    mode: str
    text: str


class CodeAssistant:
    """Two requests: show a function, or explain its public signature.

    Delivery is the returned reply. This path does not use the education gateway.
    """

    def __init__(
        self,
        gate: ReleaseGate,
        assets: CodeAssets,
        *,
        recipient_principal_id: str,
        acting_org_id: str,
        agent_principal_id: str,
        session_id: str,
        purpose: str,
        price_lambda: float = 1.0,
        price_decay: float = 1.0,
    ) -> None:
        self.gate = gate
        self.assets = assets
        self.recipient_principal_id = recipient_principal_id
        self.acting_org_id = acting_org_id
        self.agent_principal_id = agent_principal_id
        self.session_id = session_id
        self.purpose = purpose
        self.price_lambda = price_lambda
        self.price_decay = price_decay

    def show_function(self, name: str) -> CodeReply:
        unit = self.assets.unit(name)
        if unit.kind != "function":
            raise KeyError(name)
        summary = self.assets.summary(name)
        if self._allows(unit.resource_id):
            candidates = (
                Candidate(
                    "full",
                    (UnitRelease(unit.resource_id, unit.unit_id, unit.source, 0.0),),
                    _FULL_UTILITY,
                ),
                Candidate("summary", (), _SUMMARY_UTILITY),
                Candidate("refuse", (), 0.0),
            )
        else:
            candidates = (Candidate("refuse", (), 0.0),)
        return self._choose(
            name,
            candidates,
            {"full": unit.source, "summary": summary.text},
        )

    def explain_api(self, name: str) -> CodeReply:
        """Public signature only. The candidate discloses no unit."""
        unit = self.assets.unit(name)
        summary = self.assets.summary(name)
        if self._allows(unit.resource_id):
            candidates = (Candidate("explain", (), _SUMMARY_UTILITY),)
        else:
            candidates = (Candidate("refuse", (), 0.0),)
        return self._choose(name, candidates, {"explain": summary.text})

    def _allows(self, resource_id: str) -> bool:
        holder = self.gate.registry_holder
        registry = holder.current() if holder is not None else self.gate.access_registry
        if registry is None:
            return True
        return registry.is_authorized(
            self.recipient_principal_id,
            resource_id,
            self.purpose,
            self.acting_org_id,
            time.time(),
        )

    def _choose(self, name: str, candidates, texts: dict[str, str]) -> CodeReply:
        now = time.time()
        chosen, decision = self.gate.select_and_reserve(
            ReleaseRequest(
                recipient_principal_id=self.recipient_principal_id,
                acting_org_id=self.acting_org_id,
                agent_principal_id=self.agent_principal_id,
                session_id=self.session_id,
                purpose=self.purpose,
                units=(),
                now=now,
            ),
            candidates,
            price_lambda=self.price_lambda,
            decay=self.price_decay,
        )
        # The reply is the delivery, so the reservation is committed before return.
        committed = self.gate.commit(decision, time.time())
        mode = "" if chosen is None else chosen.name
        if not committed or mode not in texts:
            return CodeReply(name, "refuse", _REFUSAL)
        return CodeReply(name, mode, texts[mode])
