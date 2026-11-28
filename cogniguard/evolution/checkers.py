"""Deterministic checkers for evolution proposals. No model calls."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from cogniguard.evolution.events import EvolutionEvent
from cogniguard.evolution.gate import CheckResult
from cogniguard.evolution.ledger import EvolutionLedger

_DEFAULT_INSTRUCTION_PATTERNS = (
    r"ignore\s+(all|previous|prior)",
    r"disregard",
    r"you must always",
    r"from now on",
    r"system prompt",
    r"<tool_call>",
    r"execute",
    r"忽略之前",
    r"从现在开始",
    r"你必须总是",
)

_EXECUTABLE = ("import ", "exec(", "eval(", "subprocess", "os.system", "__")
_SKILL_FIELDS = {"name", "description", "template", "allowed_tools"}
_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_NATIONAL_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PROTECTED = ("guardrail", "safety_policy", "access_policy", "evolution_gate", "checker")


class UntrustedInstructionChecker:
    """Refuse instruction-shaped text whose provenance is not fully trusted. MLAS #7 #12 #17."""

    name = "untrusted_instruction"

    def __init__(self, patterns: tuple[str, ...] = _DEFAULT_INSTRUCTION_PATTERNS) -> None:
        self._patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        if not self._has_untrusted(event, ledger):
            return CheckResult(True)
        if any(pattern.search(event.payload) for pattern in self._patterns):
            return CheckResult(False, "untrusted_instruction")
        return CheckResult(True)

    @staticmethod
    def _has_untrusted(event: EvolutionEvent, ledger: EvolutionLedger) -> bool:
        for source_id in event.provenance:
            trusted = ledger.source_trusted(source_id)
            if trusted is not True:
                return True
        return False


class SkillSpecChecker:
    """Require a closed JSON skill spec inside the agent's capability set. MLAS #12 #14 #15."""

    name = "skill_spec"

    def __init__(
        self,
        capabilities: dict[str, list[str] | set[str]],
        url_allowlist: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._capabilities = {agent: set(tools) for agent, tools in capabilities.items()}
        self._allowlist = {host.lower() for host in url_allowlist}

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        del ledger
        try:
            spec = json.loads(event.payload)
        except json.JSONDecodeError:
            return CheckResult(False, "invalid_skill_spec")
        if not isinstance(spec, dict) or set(spec) != _SKILL_FIELDS:
            return CheckResult(False, "invalid_skill_spec")
        tools = spec["allowed_tools"]
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            return CheckResult(False, "invalid_skill_spec")
        granted = self._capabilities.get(event.agent_id, set())
        if not set(tools) <= granted:
            return CheckResult(False, "capability_expansion")
        template = spec["template"]
        if not isinstance(template, str):
            return CheckResult(False, "invalid_skill_spec")
        if any(token in template for token in _EXECUTABLE):
            return CheckResult(False, "executable_content")
        for match in _URL.findall(template):
            host = urlparse(match).hostname or ""
            if host.lower() not in self._allowlist:
                return CheckResult(False, "url_not_allowed")
        return CheckResult(True)


class MemoryPolicyChecker:
    """Bound memory size and keep shared memory free of common PII patterns. MLAS #7 #9 #10."""

    name = "memory_policy"

    def __init__(self, max_chars: int = 2000) -> None:
        self._max_chars = max_chars

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        del ledger
        if len(event.payload) > self._max_chars:
            return CheckResult(False, "payload_too_long")
        if event.kind == "knowledge_share" and self._has_pii(event.payload):
            return CheckResult(False, "pii_in_shared_memory")
        return CheckResult(True)

    @staticmethod
    def _has_pii(payload: str) -> bool:
        return bool(_EMAIL.search(payload) or _PHONE.search(payload) or _NATIONAL_ID.search(payload))


class ProtectedTargetChecker:
    """Refuse edits that name a governance invariant. MLAS #17 #18 #20."""

    name = "protected_target"

    def __init__(self, names: tuple[str, ...] = _PROTECTED) -> None:
        self._names = tuple(name.lower() for name in names)

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        del ledger
        haystack = f"{event.target}\n{event.payload}".lower()
        if any(name in haystack for name in self._names):
            return CheckResult(False, "protected_invariant")
        return CheckResult(True)


class QuarantinedLineageChecker:
    """Refuse proposals that still cite a quarantined source or its descendants. MLAS #9 #22."""

    name = "quarantined_lineage"

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        cited = list(event.provenance)
        if event.parent_version is not None:
            cited.append(event.parent_version)
        if any(ledger.is_quarantined(item) for item in cited):
            return CheckResult(False, "quarantined_lineage")
        return CheckResult(True)


class ShareRecipientChecker:
    """Share only with recipients the sender is allowed to reach. MLAS #22 #24."""

    name = "share_recipient"

    def __init__(self, share_allowed: dict[str, set[str] | list[str]]) -> None:
        self._allowed = {agent: set(recipients) for agent, recipients in share_allowed.items()}

    def check(self, event: EvolutionEvent, ledger: EvolutionLedger) -> CheckResult:
        del ledger
        allowed = self._allowed.get(event.agent_id, set())
        if any(recipient not in allowed for recipient in event.recipients):
            return CheckResult(False, "share_not_allowed")
        return CheckResult(True)


def default_checkers(
    capabilities: dict[str, list[str] | set[str]],
    share_allowed: dict[str, set[str] | list[str]],
    url_allowlist: tuple[str, ...] | list[str] = (),
) -> dict[str, list]:
    """Checkers grouped by evolution kind."""
    untrusted = UntrustedInstructionChecker()
    skill = SkillSpecChecker(capabilities, url_allowlist)
    memory = MemoryPolicyChecker()
    protected = ProtectedTargetChecker()
    quarantined = QuarantinedLineageChecker()
    share = ShareRecipientChecker(share_allowed)
    return {
        "memory_write": [untrusted, memory, quarantined],
        "prompt_edit": [untrusted, protected, quarantined],
        "skill_create": [untrusted, skill, protected, quarantined],
        "knowledge_share": [memory, quarantined, share],
    }
