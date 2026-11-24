"""Locks the non-degeneracy contract. Does not score a new proposition."""

from experiments.nowm_scenarios_20261125.verify import INFOS, KS, RULES, full_report


def test_enumeration_matches_and_the_scenarios_stay_mixed():
    report = full_report()
    assert report["failures"] == []
    assert report["mismatches"] == []
    assert report["enumeration_checks"] == 2 * 4 * 3 * 10
    for domain, sizes in report["witness_sizes"].items():
        assert sizes == (3, 4, 3, 5, 5, 5), domain
    by = {}
    oracle_by = {}
    for row in report["rows"]:
        key = (row["domain"], row["k"], row["info"], row["rule"])
        by[key] = row["decisions"]
        oracle_by[(row["domain"], row["k"])] = (row["oracle_allows"], row["oracle_denies"])
        assert row["unauthorized_success"] == 0
        assert row["utility"] == (
            (row["oracle_allows"] - row["false_refusal"]) / row["oracle_allows"]
        )
    for k in KS:
        assert oracle_by[("teacher", k)] == oracle_by[("student", k)]
        assert oracle_by[("teacher", k)][0] > 0
        assert oracle_by[("teacher", k)][1] > 0
        for info in INFOS:
            for rule in RULES:
                assert by[("teacher", k, info, rule)] == by[("student", k, info, rule)]
    for cell in report["findings"]["cells"]:
        if cell["domain"] != "teacher":
            continue
        assert cell["capd_all_harmful"] == 0
        assert cell["capd_all_utility"] == 1.0
        if cell["k"] == 1:
            assert cell["evidence_flips"] == ["r4"]
            assert cell["trusted_event_harmful"] == 1
        if cell["k"] == 2:
            assert cell["evidence_flips"] == ["r3"]
            assert cell["quota_refuses_capd_allow"] == ["r7"]
            assert cell["pairwise_matches_capd"] is True
        if cell["k"] == 3:
            assert cell["oracle_allows"] == 1
            assert cell["union_stricter_than_capd"] == ["r10"]
            assert cell["quota_allows_capd_deny"] == ["r5", "r9"]
            assert cell["trusted_event_harmful"] == 2
