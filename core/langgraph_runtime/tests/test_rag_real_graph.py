from experiments.rag_real.graph import CONTROL_GRAPH, RETRIEVAL_GRAPH, invoke_batch


def fixture(count):
    yield ("prepare", count)
    for _ in range(count):
        yield "item"
    return {"processed": count}


def test_real_retrieval_and_control_graphs_route_each_item():
    assert {"prepare", "process_item", "finalize"} <= set(RETRIEVAL_GRAPH.get_graph().nodes)
    assert {"prepare", "process_item", "finalize"} <= set(CONTROL_GRAPH.get_graph().nodes)
    assert invoke_batch(RETRIEVAL_GRAPH, fixture(2)) == {"processed": 2}
    assert invoke_batch(CONTROL_GRAPH, fixture(12)) == {"processed": 12}
