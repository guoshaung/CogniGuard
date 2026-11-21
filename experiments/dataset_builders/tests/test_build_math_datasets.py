from __future__ import annotations

import hashlib
from pathlib import Path

from protection.common.schemas import ProfileRecord, StudentProfile, TeacherResource
from protection.common.text_utils import read_jsonl

from experiments.dataset_builders.build_math_datasets import (
    ATTACK_PROMPT_VARIANTS,
    GENERATOR_VERSION,
    SCHEMA_VERSION,
    SourceSpec,
    _build_attack_templates,
    _difficulty,
    _sha256_text,
    _stage_metadata,
    _write_pack,
)
from experiments.dataset_builders.validate_math_dataset import validate_pack


def _spec(name: str, stage: str) -> SourceSpec:
    return SourceSpec(
        dataset_name=name,
        stage=stage,
        source_name=f"Fixture-{stage}",
        url=f"https://example.invalid/{name}.jsonl",
        license_name="MIT",
        license_url="https://example.invalid/LICENSE",
        data_format="jsonl",
        sample_size=80,
    )


def _problems(spec: SourceSpec, count: int = 80) -> list[dict]:
    knowledge = (
        "arithmetic_word_problem",
        "linear_equation",
        "geometry_measurement",
        "probability_combinatorics",
    )
    rows = []
    for index in range(1, count + 1):
        question = f"Fixture {spec.stage} problem {index}: compute {index} + {index + 1}."
        answer = str(index * 2 + 1)
        uid = _sha256_text(f"{spec.source_name}|{question}|{answer}|")[:24]
        rows.append(
            {
                "source_dataset": spec.source_name,
                "source_dataset_slug": spec.dataset_name,
                "source_id": f"fixture_{index:04d}",
                "source_task_uid": uid,
                "student_stage": spec.stage,
                "source_url": spec.url,
                "license_name": spec.license_name,
                "license_url": spec.license_url,
                "question": question,
                "answer": answer,
                "rationale": f"Add the two integers for fixture {index}.",
                "knowledge": knowledge[(index - 1) % len(knowledge)],
                "subfield": "",
                "difficulty": _difficulty(spec.stage, index),
                "cognitive_level": _stage_metadata(spec.stage)["cognitive_level"],
            }
        )
    return rows


def _artifact_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_attack_template_matrix_is_complete_and_holdout_disjoint() -> None:
    rows = _build_attack_templates()
    assert len(rows) == len(ATTACK_PROMPT_VARIANTS) * 5 * 3 == 75
    assert {row["strength"] for row in rows} == {"low", "medium", "high"}
    for family in ATTACK_PROMPT_VARIANTS:
        family_rows = [row for row in rows if row["attack_family"] == family]
        assert len({row["phrasing_id"] for row in family_rows}) == 5
        train = {row["phrasing_id"] for row in family_rows if row["split"] == "train"}
        dev = {row["phrasing_id"] for row in family_rows if row["split"] == "dev"}
        test = {row["phrasing_id"] for row in family_rows if row["split"] == "test"}
        assert not (train & dev or train & test or dev & test)


def test_expanded_pack_is_deterministic_valid_and_legacy_compatible(tmp_path: Path) -> None:
    spec = _spec("fixture_junior", "junior")
    problems = _problems(spec)
    first = tmp_path / "first" / spec.dataset_name
    second = tmp_path / "second" / spec.dataset_name
    manifest = _write_pack(first, [spec], problems, stage=spec.stage, seed=2026)
    _write_pack(second, [spec], problems, stage=spec.stage, seed=2026)

    report = validate_pack(first)
    assert report["valid"] is True
    assert report["questions"] == 80
    assert report["profiles"] == 30
    assert report["learning_events"] == 300
    assert report["attack_templates"] == 75
    assert report["episodes"] == 160
    assert report["split_counts"] == {"train": 48, "dev": 16, "test": 16}
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert _artifact_digest(first) == _artifact_digest(second)

    profile_rows = read_jsonl(first / "student_profile" / "data" / "profiles.jsonl")
    resource_rows = read_jsonl(first / "teacher_resource" / "data" / "teacher_resources.jsonl")
    StudentProfile.from_dict(profile_rows[0])
    TeacherResource.from_dict(resource_rows[0])
    for record in profile_rows[0]["profile_records"]:
        ProfileRecord(**record)
    assert profile_rows[0]["generation_provenance"]["generator_version"] == GENERATOR_VERSION


def test_mixed_pack_preserves_component_stage_difficulty_and_assignment(tmp_path: Path) -> None:
    specs = [
        _spec("fixture_junior", "junior"),
        _spec("fixture_high", "high_school"),
        _spec("fixture_college", "college"),
    ]
    groups = {spec.stage: _problems(spec) for spec in specs}
    junior_root = tmp_path / specs[0].dataset_name
    mixed_root = tmp_path / "mixed_math_suite"
    _write_pack(junior_root, [specs[0]], groups["junior"], stage="junior", seed=2026)
    _write_pack(
        mixed_root,
        specs,
        [problem for spec in specs for problem in groups[spec.stage]],
        stage="mixed",
        seed=2026,
    )

    junior_rows = {
        row["source_task_uid"]: row
        for row in read_jsonl(
            junior_root / "student_profile" / "data" / "student_questions.jsonl"
        )
    }
    mixed_rows = {
        row["source_task_uid"]: row
        for row in read_jsonl(
            mixed_root / "student_profile" / "data" / "student_questions.jsonl"
        )
        if row["student_stage"] == "junior"
    }
    assert set(junior_rows) == set(mixed_rows)
    for uid, component in junior_rows.items():
        aggregate = mixed_rows[uid]
        assert aggregate["difficulty"] == component["difficulty"]
        assert aggregate["student_id"] == component["student_id"]
        assert aggregate["split"] == component["split"]
        assert aggregate["target_resource_id"] == component["target_resource_id"]
    assert {row["student_stage"] for row in read_jsonl(
        mixed_root / "student_profile" / "data" / "student_questions.jsonl"
    )} == {"junior", "high_school", "college"}
