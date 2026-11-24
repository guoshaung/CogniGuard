"""Load the Sum Leaks secrets for E7. Nothing here is written to the repository.

Input: $COGNIGUARD_DATA_DIR/sumleaks (default ../cogniguard_data/sumleaks), produced by
`python -m experiments.datasets.sumleaks.generate`. Only targets, units, witness_sets
and leakage are read; secrets_private.jsonl is never opened.

Sum Leaks leakage comes from joins, not from intersecting per-table candidate sets,
so L(A) is looked up in the generator's per-subset table instead of computed by the
E5 intersection rule. Everything else reuses the frozen E5 code.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from cogniguard.governance.targets import ProtectedTarget
from experiments.capd_e5_20261123.data import REPO, Secret, _jsonl, _natural

POOLED_K = 0  # rows report K = 0: all secrets form one pool, K varies per secret


def data_dir() -> Path:
    root = os.environ.get("COGNIGUARD_DATA_DIR")
    return (Path(root) if root else REPO.parent / "cogniguard_data") / "sumleaks"


@dataclass(frozen=True, eq=False)
class JoinSecret(Secret):
    table: dict = field(default_factory=dict)

    def leakage(self, held) -> float:
        mine = frozenset(unit for unit in held if unit in self.satisfied_by)
        return self.table[mine]

    def target(self, *, max_witness: int | None = None) -> ProtectedTarget | None:
        sets = tuple(w for w in self.witness_sets if max_witness is None or len(w) <= max_witness)
        if not sets:
            return None
        return ProtectedTarget(self.target_id, "data-owner", "lab", sets,
                               kind="student_attribute", domain_size=self.K)


def load_secrets(root: Path | None = None) -> tuple[JoinSecret, ...]:
    root = root or data_dir()
    targets = {r["target_id"]: r for r in _jsonl(root / "targets.jsonl")
               if r["label_status"] == "computed"}
    units: dict[str, dict] = defaultdict(dict)
    for r in _jsonl(root / "units.jsonl"):
        if r["target_id"] in targets:
            units[r["target_id"]][(r["target_id"], r["unit_id"])] = frozenset(r["satisfied_by"])
    witnesses = {}
    for r in _jsonl(root / "witness_sets.jsonl"):
        tid = r["target_id"]
        if tid in targets:
            witnesses[tid] = tuple(frozenset((tid, u) for u in group) for group in r["sets"])
    tables: dict[str, dict] = defaultdict(dict)
    for r in _jsonl(root / "leakage.jsonl"):
        tid = r["target_id"]
        if tid in targets:
            tables[tid][frozenset((tid, u) for u in r["units"])] = float(r["L_bits"])
    out = []
    for tid in sorted(targets, key=_natural):
        record = targets[tid]
        if record["gain"]["type"] != "identity" or record["prior"] != "uniform":
            raise ValueError(f"unsupported target {tid}")
        out.append(JoinSecret(tid, int(record["K"]), float(record["tau_bits"]),
                              tuple(sorted(units[tid])), dict(units[tid]), witnesses[tid],
                              table=dict(tables[tid])))
    return tuple(out)


def manifest_sha(root: Path | None = None) -> str:
    import hashlib

    return hashlib.sha256(((root or data_dir()) / "MANIFEST.json").read_bytes()).hexdigest()
