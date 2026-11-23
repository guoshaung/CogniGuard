import pytest

from experiments.datasets.audit_io import raw_dir
from experiments.datasets.eedi_exam.audit import audit as eedi_audit, misconception_id
from experiments.datasets.sumleaks.audit import audit as sum_audit, defense_match


def test_exact_names_and_numeric_id_formats():
    assert misconception_id("12.0") == misconception_id("12")
    assert defense_match("A combination of tax and taxation is sensitive.", {"tax"})[:2] == ("partial", ["tax"])
    assert defense_match("A combination of taxation is sensitive.", {"tax"})[:2] == ("none", [])


def test_local_eedi():
    folder = raw_dir() / "eedi"
    if not all((folder / name).is_file() for name in ("train.csv", "misconception_mapping.csv")):
        pytest.skip("local Eedi inputs unavailable")
    report, hashes = eedi_audit(folder)
    assert report["unmapped_used_ids"] == 0
    assert sum(report["distinct_misconceptions_per_question"].values()) == report["csv"]["train.csv"]["rows"]
    for trial in report["feasibility"].values():
        assert trial["accepted"] + trial["failed_slots"] == trial["targets"]
    assert all(len(v) == 64 for v in hashes.values())


def test_local_sumleaks():
    folder = raw_dir() / "sumleaks"
    if not any(folder.glob("experiment_*_def_adv_both.json")):
        pytest.skip("local Sum Leaks inputs unavailable")
    report, hashes = sum_audit(folder)
    assert len(hashes) == len(report["scenes"]) == sum(report["coverage"].values()) == 119
    assert len(set(report["representative_ids"])) == 10
    assert all(all(pair["jaccard"] >= .8 for pair in scene["different_name_candidates"])
               for scene in report["scenes"].values())
