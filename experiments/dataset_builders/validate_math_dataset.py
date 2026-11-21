from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from protection.common.text_utils import read_jsonl

from .build_math_datasets import (
    ATTACK_PROMPT_VARIANTS,
    LONGITUDINAL_EVENTS_PER_STUDENT,
    SCHEMA_VERSION,
    SPLIT_ORDER,
    STAGE_METADATA,
)


class DatasetValidationError(AssertionError):
    """Raised when a generated benchmark violates a declared invariant."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetValidationError(message)


def _unique(rows: Iterable[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key, ""))
        _require(bool(value), f"{label} has an empty {key}")
        _require(value not in result, f"Duplicate {label} {key}: {value}")
        result[value] = row
    return result


def _load_pack(pack_root: Path) -> dict[str, list[dict[str, Any]]]:
    paths = {
        "questions": pack_root / "student_profile" / "data" / "student_questions.jsonl",
        "profiles": pack_root / "student_profile" / "data" / "profiles.jsonl",
        "events": pack_root / "student_profile" / "data" / "learning_events.jsonl",
        "resources": pack_root / "teacher_resource" / "data" / "teacher_resources.jsonl",
        "templates": pack_root / "evaluation" / "data" / "attack_templates.jsonl",
        "episodes": pack_root / "evaluation" / "data" / "episodes.jsonl",
    }
    for label, path in paths.items():
        _require(path.exists(), f"Missing {label} file: {path}")
    return {label: read_jsonl(path) for label, path in paths.items()}


def _assert_split_disjoint(rows: list[dict[str, Any]], key: str, label: str) -> None:
    split_values = {
        split: {str(row[key]) for row in rows if row.get("split") == split}
        for split in SPLIT_ORDER
    }
    for index, left in enumerate(SPLIT_ORDER):
        for right in SPLIT_ORDER[index + 1 :]:
            overlap = split_values[left] & split_values[right]
            _require(not overlap, f"{label} leaks across {left}/{right}: {sorted(overlap)[:3]}")


def validate_pack(pack_root: str | Path) -> dict[str, Any]:
    pack_root = Path(pack_root)
    data = _load_pack(pack_root)
    questions = data["questions"]
    profiles = data["profiles"]
    events = data["events"]
    resources = data["resources"]
    templates = data["templates"]
    episodes = data["episodes"]

    _require(bool(questions), f"No questions in {pack_root}")
    question_by_id = _unique(questions, "request_id", "question")
    profile_by_id = _unique(profiles, "student_id", "profile")
    resource_by_id = _unique(resources, "resource_id", "resource")
    _unique(events, "event_id", "event")
    _unique(templates, "attack_template_id", "attack template")
    _unique(episodes, "episode_id", "episode")

    expected_record_keys = {
        "record_id",
        "type",
        "knowledge",
        "value",
        "confidence",
        "sensitivity",
        "updated_at",
    }
    profile_split: dict[str, str] = {}
    profile_stage: dict[str, str] = {}
    for profile in profiles:
        _require(profile.get("schema_version") == SCHEMA_VERSION, "Profile schema version mismatch")
        student_id = str(profile["student_id"])
        split = str(profile.get("split"))
        stage = str(profile.get("student_context", {}).get("stage"))
        _require(split in SPLIT_ORDER, f"Invalid profile split for {student_id}: {split}")
        _require(stage in STAGE_METADATA, f"Invalid stage for {student_id}: {stage}")
        context = profile["student_context"]
        _require(
            context.get("grade_band") == STAGE_METADATA[stage]["grade_band"],
            f"Grade band/stage mismatch for {student_id}",
        )
        _require(profile.get("synthetic") is True, f"Profile {student_id} is not marked synthetic")
        _require(
            profile.get("learning_event_count") == LONGITUDINAL_EVENTS_PER_STUDENT,
            f"Unexpected event count declaration for {student_id}",
        )
        multimodal = profile.get("multimodal_profile", {})
        _require(multimodal.get("image", {}).get("raw_images_retained") is False, student_id)
        _require(multimodal.get("audio", {}).get("raw_audio_retained") is False, student_id)
        _require(multimodal.get("audio", {}).get("voiceprint_stored") is False, student_id)
        _require(multimodal.get("video", {}).get("raw_video_retained") is False, student_id)
        _require(multimodal.get("video", {}).get("biometric_template_stored") is False, student_id)
        boundary = profile.get("representation_boundary", {})
        _require("z_S" in boundary.get("local_only", []), f"z_S is not local-only for {student_id}")
        records = profile.get("profile_records", [])
        _require(bool(records), f"Profile {student_id} has no runtime records")
        for record in records:
            _require(
                set(record) == expected_record_keys,
                f"ProfileRecord compatibility shape changed for {student_id}/{record.get('record_id')}",
            )
            _require(0.0 <= float(record["confidence"]) <= 1.0, "Record confidence out of range")
            _require(0.0 <= float(record["sensitivity"]) <= 1.0, "Record sensitivity out of range")
        record_types = {str(record["type"]) for record in records}
        _require(
            {"mastery", "error_pattern", "preference", "learning_state", "behavior_aggregate"}
            <= record_types,
            f"Profile {student_id} does not expose expanded runtime records",
        )
        profile_split[student_id] = split
        profile_stage[student_id] = stage

    seen_source_uids: set[str] = set()
    for question in questions:
        request_id = str(question["request_id"])
        student_id = str(question["student_id"])
        resource_id = str(question["target_resource_id"])
        source_resource_id = str(question.get("source_resource_id", ""))
        split = str(question.get("split"))
        stage = str(question.get("student_stage"))
        source_uid = str(question.get("source_task_uid"))
        _require(question.get("schema_version") == SCHEMA_VERSION, f"Question schema: {request_id}")
        _require(student_id in profile_by_id, f"Unknown student in {request_id}: {student_id}")
        _require(resource_id in resource_by_id, f"Unknown resource in {request_id}: {resource_id}")
        _require(
            source_resource_id in resource_by_id,
            f"Unknown open source resource in {request_id}: {source_resource_id}",
        )
        target_resource = resource_by_id[resource_id]
        source_resource = resource_by_id[source_resource_id]
        _require(
            target_resource.get("access_policy", {}).get("access_sensitivity")
            == "L3_simulated_restricted",
            f"Task {request_id} is not paired to a restricted synthetic teacher resource",
        )
        _require(
            target_resource.get("rights_metadata", {}).get("synthetic_flag") is True,
            f"Restricted target is not synthetic in {request_id}",
        )
        _require(
            source_resource.get("access_policy", {}).get("access_sensitivity")
            == "L1_open_with_conditions",
            f"Source resource is not labeled open in {request_id}",
        )
        _require(profile_split[student_id] == split, f"Student split mismatch in {request_id}")
        _require(profile_stage[student_id] == stage, f"Student stage mismatch in {request_id}")
        _require(source_uid not in seen_source_uids, f"Duplicate source task: {source_uid}")
        seen_source_uids.add(source_uid)

    for resource in resources:
        resource_id = str(resource["resource_id"])
        rights = resource.get("rights_metadata", {})
        access = resource.get("access_policy", {})
        provenance = resource.get("provenance", {})
        _require(resource.get("schema_version") == SCHEMA_VERSION, f"Resource schema: {resource_id}")
        for field in (
            "rights_status",
            "license_id",
            "source_url",
            "rights_holder",
            "derivative_allowed",
            "commercial_use_allowed",
            "ai_use_status",
            "synthetic_flag",
            "simulated_policy",
        ):
            _require(field in rights, f"Resource {resource_id} missing rights_metadata.{field}")
        _require(bool(access.get("access_sensitivity")), f"Resource {resource_id} has no sensitivity")
        _require(bool(access.get("allowed_roles")), f"Resource {resource_id} has no allowed roles")
        _require(len(str(provenance.get("content_hash", ""))) == 64, f"Bad content hash: {resource_id}")
        if rights.get("rights_status") == "open_license":
            _require(
                access.get("access_sensitivity") == "L1_open_with_conditions",
                f"Open resource {resource_id} mislabeled as private",
            )
            _require(float(resource.get("copyright_level", 1.0)) <= 0.35, resource_id)
            _require(resource.get("policy", {}).get("allow_quote") is True, resource_id)
        if access.get("access_sensitivity") == "L3_simulated_restricted":
            _require(rights.get("synthetic_flag") is True, f"L3 resource must be synthetic: {resource_id}")
            _require(float(resource.get("copyright_level", 0.0)) >= 0.70, resource_id)

    content_hash_splits: dict[str, set[str]] = defaultdict(set)
    for resource in resources:
        content_hash_splits[str(resource["provenance"]["content_hash"])].add(
            str(resource["split"])
        )
    cross_split_hashes = [
        content_hash for content_hash, splits in content_hash_splits.items() if len(splits) > 1
    ]
    _require(
        not cross_split_hashes,
        f"Identical resource content crosses splits: {cross_split_hashes[:3]}",
    )

    events_by_student: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        student_id = str(event["student_id"])
        request_id = str(event["task_ref"])
        _require(student_id in profile_by_id, f"Unknown event student: {student_id}")
        _require(request_id in question_by_id, f"Unknown event task: {request_id}")
        _require(event.get("split") == profile_split[student_id], f"Event split mismatch: {event['event_id']}")
        _require(
            event.get("split") == question_by_id[request_id].get("split"),
            f"Event/task split mismatch: {event['event_id']}",
        )
        _require(event.get("raw_multimodal_data_present") is False, f"Raw modality in {event['event_id']}")
        for field in ("mastery_before", "mastery_after", "update_confidence"):
            _require(0.0 <= float(event[field]) <= 1.0, f"{field} out of range: {event['event_id']}")
        events_by_student[student_id].append(event)
    for student_id, student_events in events_by_student.items():
        _require(
            len(student_events) == LONGITUDINAL_EVENTS_PER_STUDENT,
            f"Student {student_id} has {len(student_events)} events",
        )
        ordered = sorted(student_events, key=lambda row: int(row["event_index"]))
        timestamps = [str(row["timestamp"]) for row in ordered]
        _require(timestamps == sorted(timestamps), f"Events are not chronological for {student_id}")
        probes = [row for row in ordered if row["ground_truth_label"] == "synthetic_poisoning_probe"]
        _require(len(probes) == 1, f"Student {student_id} must have one poisoning probe")
        _require(probes[0]["accepted_for_profile_update"] is False, f"Probe accepted for {student_id}")
    _require(set(events_by_student) == set(profile_by_id), "Some profiles have no longitudinal events")

    family_count = len(ATTACK_PROMPT_VARIANTS)
    _require(len(templates) == family_count * 5 * 3, "Attack template matrix is incomplete")
    coverage: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for template in templates:
        family = str(template["attack_family"])
        coverage[family]["phrasing"].add(str(template["phrasing_id"]))
        coverage[family]["strength"].add(str(template["strength"]))
    for family in ATTACK_PROMPT_VARIANTS:
        _require(len(coverage[family]["phrasing"]) == 5, f"Missing phrasings for {family}")
        _require(coverage[family]["strength"] == {"low", "medium", "high"}, family)
        family_rows = [row for row in templates if row["attack_family"] == family]
        for phrasing_id in {str(row["phrasing_id"]) for row in family_rows}:
            prompts = {
                str(row["prompt_template"])
                for row in family_rows
                if str(row["phrasing_id"]) == phrasing_id
            }
            _require(len(prompts) == 3, f"Attack strength is label-only for {phrasing_id}")

    episodes_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        _require(str(episode["request_id"]) in question_by_id, f"Unknown episode task: {episode['episode_id']}")
        _require(
            resource_by_id[str(episode["resource_id"])]
            .get("access_policy", {})
            .get("access_sensitivity")
            == "L3_simulated_restricted",
            f"Episode does not target a restricted resource: {episode['episode_id']}",
        )
        episodes_by_pair[str(episode["pair_id"])].append(episode)
    _require(len(episodes_by_pair) == len(questions), "Each task must have one clean/attack pair")
    shared_pair_fields = (
        "split",
        "student_id",
        "request_id",
        "source_task_uid",
        "resource_id",
        "student_profile_ref",
        "student_question_ref",
        "teacher_resource_ref",
        "pairing_rule",
        "seed",
    )
    for pair_id, pair_rows in episodes_by_pair.items():
        _require(len(pair_rows) == 2, f"Pair {pair_id} does not contain two episodes")
        by_condition = {str(row["condition"]): row for row in pair_rows}
        _require(set(by_condition) == {"clean", "attack"}, f"Pair conditions invalid: {pair_id}")
        for field in shared_pair_fields:
            _require(
                by_condition["clean"].get(field) == by_condition["attack"].get(field),
                f"Pair {pair_id} differs on {field}",
            )

    _assert_split_disjoint(profiles, "student_id", "students")
    _assert_split_disjoint(questions, "source_task_uid", "source tasks")
    _assert_split_disjoint(resources, "resource_id", "resources")
    _assert_split_disjoint(resources, "resource_family_id", "resource families")
    _assert_split_disjoint(templates, "phrasing_id", "attack phrasings")

    for split in SPLIT_ORDER:
        split_root = pack_root / "splits" / split
        _require(split_root.exists(), f"Missing direct split view: {split_root}")
        split_questions = read_jsonl(
            split_root / "student_profile" / "data" / "student_questions.jsonl"
        )
        _require(
            {row["request_id"] for row in split_questions}
            == {row["request_id"] for row in questions if row["split"] == split},
            f"Split view does not match full pack for {split}",
        )

    return {
        "dataset": pack_root.name,
        "questions": len(questions),
        "profiles": len(profiles),
        "learning_events": len(events),
        "resources": len(resources),
        "attack_templates": len(templates),
        "episodes": len(episodes),
        "stage_counts": dict(Counter(str(row["student_stage"]) for row in questions)),
        "split_counts": dict(Counter(str(row["split"]) for row in questions)),
        "valid": True,
    }


def validate_suite(suite_root: str | Path) -> dict[str, Any]:
    suite_root = Path(suite_root)
    manifest_path = suite_root / "manifest.json"
    _require(manifest_path.exists(), f"Missing suite manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("schema_version") == SCHEMA_VERSION, "Suite schema version mismatch")
    dataset_names = [str(row["dataset"]) for row in manifest.get("datasets", [])]
    _require("mixed_math_suite" in dataset_names, "Missing aggregate mixed_math_suite")
    reports = {name: validate_pack(suite_root / name) for name in dataset_names}

    component_names = [name for name in dataset_names if name != "mixed_math_suite"]
    component_questions: dict[str, dict[str, Any]] = {}
    for name in component_names:
        for row in _load_pack(suite_root / name)["questions"]:
            component_questions[str(row["source_task_uid"])] = row
    mixed_questions = {
        str(row["source_task_uid"]): row
        for row in _load_pack(suite_root / "mixed_math_suite")["questions"]
    }
    _require(set(component_questions) == set(mixed_questions), "Mixed task set is not component union")
    invariant_fields = (
        "request_id",
        "student_id",
        "student_stage",
        "grade_band",
        "difficulty",
        "split",
        "source_resource_id",
        "target_resource_id",
    )
    for source_uid, component in component_questions.items():
        mixed = mixed_questions[source_uid]
        for field in invariant_fields:
            _require(
                component.get(field) == mixed.get(field),
                f"Mixed regeneration changed {source_uid}.{field}",
            )
    _require(
        int(manifest.get("independent_task_count", -1)) == len(component_questions),
        "Manifest independent task count is wrong",
    )
    return {
        "suite": suite_root.name,
        "independent_task_count": len(component_questions),
        "packs": reports,
        "valid": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CogniGuard math dataset v2 invariants.")
    parser.add_argument("suite_root", type=Path)
    args = parser.parse_args()
    report = validate_suite(args.suite_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
