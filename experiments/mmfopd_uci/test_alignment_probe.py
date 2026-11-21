from experiments.mmfopd_uci.alignment_probe import ARMS, aligned_fields
from experiments.mmfopd_uci.runner import FIELDS, make_profile


def _row():
    row = {field: "1" for field in FIELDS}
    row.update(G1="10", G2="12", G3="13", romantic="no", Pstatus="T")
    return row


def test_aligned_progress_arms_keep_equal_budget_and_no_private_fields():
    profile, task = make_profile(_row(), 0)
    mi_order = ["G2", "G1", "absences", "studytime"]
    base = aligned_fields("MM-FOPD", profile, task, 17, mi_order)
    swap = aligned_fields("SwapG1ForG2-3", profile, task, 17, mi_order)
    aligned = aligned_fields("AlignedG1G2-3", profile, task, 17, mi_order)
    assert len(base) == len(swap) == len(aligned) == 3
    assert "G1" in base and "G2" not in base
    assert "G2" in swap and "G1" not in swap
    assert {"G1", "G2"} <= aligned
    assert "health" not in aligned and "romantic" not in aligned
    assert len(ARMS) == 4
