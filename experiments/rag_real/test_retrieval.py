import json

from experiments.rag_real.retrieval import retrieval_metrics, rrf_rank, select_hotpot


def test_two_evidence_documents_are_not_scored_as_one_hit():
    m = retrieval_metrics(["a", "other", "x"], {"a": 1, "b": 1})
    assert m["hit@3"] == 1.0
    assert m["recall@3"] == .5
    assert m["all_evidence@3"] == 0.0
    assert m["mrr@100"] == 1.0
    assert retrieval_metrics(["other", "b", "a"], {"a": 1, "b": 1})["all_evidence@3"] == 1.0


def test_hotpot_sampling_does_not_depend_on_answer_or_gold(tmp_path):
    base = {"id": "", "question": "Which city?", "answer": "secret", "type": "bridge",
            "context": [["A", ["one sentence."]], ["B", ["another sentence."]]],
            "supporting_facts": [["A", 0], ["B", 0]]}
    rows = [{**base, "id": str(i)} for i in range(6)]
    path = tmp_path / "hotpot-validation.json"
    path.write_text(json.dumps(rows))
    corpus, questions = select_hotpot(tmp_path, 3)
    chosen = [item["id"] for item in questions]
    assert len(corpus) == 2 and all(len(q["gold"]) == 2 for q in questions)
    path.write_text(json.dumps([{**r, "answer": "changed", "supporting_facts": [["A", 0]]} for r in rows]))
    assert [item["id"] for item in select_hotpot(tmp_path, 3)[1]] == chosen


def test_rrf_deduplicates_and_uses_locked_document_tie_break():
    from types import SimpleNamespace
    chunks = [SimpleNamespace(chunk_id="z"), SimpleNamespace(chunk_id="a")]
    assert rrf_rank([0, 1], [1, 0], chunks) == [1, 0]
