from experiments.mmfopd_uci.portuguese_transfer_probe import make_portuguese_profile
from experiments.mmfopd_uci.runner import FIELDS


def test_portuguese_task_and_profile_share_subject_without_changing_real_fields():
    row = {field: "1" for field in FIELDS}
    row.update(G1="10", G2="12", G3="13", romantic="no", Pstatus="T")
    profile, task = make_portuguese_profile(row, 0)
    assert task.knowledge == "language_progress"
    assert "Portuguese" in task.question
    assert next(record for record in profile.profile_records if record.record_id == "G1").knowledge == "language_progress"
    assert next(record for record in profile.profile_records if record.record_id == "G2").value == .6
    assert not profile.local_only_fields
