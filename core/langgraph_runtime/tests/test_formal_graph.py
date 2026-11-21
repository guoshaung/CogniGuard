from pathlib import Path

from experiments.formal_v2.graph import FORMAL_GRAPH
from experiments.formal_v2.run_formal import run


ROOT = Path(__file__).resolve().parents[3]


def test_formal_graph_runs_one_case_without_hidden_labels(tmp_path):
    assert {"load_cases", "evaluate_job", "aggregate", "statistics", "persist"} <= set(FORMAL_GRAPH.get_graph().nodes)
    manifest = run(
        ROOT / "experiments/datasets/cogniguard_math_suite/mixed_math_suite/splits/test",
        tmp_path / "formal",
        [20260826],
        case_limit=1,
    )
    assert manifest["orchestrator"] == "langgraph"
    assert manifest["case_count"] == 1
    assert manifest["row_count"] == 20
    assert manifest["hidden_labels_passed_to_methods"] is False
