from __future__ import annotations

from pathlib import Path

import scripts.build_episode_dataset as builder


def test_generated_episode_builder_is_idempotent_and_balanced(tmp_path: Path, monkeypatch) -> None:
    first = builder.build_generated_episodes(limit=50)
    second = builder.build_generated_episodes(limit=50)
    assert first == second
    assert len(first) == 50
    assert len({row["episode_id"] for row in first}) == 50
    assert len({row["student_profile_ref"] for row in first}) == 10
    assert len({row["teacher_resource_ref"] for row in first}) == 10
    assert len({row["attack_template_ref"] for row in first}) == 5
    assert {row["pairing_rule"] for row in first} == {"deterministic_stratified_rotation_v2"}
    templates_by_student = {}
    for row in first:
        templates_by_student.setdefault(row["student_profile_ref"], set()).add(
            row["attack_template_ref"]
        )
    assert all(len(template_refs) == 5 for template_refs in templates_by_student.values())

    output_path = tmp_path / "episodes.jsonl"
    monkeypatch.setattr(builder, "OUTPUT_PATH", output_path)
    builder.save_generated_episodes(limit=50)
    first_bytes = output_path.read_bytes()
    builder.save_generated_episodes(limit=50)
    assert output_path.read_bytes() == first_bytes


def test_generated_episode_builder_rejects_negative_limit() -> None:
    try:
        builder.build_generated_episodes(limit=-1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:  # pragma: no cover - assertion aid
        raise AssertionError("negative limit must fail")
