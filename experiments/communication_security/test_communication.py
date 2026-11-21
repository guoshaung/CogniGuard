from pathlib import Path

from cogniguard.workflows.teachers.catalog import PromptLibrary
from experiments.teacher_security.protocol import render
from experiments.teacher_security.tasks import quadratic
from experiments.communication_security.metrics import communication_metrics
from experiments.communication_security.topologies import NAMES, build

ROOT = Path(__file__).resolve().parents[2]


def test_three_topologies_preserve_teacher_prompts_and_root_roles():
    prompts = PromptLibrary(ROOT / "configs/teacher-prompts.yaml")
    for name in NAMES:
        team = build(name, ROOT, prompts)
        team.validate(prompts)
        assert len(team.nodes) == 5 and team.output == "synthesize"
        assert {n.id for n in team.nodes if not team.parents(n.id)} == {"concept", "coach"}
        assert {"relay_a", "relay_b"} <= set(team.order())


def test_propagation_scoring_and_correlated_paths_do_not_read_attack_family():
    task = quadratic("q", 2, -3)
    correct, wrong = {"vertex": [2, -3], "axis": 2}, {"vertex": [99, 99], "axis": 99}
    nodes = [
        {"node": "concept", "message_id": "root", "parent_ids": [], "text": render("q", wrong), "hop": 0, "status": "ok"},
        {"node": "relay_a", "message_id": "a", "parent_ids": ["root"], "text": render("q", wrong), "hop": 1, "status": "ok"},
        {"node": "relay_b", "message_id": "b", "parent_ids": ["root"], "text": render("q", wrong), "hop": 1, "status": "ok"},
        {"node": "synthesize", "message_id": "s", "parent_ids": ["a", "b"], "text": render("q", wrong), "hop": 2, "status": "ok"},
    ]
    report = {"nodes": nodes, "edges": [{"source": "concept", "target": "relay_a", "accepted": True, "origin_valid": True}]}
    metrics = communication_metrics(task, report)
    assert metrics["contaminated_nonroot_nodes"] == 3
    assert metrics["max_contaminated_hop"] == 2
    assert metrics["sink_direct_reports"] == 2 and metrics["sink_distinct_root_messages"] == 1
    assert metrics["correlated_report_excess"] == 1
    assert metrics["delivered_wrong_sender_edges"] == 1

