from experiments.focused.batch_graph import BATCH_GRAPH, run_graph_batch


def test_focused_batch_runs_each_case_and_serializes_result_callback():
    seen = []
    rows = run_graph_batch(
        list(range(10)), lambda item: {"case": item, "square": item * item},
        workers=3, on_result=lambda row, count: seen.append((count, row["case"])),
    )
    assert sorted(row["case"] for row in rows) == list(range(10))
    assert [count for count, _ in seen] == list(range(1, 11))
    assert {"run_item"} <= set(BATCH_GRAPH.get_graph().nodes)


def test_focused_batch_handles_empty_and_rejects_invalid_parallelism():
    assert run_graph_batch([], lambda item: item, workers=1) == []
    try:
        run_graph_batch([1], lambda item: item, workers=0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid worker count was accepted")
