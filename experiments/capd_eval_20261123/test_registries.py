"""R-syn matches the pre-registered description. R-edu is loaded from the pack."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from experiments.capd_eval_20261123.registries import (
    SYNTHETIC_SEED,
    education_targets,
    synthetic_targets,
)
from experiments.capd_eval_20261123.run import iter_specs


def test_synthetic_registry_matches_the_preregistration() -> None:
    targets = synthetic_targets()
    assert synthetic_targets(SYNTHETIC_SEED) == targets
    assert len(targets) == 20
    assert sum(len(target.witness_sets) == 2 for target in targets) == 6
    assert sum(len(target.witness_sets) == 1 for target in targets) == 14
    sizes = [len(witness) for target in targets for witness in target.witness_sets]
    assert set(sizes) <= {2, 3, 4}
    for size in (2, 3, 4):
        assert abs(sizes.count(size) / len(sizes) - 1 / 3) < 0.05
    owners: dict[tuple[str, str], set[str]] = {}
    for target in targets:
        units = set()
        for witness in target.witness_sets:
            units.update(witness)
        for unit in units:
            owners.setdefault(unit, set()).add(target.target_id)
    shared = sum(1 for used_by in owners.values() if len(used_by) > 1)
    assert abs(shared / len(owners) - 0.20) < 0.02


def test_preregistration_file_matches_its_recorded_hash() -> None:
    directory = Path(__file__).resolve().parent
    recorded = (directory / "PREREG_E2.sha256").read_text(encoding="utf-8").split()[0]
    digest = hashlib.sha256((directory / "PREREG_E2.md").read_bytes()).hexdigest()
    assert recorded == digest


def test_education_registry_reads_the_asset_pack() -> None:
    if not os.environ.get("COGNIGUARD_ASSET_PACK", "").strip():
        pytest.skip("COGNIGUARD_ASSET_PACK is not set")
    targets = education_targets()
    assert len(targets) == 15
    assert all(len(target.witness_sets) == 1 for target in targets)


def test_grid_counts_every_preregistered_combination() -> None:
    assert len(tuple(iter_specs())) == 17 * 2 * 2 * 10
