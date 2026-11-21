import pytest

from experiments.rag_real.reranker_pair_audit import compare_rows


def _row(qid, method, recall10, recall100, hit10):
    return {"query_id": qid, "query_type": "claim", "gold_document_count": 1,
            "method": method, "recall@10": recall10, "recall@100": recall100,
            "mrr@100": recall10, "ndcg@10": recall10,
            "hit@10": hit10, "all_evidence@10": recall10}


def test_pair_audit_counts_lost_hits_without_candidate_drift():
    rows = [
        _row("a", "RRF", 1., 1., 1.),
        _row("a", "RRF+CrossEncoder", 0., 1., 0.),
        _row("b", "RRF", 0., 1., 0.),
        _row("b", "RRF+CrossEncoder", 1., 1., 1.),
    ]
    result = compare_rows(rows)
    assert result["all"]["queries"] == 2
    assert result["all"]["hit10_lost"] == 1
    assert result["all"]["hit10_gained"] == 1
    assert result["all"]["metric_delta"]["recall@10"]["mean"] == 0.


def test_pair_audit_rejects_candidate_set_drift():
    rows = [_row("a", "RRF", 1., 1., 1.),
            _row("a", "RRF+CrossEncoder", 0., 0., 0.)]
    with pytest.raises(ValueError, match="parity"):
        compare_rows(rows)
