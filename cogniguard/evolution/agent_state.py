"""Agent-facing evolution hooks. Every write goes through EvolutionGate."""

from __future__ import annotations

import json
from uuid import uuid4

from cogniguard.evolution.events import EvolutionEvent
from cogniguard.evolution.gate import EvolutionGate, GateDecision


class EvolvingAgentState:
    def __init__(self, agent_id: str, gate: EvolutionGate) -> None:
        self.agent_id = agent_id
        self.gate = gate

    def remember(self, key: str, text: str, provenance: tuple[str, ...] | list[str]) -> GateDecision:
        target = f"{self.agent_id}:memory:{key}"
        return self._apply(
            "memory_write",
            target,
            text,
            provenance,
        )

    def create_skill(self, spec: dict, provenance: tuple[str, ...] | list[str]) -> GateDecision:
        name = spec.get("name", "") if isinstance(spec, dict) else ""
        target = f"{self.agent_id}:skill:{name}"
        return self._apply("skill_create", target, json.dumps(spec), provenance)

    def edit_prompt(
        self,
        fragment: str,
        text: str,
        provenance: tuple[str, ...] | list[str],
    ) -> GateDecision:
        target = f"{self.agent_id}:prompt:{fragment}"
        return self._apply("prompt_edit", target, text, provenance)

    def share(
        self,
        target: str,
        recipients: tuple[str, ...] | list[str],
        provenance: tuple[str, ...] | list[str],
    ) -> GateDecision:
        version = self.gate.ledger.current(target)
        if version is None:
            event = self._event(
                "knowledge_share",
                target,
                "",
                provenance,
                recipients=tuple(recipients),
            )
            return GateDecision(False, "missing_source", None, event)
        payload = self.gate.ledger.content(version)
        base = tuple(provenance) + (version,)
        last: GateDecision | None = None
        for recipient in recipients:
            decision = self._apply(
                "knowledge_share",
                f"{recipient}:shared:{target}",
                payload,
                base,
                recipients=(recipient,),
            )
            if not decision.allowed:
                return decision
            last = decision
        if last is None:
            event = self._event("knowledge_share", target, payload, base)
            return GateDecision(False, "no_recipients", None, event)
        return last

    def memory(self, key: str) -> str | None:
        return self._read(f"{self.agent_id}:memory:{key}")

    def skills(self) -> dict[str, str]:
        prefix = f"{self.agent_id}:skill:"
        found: dict[str, str] = {}
        for target in self.gate.ledger.targets():
            if not target.startswith(prefix):
                continue
            content = self._read(target)
            if content is not None:
                found[target[len(prefix) :]] = content
        return found

    def prompt(self, fragment: str) -> str | None:
        return self._read(f"{self.agent_id}:prompt:{fragment}")

    def _apply(
        self,
        kind: str,
        target: str,
        payload: str,
        provenance: tuple[str, ...] | list[str],
        recipients: tuple[str, ...] = (),
    ) -> GateDecision:
        event = self._event(kind, target, payload, provenance, recipients)
        decision = self.gate.propose(event)
        if not decision.allowed:
            return decision
        if not self.gate.commit(decision):
            return GateDecision(False, "recheck_failed", None, event)
        return decision

    def _event(
        self,
        kind: str,
        target: str,
        payload: str,
        provenance: tuple[str, ...] | list[str],
        recipients: tuple[str, ...] = (),
    ) -> EvolutionEvent:
        return EvolutionEvent(
            event_id=uuid4().hex,
            kind=kind,  # type: ignore[arg-type]
            agent_id=self.agent_id,
            target=target,
            payload=payload,
            parent_version=self.gate.ledger.current(target),
            provenance=tuple(provenance),
            recipients=tuple(recipients),
        )

    def _read(self, target: str) -> str | None:
        version = self.gate.ledger.current(target)
        if version is None:
            return None
        return self.gate.ledger.content(version)
