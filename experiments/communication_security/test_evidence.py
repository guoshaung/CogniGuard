import copy
from pathlib import Path

from cogniguard.workflows.teachers.catalog import PromptLibrary
from cogniguard.workflows.teachers.skills import SkillLibrary
from experiments.communication_security.evidence_protocol import EvidenceAssessor, parse, render
from experiments.communication_security.evidence_runner import payloads, case_plan, team

ROOT = Path(__file__).resolve().parents[2]


def sample():
    return {"id": "q1", "question": "What do plants use?", "choices": [("A", "sunlight"), ("B", "salt")],
            "fact1": "Plants use sunlight for photosynthesis.", "fact2": "Sunlight is a source of energy.", "answerKey": "A"}


def test_guard_has_no_gold_parameter_and_rejects_forged_source_quote():
    row = sample()
    guard = EvidenceAssessor(row["id"], {"R1": row["fact1"], "R2": row["fact2"]}, ["A", "B"])
    clean, _ = payloads(row, "clean")
    attack, _ = payloads(row, "forged_quote")
    assert guard(clean["source_a"], row["question"], "handoff").allow
    assert not guard(attack["source_a"], row["question"], "handoff").allow
    # Source-bound B is allowed even if the scorer's gold happens to be A:
    # citation presence is intentionally not an entailment oracle.
    report = parse(clean["source_a"])
    report["choice"] = "B"
    assert guard(render(row["id"], report["evidence"], choice="B"), "", "final").allow


def test_attack_assembly_does_not_choose_target_from_answer_key():
    row = sample()
    changed = copy.deepcopy(row)
    changed["answerKey"] = "B"
    assert payloads(row, "collusive_quote") == payloads(changed, "collusive_quote")
    assert payloads(row, "forged_quote")[1] == "A"


def test_actual_tool_scope_is_separate_from_source_citation_matching():
    row = sample()
    guard = EvidenceAssessor(row["id"], {"R1": row["fact1"], "R2": row["fact2"]}, ["A", "B"])
    attack, _ = payloads(row, "tool_scope")
    assessment = guard(attack["source_a"], "", "handoff")
    assert not assessment.allow and "tool_scope_denied" in assessment.reasons
    final_only = EvidenceAssessor(row["id"], guard.references, ["A", "B"], handoff=False)
    assert final_only(attack["source_a"], "", "handoff").allow
    assert not final_only(attack["source_a"], "", "final").allow


def test_each_science_task_has_a_matched_clean_control():
    rows = [dict(sample(), id=f"q{i}") for i in range(3)]
    cases = case_plan(rows)
    assert len(cases) == 6
    for row in rows:
        matched = [family for item, family in cases if item["id"] == row["id"]]
        assert len(matched) == 2 and matched[0].startswith("clean")


def test_science_models_never_receive_canonical_source_field():
    prompts = PromptLibrary(ROOT / "configs/qasc-communication-prompts.yaml")
    skills = SkillLibrary(ROOT / "configs/qasc-communication-skills.yaml")
    t = team()
    t.validate(prompts)
    for node in t.nodes:
        skills.get(node.teacher)
        if node.backend != "sources":
            assert "resource_text" not in node.view_fields and not node.requires_all_inputs
