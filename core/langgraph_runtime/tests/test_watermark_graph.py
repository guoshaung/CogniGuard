from protection.audit_trace.src.watermark_graph import (
    WATERMARK_GRAPH,
    WatermarkContext,
    WatermarkFrame,
)


def _staged_fixture():
    yield ("prepare", 2)
    for _ in range(2):
        yield "rewrite"
        yield "detect"
        yield "audit"
        yield "attack"
    yield "clean_eval"
    return "done"


def test_watermark_graph_has_per_sample_rewrite_detection_and_audit():
    assert {"rewrite", "detect", "audit", "attack", "clean_eval"} <= set(WATERMARK_GRAPH.get_graph().nodes)
    frame = WatermarkFrame(_staged_fixture())
    state = WATERMARK_GRAPH.invoke({}, context=WatermarkContext(frame),
                                   config={"recursion_limit": 100})
    assert state["completed"]
    assert state["sample_index"] == 2
    assert frame.result == "done"
