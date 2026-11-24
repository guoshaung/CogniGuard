"""Knowledge checkers for the X3-E2E verifier (pe-1.0 `UnitChecker` signature).

`lexical`   : the frozen TextUnitChecker (containment >= 0.95).
`nli-replay`: replays per-(artifact, unit) judgments that Codex produced with the original
              frozen NLI (DeBERTa-v3-base-mnli-fever-anli @ 6f5cf0a). Nothing is re-inferred here.

Semantics (DEVIATIONS §7):
  entailment               -> PRESENT  (semantic verification of content; may confirm a holding)
  neutral / contradiction  -> UNKNOWN  (claim stays suspected; an altered fact is not proof that
                                        the holder lacks the other units)
  missing judgment         -> UNKNOWN
A checker only answers "is this unit in this artifact". It cannot create an event, a credential
or a budget credit: those come only from signed event_claim / credential fields, so NLI can
never offset the propagation budget.

Judgment file (JSONL), one row per (artifact, unit):
  {"artifact_sha256": hex, "unit": [resource_id, unit_id], "judgment": "entailment|neutral|contradiction",
   "score": float|null, "method_version": "...", "split": "calibration|test"}
Rows must not carry gold fields; the loader rejects them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.schema import Presence, SchemaError, Unit, _check_no_gold

LABELS = {"entailment": Presence.PRESENT, "neutral": Presence.UNKNOWN, "contradiction": Presence.UNKNOWN}


class NliReplayChecker:
    def __init__(self, path: Path, split: str | None = None):
        self.table: dict[tuple[str, Unit], Presence] = {}
        self.method_versions: set[str] = set()
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            _check_no_gold(row)
            if split and row.get("split") != split:
                continue
            if row["judgment"] not in LABELS:
                raise SchemaError(f"unknown NLI judgment {row['judgment']!r}")
            key = (row["artifact_sha256"], (row["unit"][0], row["unit"][1]))
            if key in self.table and self.table[key] is not LABELS[row["judgment"]]:
                raise SchemaError(f"conflicting NLI judgments for {key}")
            self.table[key] = LABELS[row["judgment"]]
            self.method_versions.add(row.get("method_version", ""))

    def __call__(self, artifact: Artifact | None, unit: Unit) -> Presence:
        if artifact is None:
            return Presence.UNKNOWN
        digest = hashlib.sha256(artifact.text.encode()).hexdigest()
        return self.table.get((digest, unit), Presence.UNKNOWN)
