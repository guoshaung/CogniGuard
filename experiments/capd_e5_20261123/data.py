"""Load the synthetic confidential-secret dataset. Nothing here is written to the repository.

Input directory: $COGNIGUARD_DATA_DIR/synthetic, default ../cogniguard_data/synthetic
next to the checkout. Only targets, units and witness_sets are read. The private
values and salts are never opened.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

from cogniguard.governance.targets import ProtectedTarget

UnitRef = tuple[str, str]
REPO = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    root = os.environ.get("COGNIGUARD_DATA_DIR")
    base = Path(root) if root else REPO.parent / "cogniguard_data"
    return base / "synthetic"


@dataclass(frozen=True, eq=False)
class Secret:
    """One discrete secret with identity gain and a uniform prior."""

    target_id: str
    K: int
    tau: float
    units: tuple[UnitRef, ...]
    satisfied_by: dict[UnitRef, frozenset[str]]
    witness_sets: tuple[frozenset[UnitRef], ...]

    def leakage(self, held) -> float:
        """L(A) = log2(K / |S_A|), A restricted to this secret's units."""
        mine = [unit for unit in held if unit in self.satisfied_by]
        if not mine:
            return 0.0
        consistent = frozenset.intersection(*(self.satisfied_by[unit] for unit in mine))
        return math.log2(self.K / len(consistent))

    def leakage_star(self, held) -> float:
        """L*(A) = max over subsets. Identity gain with a uniform prior is monotone,
        so this equals L(A); the subset maximum is kept to follow the definition."""
        mine = tuple(sorted(unit for unit in held if unit in self.satisfied_by))
        best = 0.0
        for size in range(1, len(mine) + 1):
            for subset in combinations(mine, size):
                best = max(best, self.leakage(subset))
        return best

    def target(self, *, max_witness: int | None = None) -> ProtectedTarget | None:
        sets = tuple(w for w in self.witness_sets if max_witness is None or len(w) <= max_witness)
        if not sets:
            return None
        return ProtectedTarget(
            self.target_id, "teacher", "lab", sets, kind="teaching_asset", domain_size=self.K
        )


def load_secrets(K: int, root: Path | None = None) -> tuple[Secret, ...]:
    root = root or data_dir()
    targets = {}
    for record in _jsonl(root / "targets.jsonl"):
        if record["K"] == K and record["label_status"] == "computed":
            if record["gain"]["type"] != "identity" or record["prior"] != "uniform":
                raise ValueError(f"unsupported target {record['target_id']}")
            targets[record["target_id"]] = record
    units: dict[str, dict[UnitRef, frozenset[str]]] = defaultdict(dict)
    for record in _jsonl(root / "units.jsonl"):
        if record["target_id"] in targets:
            ref = (record["target_id"], record["unit_id"])
            units[record["target_id"]][ref] = frozenset(record["satisfied_by"])
    witnesses: dict[str, tuple[frozenset[UnitRef], ...]] = {}
    for record in _jsonl(root / "witness_sets.jsonl"):
        tid = record["target_id"]
        if tid in targets:
            witnesses[tid] = tuple(
                frozenset((tid, unit_id) for unit_id in group) for group in record["sets"]
            )
    secrets = []
    for tid in sorted(targets, key=_natural):
        record = targets[tid]
        secrets.append(
            Secret(
                tid,
                K,
                float(record["tau_bits"]),
                tuple(sorted(units[tid])),
                dict(units[tid]),
                witnesses[tid],
            )
        )
    return tuple(secrets)


def load_texts(K: int, root: Path | None = None) -> list[dict]:
    root = root or data_dir()
    wanted = {r["target_id"] for r in _jsonl(root / "targets.jsonl") if r["K"] == K}
    return [r for r in _jsonl(root / "texts.jsonl") if r["target_id"] in wanted]


def load_predicates(K: int, root: Path | None = None) -> dict[UnitRef, dict]:
    root = root or data_dir()
    wanted = {r["target_id"] for r in _jsonl(root / "targets.jsonl") if r["K"] == K}
    return {
        (r["target_id"], r["unit_id"]): r["predicate"]
        for r in _jsonl(root / "units.jsonl")
        if r["target_id"] in wanted
    }


def manifest_sha(root: Path | None = None) -> str:
    import hashlib

    root = root or data_dir()
    return hashlib.sha256((root / "MANIFEST.json").read_bytes()).hexdigest()


def _jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _natural(target_id: str):
    return tuple(int(part) if part.isdigit() else part for part in target_id.split("."))
