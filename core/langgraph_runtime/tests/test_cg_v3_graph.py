from experiments.evaluation.cg_v3_graph import CG_GRAPH, CGContext, CGFrame, PHASES


def phases():
    for name in PHASES:
        yield name
    return {"decision": "allow"}


def test_cg_graph_runs_separate_budget_execution_and_audit_phases():
    assert set(PHASES) | {"finalize"} <= set(CG_GRAPH.get_graph().nodes)
    frame = CGFrame(phases())
    result = CG_GRAPH.invoke({}, context=CGContext(frame))
    assert result["completed"]
    assert frame.result == {"decision": "allow"}
