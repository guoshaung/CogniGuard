from pathlib import Path

from cogniguard.demo.classroom_learning_graph import LEARNING_GRAPH, PHASES
from cogniguard.demo.classroom_session import run_classroom_turn


ROOT = Path(__file__).resolve().parents[3]


def test_learning_turn_executes_all_graph_phases(monkeypatch):
    monkeypatch.setenv("COGNIGUARD_RUNTIME_MODE", "mock")
    monkeypatch.setenv("COGNIGUARD_NEMO_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("MIMO_API_KEY", "")
    monkeypatch.setenv("NARRA_IMAGE_API_KEY", "")
    assert set(PHASES) | {"assemble_result"} <= set(LEARNING_GRAPH.get_graph().nodes)
    result = run_classroom_turn(data_root=ROOT / "data", case_index=0,
                                turn_kind="learning", round_number=1)
    assert result["success"]
    assert result["session_state"]["round_history"]
