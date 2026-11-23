"""Turn unstructured text into disclosed units and inference advantage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, kw_only=True)
class Measurement:
    units: frozenset[tuple[str, str]]
    bits: dict[str, float] = field(default_factory=dict)
    method: str


class DisclosureMeter(Protocol):
    def measure(
        self, text: str, *, candidate_units: frozenset[tuple[str, str]]
    ) -> Measurement: ...
