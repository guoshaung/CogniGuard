from experiments.c2rag_v3.fact_release import gate_fact, source_quote_matches
from experiments.three_layer_refinement.rag_model import scores


SOURCE = "The observatory opened in 1920 beside a large mountain. " + "People use a telescope to watch the night sky. " * 12


def valid(answer="1920"):
    return {"answer": answer, "abstain": False,
            "evidence": [{"document_id": "d", "quote": "The observatory opened in 1920"}]}


def test_short_facts_and_nonexistent_witnesses():
    ledger = {}
    result = gate_fact(valid(), {"d": SOURCE}, ledger)
    assert result["released"] and result["answer"] == "1920" and ledger["d"] > 0
    fake = valid()
    fake["evidence"][0]["quote"] = "The observatory opened in 1700"
    assert not gate_fact(fake, {"d": SOURCE}, {})["released"]
    assert not gate_fact(valid("1700"), {"d": SOURCE}, {})["released"]


def test_fail_closed_schema_length_and_budget():
    for output in (None, [], {"answer": "1920", "abstain": "false"}, valid(SOURCE)):
        assert not gate_fact(output, {"d": SOURCE}, {})["released"]
    ledger = {"d": .15}
    assert not gate_fact(valid(), {"d": SOURCE}, ledger)["released"]
    assert ledger == {"d": .15}


def test_normalized_answer_scorer():
    assert scores("The Netherlands", "Netherlands")["normalized_answer_em"] == 1
    assert scores("no", "yes")["answer_token_f1"] == 0
    assert scores("", "Netherlands")["answer_token_f1"] == 0


def test_ellipsis_quotes_require_each_span_in_order_in_same_source():
    assert source_quote_matches("The observatory opened ... beside a large mountain", SOURCE)
    assert not source_quote_matches("The observatory opened ... beside a blue ocean", SOURCE)
    assert not source_quote_matches("beside a large mountain ... The observatory opened", SOURCE)
    assert not source_quote_matches("The ... 1920", SOURCE)
