from dataclasses import replace

from experiments.c2rag_v3.core import Chunk, C2RAGConfig, C2RAGV3, ResourceDocument, disclosure_measurement
from experiments.c2rag_v3.evidence_release import measured_cost, plan_excerpt
from experiments.three_layer_refinement.rag import answer_available


def resource(license="CC-BY-SA-4.0"):
    text = "A telescope studies distant stars and their light. " * 12 + "The observatory opened in 1920 beside a large mountain."
    return ResourceDocument("d", "d", "body", text, "Observatory", "test", license, .85,
                            ("teacher",), ("tutoring",), "hash", "family", "Observatory", ())


def test_measured_plan_fits_budget_and_is_real_source_excerpt():
    doc = resource()
    engine = C2RAGV3([doc], C2RAGConfig())
    chunk = replace(engine.chunks[0], text=doc.text)
    plan = plan_excerpt("When did the observatory open?", chunk, .15)
    assert plan["action"] == "controlled_quote"
    assert plan["content"] in chunk.text
    actual = measured_cost(disclosure_measurement("教学回答：引用摘录：" + plan["content"], chunk.text, (), 5))
    assert actual <= .15 and actual == plan["estimated_copyright_cost"]
    assert plan_excerpt("observatory", chunk, 0)["action"] == "refuse"
    short = replace(chunk, text="The observatory opened in 1920 beside a large mountain.")
    assert plan_excerpt("observatory", short, .15)["action"] == "refuse"


def test_new_mode_cannot_bypass_authorization_or_cumulative_budget():
    cfg = C2RAGConfig(evidence_renderer="query_bounded", total_copyright_budget=.15)
    engine = C2RAGV3([resource()], cfg)
    for turn in range(1, 5):
        result = engine.run_round(session_id="s", round_id=turn, identity="u", query="Explain stars and their light")
        assert result.session_cost_after <= .15 + 1e-9
    invalid = C2RAGV3([resource("unverified")], cfg)
    result = invalid.run_round(session_id="s", round_id=1, identity="u", query="Explain stars")
    assert result.refusal


def test_answer_availability_is_not_boolean_qa_scoring():
    assert answer_available("yes", "yes indeed") is None
    assert answer_available("1920", "It opened in 1920.") == 1
    assert answer_available("1920", "The number is 19201.") == 0
