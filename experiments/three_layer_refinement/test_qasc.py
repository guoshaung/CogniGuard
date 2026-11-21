from experiments.three_layer_refinement.qasc_retrieval import adapted_corpus


def test_qasc_query_and_corpus_exclude_answer_and_combined_fact_labels():
    row = {"id": "science-1", "question": "What is required for a plant?",
           "fact1": "Plants use sunlight.", "fact2": "Sunlight is a form of energy.",
           "answerKey": "DO_NOT_LEAK_ANSWER", "combinedfact": "DO_NOT_LEAK_CONCLUSION"}
    corpus, queries = adapted_corpus({"train": [], "validation": [row]}, 1)
    assert len(corpus) == 2
    assert queries[0]["text"] == row["question"]
    assert len(queries[0]["gold"]) == 2
    assert "DO_NOT_LEAK" not in str(corpus) and "DO_NOT_LEAK" not in str(queries)


def test_same_global_corpus_for_all_queries_not_per_query_gold_filter():
    rows = [{"id": "q1", "question": "question one", "fact1": "Source fact one.", "fact2": "Source fact two."},
            {"id": "q2", "question": "question two", "fact1": "Source fact three.", "fact2": "Source fact four."}]
    corpus, queries = adapted_corpus({"train": [], "validation": rows}, 2)
    assert len(corpus) == 4 and len(queries) == 2
    assert all(set(q["gold"]) < set(corpus) for q in queries)
