"""The dry-run count is the pre-registered grid and does not execute it."""

from __future__ import annotations

from experiments.capd_e3a_20261123.run import iter_specs


def test_grid_counts_every_preregistered_combination() -> None:
    specs = tuple(iter_specs())
    assert len(specs) == 10 * 2 * 2 * 3 * 3 * 10
    assert len(specs) == 3600
    assert sum(spec.arm == "no_defense" for spec in specs) == 360
    assert sum(spec.arm == "capd_any" for spec in specs) == 3 * 360
    assert sum(spec.arm == "capd_rel" for spec in specs) == 6 * 360
