"""In-memory evolution ledger. The method set is the stable storage interface."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from cogniguard.evolution.events import EvolutionEvent, SourceInfo


@dataclass
class _Record:
    event: EvolutionEvent
    status: str
    order: int


class EvolutionLedger:
    """Append-only version store. Rollback changes status; it does not delete rows."""

    def __init__(self) -> None:
        self._sources: dict[str, bool] = {}
        self._versions: dict[str, _Record] = {}
        self._by_target: dict[str, list[str]] = {}
        self._current: dict[str, str | None] = {}
        self._order = 0
        self._quarantined_sources: set[str] = set()
        self._quarantined_versions: set[str] = set()

    def register_source(self, info: SourceInfo) -> None:
        previous = self._sources.get(info.source_id)
        if previous is not None and previous != info.trusted:
            raise ValueError(f"source {info.source_id} already registered with a different trust")
        self._sources[info.source_id] = info.trusted

    def source_trusted(self, source_id: str) -> bool | None:
        """True or False if registered, None if this source was never registered."""
        return self._sources.get(source_id)

    def is_quarantined(self, source_or_version: str) -> bool:
        if source_or_version in self._quarantined_sources:
            return True
        if source_or_version in self._quarantined_versions:
            return True
        record = self._versions.get(source_or_version)
        return record is not None and record.status == "quarantined"

    def reserve(self, event: EvolutionEvent) -> str:
        version_id = uuid4().hex
        self._order += 1
        self._versions[version_id] = _Record(event=event, status="reserved", order=self._order)
        self._by_target.setdefault(event.target, []).append(version_id)
        return version_id

    def commit(self, version_id: str) -> None:
        record = self._require(version_id)
        if record.status != "reserved":
            raise ValueError(f"cannot commit version in status {record.status}")
        record.status = "committed"
        self._current[record.event.target] = version_id

    def cancel(self, version_id: str) -> None:
        record = self._require(version_id)
        if record.status != "reserved":
            raise ValueError(f"cannot cancel version in status {record.status}")
        record.status = "cancelled"

    def current(self, target: str) -> str | None:
        return self._current.get(target)

    def content(self, version_id: str) -> str:
        return self._require(version_id).event.payload

    def lineage(self, version_id: str) -> list[str]:
        """Newest first, following parent_version back to the root."""
        chain: list[str] = []
        seen: set[str] = set()
        version = version_id
        while version is not None and version not in seen and version in self._versions:
            seen.add(version)
            chain.append(version)
            version = self._versions[version].event.parent_version
        return chain

    def rollback(self, target: str, to_version: str) -> None:
        current = self._current.get(target)
        if current is None:
            raise ValueError(f"{target} has no current version")
        chain = self.lineage(current)
        if to_version not in chain:
            raise ValueError("to_version is not in the current lineage")
        for version_id in chain:
            if version_id == to_version:
                break
            record = self._versions[version_id]
            if record.status == "committed":
                record.status = "rolled_back"
        self._current[target] = to_version

    def descendants_of_source(self, source_id: str) -> set[str]:
        """Committed versions that depend on source_id, directly or through parent or provenance."""
        committed = [
            version_id
            for version_id, record in self._versions.items()
            if record.status == "committed"
        ]
        descendants: set[str] = set()
        changed = True
        while changed:
            changed = False
            for version_id in committed:
                if version_id in descendants:
                    continue
                if self._depends(self._versions[version_id].event, source_id, descendants):
                    descendants.add(version_id)
                    changed = True
        return descendants

    def quarantine_source(self, source_id: str) -> list[str]:
        """Roll each affected target back to the nearest version that does not depend on source_id.

        When every version in the current lineage depends on it, the target has no current
        version and those versions are marked quarantined. Rows are kept.
        """
        descendants = self.descendants_of_source(source_id)
        self._quarantined_sources.add(source_id)
        self._quarantined_versions.update(descendants)
        targets: list[str] = []
        seen: set[str] = set()
        ordered = sorted(descendants, key=lambda version_id: self._versions[version_id].order)
        for version_id in ordered:
            target = self._versions[version_id].event.target
            if target not in seen:
                seen.add(target)
                targets.append(target)
        for target in targets:
            current = self._current.get(target)
            if current is None:
                continue
            clean = next(
                (version_id for version_id in self.lineage(current) if version_id not in descendants),
                None,
            )
            if clean is None:
                for version_id in self.lineage(current):
                    record = self._versions[version_id]
                    if record.status == "committed" and version_id in descendants:
                        record.status = "quarantined"
                self._current[target] = None
            else:
                self.rollback(target, clean)
        return targets

    def history(self, target: str) -> list[tuple[str, str]]:
        return [
            (version_id, self._versions[version_id].status)
            for version_id in self._by_target.get(target, [])
        ]

    def targets(self) -> list[str]:
        return list(self._by_target)

    def _require(self, version_id: str) -> _Record:
        try:
            return self._versions[version_id]
        except KeyError as exc:
            raise ValueError(f"unknown version {version_id}") from exc

    @staticmethod
    def _depends(event: EvolutionEvent, source_id: str, descendants: set[str]) -> bool:
        if source_id in event.provenance:
            return True
        if any(item in descendants for item in event.provenance):
            return True
        return event.parent_version is not None and event.parent_version in descendants
