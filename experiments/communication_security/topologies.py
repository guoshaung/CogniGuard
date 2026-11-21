"""Same teachers and prompts, different explicit communication edges."""
from dataclasses import replace

from cogniguard.workflows.teachers.catalog import TeamCatalog, TeamSpec, TeacherEdge

NAMES = ("serial_merge", "parallel_merge", "correlated_echo")


def build(name, root, prompts):
    if name not in NAMES:
        raise ValueError("unknown communication topology")
    base = TeamCatalog(root / "configs/teacher-teams.yaml", prompts).get("dual_teachers")
    by_id = {node.id: node for node in base.nodes}
    nodes = (by_id["concept"], by_id["coach"],
             replace(by_id["coach"], id="relay_a"),
             replace(by_id["concept"], id="relay_b"), by_id["synthesize"])
    pairs = {
        "serial_merge": (("concept", "relay_a"), ("coach", "relay_a"),
                         ("relay_a", "relay_b"), ("relay_b", "synthesize")),
        "parallel_merge": (("concept", "relay_a"), ("coach", "relay_b"),
                           ("relay_a", "synthesize"), ("relay_b", "synthesize")),
        "correlated_echo": (("concept", "relay_a"), ("concept", "relay_b"),
                            ("relay_a", "synthesize"), ("relay_b", "synthesize"), ("coach", "synthesize")),
    }[name]
    team = TeamSpec(name, nodes, tuple(TeacherEdge(a, b) for a, b in pairs), "synthesize")
    team.validate(prompts)
    return team
