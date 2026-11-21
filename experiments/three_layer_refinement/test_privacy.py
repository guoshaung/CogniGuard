import copy

from experiments.mmfopd_uci.runner import CONFIG, FIELDS, PRIVATE, make_profile
from experiments.three_layer_refinement.privacy import slot_fields
from protection.student_profile.src.fopd.profile_selector import ProfileSelector


def example():
    row = {key: "1" for key in FIELDS}
    row.update(G1="10", G2="12", G3="13", romantic="no", Pstatus="T")
    return make_profile(row, 0)


def test_periods_survive_equal_budget():
    profile, task = example()
    picked = slot_fields("TaskSlot-MMFOPD-3", profile, task, 17, [])
    assert {"G1", "G2"} <= picked
    assert len(picked) == 3 and not picked & PRIVATE
    assert "G2" not in slot_fields("MM-FOPD", profile, task, 17, [])


def test_alignment_cannot_bypass_sensitivity_and_budget():
    profile, task = example()
    next(r for r in profile.profile_records if r.record_id == "G2").sensitivity = .99
    cfg = copy.deepcopy(CONFIG)
    cfg["fopd"]["unit_budget"].update(distinct_requested_types=["mastery"], max_units=1)
    result = ProfileSelector(cfg).select(profile, task)
    assert len(result) == 1 and result[0].record.record_id == "G1"


def test_exact_task_id_boundaries():
    profile, task = example()
    next(r for r in profile.profile_records if r.record_id == "G2").record_id = "G20"
    picked = slot_fields("TaskSlot-MMFOPD-3", profile, task, 17, [])
    assert "G20" not in picked
