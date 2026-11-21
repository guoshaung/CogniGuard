from pathlib import Path

from cogniguard.demo.demo_graph import DEMO_GRAPH
from cogniguard.demo.run_demo import run_demo


ROOT = Path(__file__).resolve().parents[3]


def test_dashboard_demo_uses_graph_for_binding_and_compliance(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("MIMO_API_KEY", "")
    assert {"load_case", "protected_agents", "watermark_bind", "compliance", "package_view"} <= set(DEMO_GRAPH.get_graph().nodes)
    result = run_demo(data_root=ROOT / "data", case_index=0)
    assert result["workflow_steps"]
    assert result["final_protected_teaching_answer"]
    assert result["audit_trace"]["audit_complete"]
