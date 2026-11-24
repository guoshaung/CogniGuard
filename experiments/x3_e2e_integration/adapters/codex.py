"""Codex KBPW outputs -> pe-1.0 Observations. Frozen mapping (PREREG_X3E2E §3.3).

This is the only place that touches Codex rows that mix predictions with labels. Prediction
fields go to observations; label fields (gold_*, eligible_release, input_release_ids,
instruction_pass) are dropped here and never forwarded. Labels for scoring are built
separately by the scenario builder from annotations.

| Codex method                                   | evidence_type             |
|------------------------------------------------|---------------------------|
| M1                                             | watermark                 |
| M1+source                                      | joint                     |
| M2, M3                                         | knowledge_bound_watermark |
| sha256, minhash, active_variants, issuance_lookup | fingerprint            |
| bm25, bge, bge_rerank                          | retrieval                 |
| plain (decoder on unmarked text)               | not mapped                |

Unit claims, the same rule for every method: every registered fact of each returned source,
plus any fact the method reports itself (pred_fact). The verifier's knowledge check then
decides which of them are confirmed; the rest stay suspected.
"""

from __future__ import annotations

from cogniguard.provenance.schema import (
    SCHEMA_VERSION,
    Candidate,
    CandidateSet,
    ConfidenceKind,
    DetectorStatus,
    EvidenceType,
    Observation,
    Presence,
    ScanStatus,
    UnitClaim,
)

METHOD_TYPE = {
    "M1": EvidenceType.WATERMARK,
    "M1+source": EvidenceType.JOINT,
    "M2": EvidenceType.KNOWLEDGE_BOUND_WATERMARK,
    "M3": EvidenceType.KNOWLEDGE_BOUND_WATERMARK,
    "sha256": EvidenceType.FINGERPRINT,
    "minhash": EvidenceType.FINGERPRINT,
    "active_variants": EvidenceType.FINGERPRINT,
    "issuance_lookup": EvidenceType.FINGERPRINT,
    "bm25": EvidenceType.RETRIEVAL,
    "bge": EvidenceType.RETRIEVAL,
    "bge_rerank": EvidenceType.RETRIEVAL,
}
DROPPED = {"gold_release", "gold_source", "gold_fact", "eligible_release", "input_release_ids",
           "instruction_pass"}


def _cset(items):
    items = list(dict.fromkeys(items))
    if not items:
        return CandidateSet(ScanStatus.NONE)
    return CandidateSet(ScanStatus.FOUND, tuple(Candidate(i, s) for i, s in items))


def to_observation(row: dict, *, artifact_id: str, holder: str, observed_at: float,
                   facts_of_source: dict, codex_ref: str) -> Observation | None:
    method = row["method"]
    etype = METHOD_TYPE.get(method)
    if etype is None:
        return None
    if "pred_release" in row:  # decoder rows
        sources = [(s, None) for s in row.get("pred_source", [])]
        releases = [(r, None) for r in row.get("pred_release", [])]
        own_facts = row.get("pred_fact", [])
    else:                      # content baseline rows
        scores = {r["source_id"]: r.get("score") for r in row.get("ranked_sources", [])}
        sources = [(s, scores.get(s)) for s in row.get("source_ids", [])]
        releases = [(r, None) for r in row.get("release_ids", [])]
        own_facts = []
    facts = {f: None for s, _ in sources for f in facts_of_source.get(s, ())}
    facts.update({f: None for f in own_facts})
    claims = tuple(UnitClaim((f.rsplit(":", 1)[0], f), Presence.PRESENT, None) for f in sorted(facts))
    return Observation(
        SCHEMA_VERSION, f"codex:{method}:{artifact_id}", artifact_id, holder, etype,
        f"codex-{method}@{codex_ref}", DetectorStatus.OK, _cset(sources), _cset(releases), claims,
        None, ConfidenceKind.UNCALIBRATED, None, 1, observed_at,
        artifact_sha256=row.get("text_sha256"),
        extra={"codex_case_id": row["case_id"], "codex_variant": row["variant"]},
    )
