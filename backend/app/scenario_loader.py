from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = PROJECT_ROOT / "data" / "scenario_layers"


class ScenarioDataError(RuntimeError):
    """Raised when scenario-layer data is missing or malformed."""


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    manifest_path = SCENARIO_ROOT / "manifest.json"
    if not manifest_path.exists():
        raise ScenarioDataError(f"Missing scenario manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_jsonl_group(group_name: str) -> list[dict[str, Any]]:
    manifest = load_manifest()
    layers = manifest.get("layers", {})
    relative_path = layers.get(group_name)
    if not relative_path:
        raise ScenarioDataError(f"Unknown scenario group: {group_name}")

    file_paths = [PROJECT_ROOT / relative_path]
    if group_name == "scenario_orchestration":
        generated_path = SCENARIO_ROOT / "scenario_orchestration" / "episode_eval_samples_generated.jsonl"
        if generated_path.exists():
            file_paths.append(generated_path)

    rows: list[dict[str, Any]] = []
    for file_path in file_paths:
        if not file_path.exists():
            raise ScenarioDataError(f"Missing scenario file for {group_name}: {file_path}")
        with file_path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ScenarioDataError(
                        f"Invalid JSONL in {file_path} line {line_number}: {exc}"
                    ) from exc
    return rows


ID_FIELDS = {
    "scenario_orchestration": "episode_id",
    "attack_templates": "attack_template_id",
    "synthetic_profiles": "student_id",
    "teacher_resources": "resource_id",
}


def get_row_by_id(group_name: str, row_id: str) -> dict[str, Any]:
    id_field = ID_FIELDS[group_name]
    for row in load_jsonl_group(group_name):
        if str(row.get(id_field)) == str(row_id):
            return row
    raise ScenarioDataError(f"{group_name} row not found: {row_id}")


def list_episode_samples() -> list[dict[str, Any]]:
    return load_jsonl_group("scenario_orchestration")


def get_episode_sample(episode_id: str) -> dict[str, Any]:
    return get_row_by_id("scenario_orchestration", episode_id)


def list_attack_templates() -> list[dict[str, Any]]:
    return load_jsonl_group("attack_templates")


def get_attack_template(attack_template_id: str) -> dict[str, Any]:
    return get_row_by_id("attack_templates", attack_template_id)


def list_synthetic_profiles() -> list[dict[str, Any]]:
    return load_jsonl_group("synthetic_profiles")


def get_synthetic_profile(student_id: str) -> dict[str, Any]:
    return get_row_by_id("synthetic_profiles", student_id)


def list_teacher_resources() -> list[dict[str, Any]]:
    return load_jsonl_group("teacher_resources")


def get_teacher_resource(resource_id: str) -> dict[str, Any]:
    return get_row_by_id("teacher_resources", resource_id)


def resolve_reference(reference: str) -> dict[str, Any]:
    try:
        relative_path, anchor = reference.split("#", 1)
    except ValueError as exc:
        raise ScenarioDataError(f"Invalid scenario reference: {reference}") from exc

    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("synthetic_profiles/"):
        return get_synthetic_profile(anchor)
    if normalized.startswith("teacher_resources/"):
        return get_teacher_resource(anchor)
    if normalized.startswith("attack_templates/"):
        return get_attack_template(anchor)

    raise ScenarioDataError(f"Unsupported scenario reference: {reference}")


def build_episode_bundle(episode_id: str) -> dict[str, Any]:
    episode = get_episode_sample(episode_id)
    profile = resolve_reference(episode["student_profile_ref"])
    resource = resolve_reference(episode["teacher_resource_ref"])
    attack_template = resolve_reference(episode["attack_template_ref"])
    return {
        "episode": episode,
        "student_profile": profile,
        "teacher_resource": resource,
        "attack_template": attack_template,
    }


def build_cases_manifest() -> dict[str, Any]:
    rows = []
    for episode in list_episode_samples():
        profile = resolve_reference(episode["student_profile_ref"])
        resource = resolve_reference(episode["teacher_resource_ref"])
        attack_template = resolve_reference(episode["attack_template_ref"])
        knowledge_points = profile.get("context_card", {}).get("knowledge_points", [])
        rows.append(
            {
                "episode_id": episode["episode_id"],
                "scenario_type": episode.get("scenario_type"),
                "student_id": profile.get("student_id"),
                "student_level": profile.get("context_card", {}).get("student_level"),
                "knowledge_points": knowledge_points,
                "knowledge_point": " / ".join(knowledge_points),
                "risk_level": profile.get("context_card", {}).get("risk_level"),
                "resource_id": resource.get("resource_id"),
                "resource_return_mode": resource.get("return_mode"),
                "attack_template_id": attack_template.get("attack_template_id"),
                "attack_type": attack_template.get("attack_type"),
                "evaluation_targets": episode.get("evaluation_targets", []),
            }
        )
    return {"preferred_layout": "scenario_layers", "rows": rows}
