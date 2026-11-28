"""Evolution events and source records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EvolutionKind = Literal["memory_write", "skill_create", "prompt_edit", "knowledge_share"]


@dataclass(frozen=True)
class EvolutionEvent:
    event_id: str  # uuid4().hex
    kind: EvolutionKind
    agent_id: str  # agent that proposes the change
    target: str  # memory key, skill name, prompt fragment, or shared object id
    payload: str  # proposed content
    parent_version: str | None  # current version of the target; None when creating
    provenance: tuple[str, ...]  # source ids: tool output, pages, other versions
    recipients: tuple[str, ...] = ()  # used only by knowledge_share


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    trusted: bool  # True for internal components; False for pages, tools, user input
