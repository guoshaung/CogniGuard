from experiments.rag_real.alignment_probe import sentence_fraction
from experiments.c2rag_v3.policy_selector import select_copyright_candidate


def test_support_fraction_ignores_whitespace_but_not_missing_sentence():
    refs = ["A fact is here.", "The second fact matters."]
    assert sentence_fraction(refs, "A   fact is here. More text.") == 0.5
    assert sentence_fraction(refs, "A fact is here. The second fact matters.") == 1.0
    assert sentence_fraction(refs, "A similar but incomplete fact.") == 0.0


def test_current_policy_scores_summary_above_quote_even_when_both_feasible():
    candidates = [
        {"action": "controlled_quote", "estimated_copyright_cost": .35,
         "residual_copyright_risk": .55, "provenance_required": True},
        {"action": "abstractive_summary", "estimated_copyright_cost": .10,
         "residual_copyright_risk": .22, "provenance_required": True},
    ]
    for risk in (0.0, .5, 1.0):
        selected = select_copyright_candidate(candidates, {
            "copyright_risk_score": risk, "remaining_budget": 1.0,
            "provenance_valid": True,
        })
        by_action = {row["action"]: row for row in selected.evaluated}
        assert by_action["controlled_quote"]["feasible"]
        assert by_action["abstractive_summary"]["feasible"]
        assert selected.action == "abstractive_summary"
        assert by_action["abstractive_summary"]["copyright_score"] > by_action["controlled_quote"]["copyright_score"]
