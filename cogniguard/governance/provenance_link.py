"""Switchable provenance link for evidence Codex may supply later.

The link classifies sources and decides which rows could become ledger
facts. It does not write ``DisclosureStore`` and it does not score an
algorithm. A missing or unverified source stays unknown. Unknown is not
the same fact as "this knowledge was never propagated."
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from cogniguard.governance.source_evidence import SourceEvidence, load_evidence_list

MODES = ("static", "fingerprint", "ideal", "real")
SOURCE_CLASSES = ("verified", "candidate", "unknown", "conflict")
MODE_TYPES = {
    "static": frozenset(),
    "fingerprint": frozenset({"fingerprint"}),
    "ideal": frozenset({"ideal"}),
    "real": frozenset({"fingerprint", "watermark", "signed_credential", "trusted_log"}),
}
UnitRef = tuple[str, str]


@dataclass(frozen=True, slots=True)
class SourceAssessment:
    """One source after a round. ``propagated is None`` means not known."""

    source_id: str
    source_class: str
    issuance_ids: tuple[str, ...]
    issuance_status: str
    propagated: bool | None
    ledger_writable: bool
    round_id: int
    evidence_ids: tuple[str, ...] = ()
    holder_principal_id: str | None = None
    matched_units: tuple[UnitRef, ...] = ()


@dataclass(frozen=True, slots=True)
class LedgerFact:
    """A verified propagation holding. Candidates never use this type."""

    source_id: str
    issuance_ids: tuple[str, ...]
    holder_principal_id: str | None
    units: tuple[UnitRef, ...]
    trusted_event_id: str | None
    round_id: int
    evidence_id: str


@dataclass(frozen=True, slots=True)
class LedgerRejection:
    evidence_id: str
    source_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class LinkSnapshot:
    """Interface result. ``evaluation_status`` is never an algorithm pass."""

    mode: str
    round_id: int
    sources: tuple[SourceAssessment, ...]
    recovery: str
    admitted: tuple[LedgerFact, ...]
    rejected: tuple[LedgerRejection, ...]
    evaluation_status: str = "interface_only"
    writes_disclosure_store: bool = False


def _evidence_from_payload(payload: dict) -> tuple[SourceEvidence, ...]:
    if "channels" in payload:
        rows = []
        for items in payload["channels"].values():
            rows.extend(items)
        return tuple(SourceEvidence.from_dict(item) for item in rows)
    if "evidence" in payload:
        return load_evidence_list(payload)
    return ()


def _source_keys(row: SourceEvidence) -> tuple[str, ...]:
    if row.candidate_issuance_ids:
        return row.candidate_issuance_ids
    if row.holder_principal_id:
        return (f"holder:{row.holder_principal_id}",)
    return (f"evidence:{row.evidence_id}",)


def _classify(row: SourceEvidence) -> tuple[str, str, bool | None, bool, str]:
    """Return class, issuance status, propagated, ledger flag, and reject reason."""
    if row.verification_status == "conflict":
        return "conflict", "conflict", None, False, "conflict"
    if row.evidence_type in {"watermark", "fingerprint"}:
        if row.candidate_issuance_ids:
            return "candidate", "candidate", None, False, "unverified_candidate"
        return "unknown", "unknown", None, False, "unknown_source"
    if row.verification_status == "absent":
        return "unknown", "unknown", None, False, "unknown_source"
    if not row.is_trusted_event():
        status = "candidate" if row.candidate_issuance_ids else "unknown"
        reason = "unverified_candidate" if status == "candidate" else "unknown_source"
        return status, status, None, False, reason
    propagated = True if row.confirms_propagation() else None
    issuance = "verified" if row.trusted_issuance_ids() else "unknown"
    # A credential can verify issuance identity and still not be a holding.
    writable = bool(row.confirms_propagation() and row.holder_principal_id)
    return "verified", issuance, propagated, writable, ""


def _units_of(rows: tuple[SourceEvidence, ...]) -> tuple[UnitRef, ...]:
    found: list[UnitRef] = []
    for row in rows:
        for unit in row.matched_knowledge_units:
            if unit not in found:
                found.append(unit)
    return tuple(found)


def _holder_of(rows: tuple[SourceEvidence, ...]) -> str | None:
    holders = {row.holder_principal_id for row in rows if row.holder_principal_id}
    if len(holders) == 1:
        return next(iter(holders))
    return None


def _disjoint_holdings(rows: tuple[SourceEvidence, ...]) -> bool:
    asserted = [frozenset(row.matched_knowledge_units) for row in rows if row.holdings_asserted]
    if len(asserted) < 2:
        return False
    return any(left and right and not (left & right) for left in asserted for right in asserted)


def _holders_disagree(rows: tuple[SourceEvidence, ...]) -> bool:
    holders = {row.holder_principal_id for row in rows if row.holder_principal_id}
    return len(holders) > 1


class _Group:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.rows: list[tuple[SourceEvidence, tuple]] = []

    def add(self, row: SourceEvidence, classified: tuple) -> None:
        self.rows.append((row, classified))

    def resolve(self, round_id: int) -> SourceAssessment:
        classes = {item[1][0] for item in self.rows}
        evidence_ids = tuple(row.evidence_id for row, _ in self.rows)
        issuance_ids = tuple(
            dict.fromkeys(
                issuance_id
                for row, _ in self.rows
                for issuance_id in row.candidate_issuance_ids
            )
        )
        verified_rows = tuple(row for row, info in self.rows if info[0] == "verified")
        conflict = "conflict" in classes or (
            len(verified_rows) >= 2
            and (_holders_disagree(verified_rows) or _disjoint_holdings(verified_rows))
        )
        if conflict:
            return SourceAssessment(
                self.source_id,
                "conflict",
                issuance_ids,
                "conflict",
                None,
                False,
                round_id,
                evidence_ids,
            )
        if verified_rows:
            propagated = True if any(row.confirms_propagation() for row in verified_rows) else None
            writable = any(
                row.confirms_propagation() and row.holder_principal_id for row in verified_rows
            )
            issuance = "unknown"
            if any(row.trusted_issuance_ids() for row in verified_rows):
                issuance = "verified"
            return SourceAssessment(
                self.source_id,
                "verified",
                issuance_ids,
                issuance,
                propagated,
                writable,
                round_id,
                evidence_ids,
                _holder_of(verified_rows),
                _units_of(verified_rows),
            )
        if "candidate" in classes:
            return SourceAssessment(
                self.source_id,
                "candidate",
                issuance_ids,
                "candidate" if issuance_ids else "unknown",
                None,
                False,
                round_id,
                evidence_ids,
            )
        return _unknown(self.source_id, round_id, evidence_ids)


def _unknown(source_id: str, round_id: int, evidence_ids: tuple[str, ...] = ()) -> SourceAssessment:
    return SourceAssessment(
        source_id,
        "unknown",
        (source_id,) if not source_id.startswith(("holder:", "evidence:")) else (),
        "unknown",
        None,
        False,
        round_id,
        evidence_ids,
    )


def _recovery(sources: tuple[SourceAssessment, ...]) -> str:
    if not sources or all(item.source_class == "unknown" for item in sources):
        return "none"
    if all(item.source_class == "verified" for item in sources):
        return "full"
    return "partial"


def _merge(prior: SourceAssessment | None, incoming: SourceAssessment) -> SourceAssessment:
    """A later miss does not erase a verified source or call it unpropagated."""
    if prior is None or incoming.source_class == "conflict":
        return incoming
    if incoming.source_class == "unknown":
        return prior
    if incoming.source_class == "candidate" and prior.source_class == "verified":
        return prior
    if prior.source_class == "verified" and incoming.source_class == "verified":
        units = tuple(dict.fromkeys((*prior.matched_units, *incoming.matched_units)))
        holders = {
            item
            for item in (prior.holder_principal_id, incoming.holder_principal_id)
            if item
        }
        if len(holders) > 1 or (
            prior.matched_units
            and incoming.matched_units
            and not set(prior.matched_units) & set(incoming.matched_units)
        ):
            return replace(
                incoming,
                source_class="conflict",
                issuance_status="conflict",
                propagated=None,
                ledger_writable=False,
            )
        propagated = True if prior.propagated or incoming.propagated else None
        evidence_ids = tuple(dict.fromkeys((*prior.evidence_ids, *incoming.evidence_ids)))
        return replace(
            incoming,
            matched_units=units,
            holder_principal_id=next(iter(holders)) if holders else None,
            propagated=propagated,
            ledger_writable=prior.ledger_writable or incoming.ledger_writable,
            issuance_status="verified"
            if "verified" in {prior.issuance_status, incoming.issuance_status}
            else incoming.issuance_status,
            evidence_ids=evidence_ids,
        )
    if incoming.source_class == "verified":
        return incoming
    return incoming


class ProvenanceLink:
    """One mode of the link. Create another instance to switch modes."""

    def __init__(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        self._round = 0
        self._sources: dict[str, SourceAssessment] = {}
        self._facts: dict[str, LedgerFact] = {}

    def update(self, payload: dict) -> LinkSnapshot:
        round_id = int(payload.get("round_id", self._round + 1))
        if round_id < self._round:
            raise ValueError("round_id must not go backwards")
        self._round = round_id
        accepted = MODE_TYPES[self.mode]
        groups: dict[str, _Group] = {}
        rejected: list[LedgerRejection] = []
        for row in _evidence_from_payload(payload):
            keys = _source_keys(row)
            if row.evidence_type not in accepted:
                for key in keys:
                    rejected.append(LedgerRejection(row.evidence_id, key, "mode_excluded"))
                continue
            classified = _classify(row)
            for key in keys:
                groups.setdefault(key, _Group(key)).add(row, classified)
        for source_id in payload.get("expected_source_ids", ()):
            groups.setdefault(str(source_id), _Group(str(source_id)))

        for source_id, group in groups.items():
            if not group.rows:
                incoming = _unknown(source_id, round_id)
            else:
                incoming = group.resolve(round_id)
            merged = _merge(self._sources.get(source_id), incoming)
            self._sources[source_id] = merged
            if merged.source_class == "conflict":
                self._facts.pop(source_id, None)
            elif merged.ledger_writable:
                event = _event_for(group, source_id)
                previous = self._facts.get(source_id)
                if event is None and previous is not None:
                    event = previous.trusted_event_id
                if event is not None or previous is None:
                    evidence_id = merged.evidence_ids[-1] if merged.evidence_ids else ""
                    self._facts[source_id] = LedgerFact(
                        source_id,
                        merged.issuance_ids,
                        merged.holder_principal_id,
                        merged.matched_units,
                        event,
                        merged.round_id,
                        evidence_id,
                    )
            for row, info in group.rows:
                if info[3] and merged.source_class == "verified" and merged.ledger_writable:
                    continue
                reason = "conflict" if merged.source_class == "conflict" else info[4]
                if reason:
                    rejected.append(LedgerRejection(row.evidence_id, source_id, reason))

        sources = tuple(self._sources[key] for key in sorted(self._sources))
        admitted = tuple(self._facts[key] for key in sorted(self._facts))
        return LinkSnapshot(
            self.mode,
            round_id,
            sources,
            _recovery(sources),
            admitted,
            tuple(rejected),
        )


def _event_for(group: _Group, source_id: str) -> str | None:
    for row, info in group.rows:
        if info[0] != "verified" or source_id not in _source_keys(row):
            continue
        if row.confirms_propagation():
            return row.trusted_event_id
    return None


def open_provenance_link(mode: str) -> ProvenanceLink:
    """Open one of static, fingerprint, ideal, or real. Nothing is written."""
    return ProvenanceLink(mode)
