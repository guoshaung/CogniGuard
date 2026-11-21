from cogniguard.agents.orchestrator import MultiAgentOrchestrator
from cogniguard.agents.research_flow_graph import RESEARCH_FLOW_GRAPH
from experiments.demo_multiagent_system import (
    create_demo_config,
    create_demo_student_profile,
    create_demo_teacher_resources,
)


def test_research_flow_graph_binds_and_verifies_exact_output():
    assert {"select_profile", "control_resources", "audit_answer"} <= set(RESEARCH_FLOW_GRAPH.get_graph().nodes)
    runner = MultiAgentOrchestrator(create_demo_config())
    result = runner.process_query(
        "请帮我解一元二次方程 x²-5x+6=0",
        create_demo_student_profile(),
        create_demo_teacher_resources(),
    )
    assert result["fopd_context"]
    assert len(result["c2rag_context"]) == 3
    assert "画像: 学生擅长" in result["answer"]
    assert runner.verify_answer(result["answer"], result["audit_chain_id"])["valid"]
    assert not runner.verify_answer(result["answer"] + "篡改", result["audit_chain_id"])["valid"]
    assert runner.get_audit_report(result["metadata"]["answer_id"])["total_sources"] == 3
