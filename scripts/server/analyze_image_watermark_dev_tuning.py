"""Analyze one completed image-watermark development run without model access.

This command is deliberately offline.  It reads only artifacts below a supplied
``RUN`` directory, reconstructs the development codebook from the authenticated
run-local registry snapshot plus embed payload artifacts, validates every
recorded bit accuracy, and simulates one closed-set registry lookup per
recovered raw word for radii zero through five.  Legacy test fixtures without a
registry snapshot retain the older exact-match reference fallback.

The resulting JSON is a development diagnostic, never a paper result.  In
particular, codebook distance and lookup outcomes must be recomputed after the
formal 3000-image registry has been built.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


RESULT_CLASS = "development_only_not_paper_result"
SOURCE_RUN_CLASS = "dev_tuning"
SCHEMA_VERSION = "cogniguard_image_watermark_dev_analysis_v1"
MESSAGE_BITS = 64
RADII = tuple(range(6))
DEFAULT_EXPECTED_SAMPLES = 117
JOB_ID_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")

MASK_METRICS = (
    "predicted_mask_area_ratio",
    "mask_iou",
    "mask_dice",
    "mask_precision",
    "mask_recall",
    "mask_fpr",
    "image_tamper_detected",
)
QUALITY_METRICS = (
    "watermark_psnr",
    "watermark_ssim",
    "watermark_lpips",
    "watermark_normalized_mae",
)


class DevAnalysisError(RuntimeError):
    """Raised when a development run cannot be analyzed reproducibly."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a completed development-only image-watermark run."
    )
    parser.add_argument("--run", required=True, help="Development RUN directory.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON (default: RUN/development_only_analysis.json).",
    )
    parser.add_argument(
        "--expected-samples",
        type=int,
        default=DEFAULT_EXPECTED_SAMPLES,
        help="Exact expected development sample count.",
    )
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevAnalysisError(f"Cannot read {label} at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DevAnalysisError(f"{label} must be a JSON object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DevAnalysisError(
                        f"Invalid JSON on raw_results line {line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise DevAnalysisError(
                        f"raw_results line {line_number} is not a JSON object."
                    )
                rows.append(payload)
    except OSError as exc:
        raise DevAnalysisError(f"Cannot read raw results at {path}: {exc}") from exc
    if not rows:
        raise DevAnalysisError(f"Raw results are empty: {path}")
    return rows


def _is_below(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative_path(path: Path, run_dir: Path) -> str:
    try:
        return path.relative_to(run_dir).as_posix()
    except ValueError as exc:
        raise DevAnalysisError(f"Artifact escapes the RUN directory: {path}") from exc


def _binary_word(value: Any, label: str) -> str:
    bits = str(value or "")
    if len(bits) != MESSAGE_BITS or any(bit not in {"0", "1"} for bit in bits):
        raise DevAnalysisError(f"{label} must contain exactly 64 binary digits.")
    return bits


def hamming_distance(left: str, right: str) -> int:
    left = _binary_word(left, "left codeword")
    right = _binary_word(right, "right codeword")
    return (int(left, 2) ^ int(right, 2)).bit_count()


def _strict_bool(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    raise DevAnalysisError(f"{label} must be boolean or numeric 0/1, got {value!r}.")


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise DevAnalysisError(f"{label} must be numeric, got boolean {value!r}.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DevAnalysisError(f"{label} must be numeric, got {value!r}.") from exc
    if not math.isfinite(result):
        raise DevAnalysisError(f"{label} must be finite, got {value!r}.")
    return result


def _condition_component(value: Any) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise DevAnalysisError("Attack parameters must be finite.")
        rendered = format(value, ".12g")
    elif value is None:
        rendered = "null"
    elif isinstance(value, str):
        rendered = value.strip().lower()
    else:
        canonical = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        rendered = f"sha256-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:12]}"
    rendered = re.sub(r"[^a-zA-Z0-9.+-]+", "-", rendered).strip("-")
    return rendered or "empty"


def canonical_condition(row: dict[str, Any]) -> str:
    """Return a stable condition label derived from attack name and parameters."""

    attack_id = str(row.get("attack_id") or "").strip()
    attack_name = str(row.get("attack_name") or "").strip().lower()
    if not attack_name:
        attack_name = attack_id.split("__", 1)[0].lower()
    attack_name = re.sub(r"[^a-z0-9.+-]+", "_", attack_name).strip("_")
    if not attack_name:
        raise DevAnalysisError("Every row must define attack_name or attack_id.")
    params = row.get("attack_params") or {}
    if not isinstance(params, dict):
        raise DevAnalysisError(f"attack_params must be an object for {attack_id!r}.")
    if attack_name == "clean" and not params:
        return "clean"
    parts = [attack_name]
    for key in sorted(params):
        normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
        if not normalized_key:
            raise DevAnalysisError(f"Invalid attack parameter key: {key!r}")
        parts.extend((normalized_key, _condition_component(params[key])))
    return "_".join(parts)


def _resolve_verify_report(
    run_dir: Path, index_path: Path, index_payload: dict[str, Any], job_id: str
) -> Path:
    if index_payload.get("job_id") != job_id:
        raise DevAnalysisError(f"Index job_id mismatch for {index_path}.")
    if index_payload.get("job_type") != "verify":
        raise DevAnalysisError(f"Index is not a verify job: {index_path}")
    raw_pointer = str(index_payload.get("report_json_path") or "").strip()
    if not raw_pointer:
        raise DevAnalysisError(f"Index has no report_json_path: {index_path}")
    pointer = Path(os.path.expandvars(raw_pointer)).expanduser()
    if not pointer.is_absolute():
        pointer = index_path.parent / pointer
    report_path = pointer.resolve()
    if not _is_below(report_path, run_dir):
        raise DevAnalysisError(
            f"Verify-report pointer escapes the RUN directory: {report_path}"
        )
    if report_path.name != "verify_report.json" or not report_path.is_file():
        raise DevAnalysisError(f"Verify report is missing or misnamed: {report_path}")
    return report_path


def _raw_word(report: dict[str, Any], response: dict[str, Any], job_id: str) -> str:
    candidates = [
        value
        for value in (
            report.get("recovered_bits"),
            response.get("recovered_capsule_bits"),
        )
        if value not in {None, ""}
    ]
    if not candidates:
        raise DevAnalysisError(f"Verify report {job_id} contains no recovered raw word.")
    words = {_binary_word(value, f"raw word for {job_id}") for value in candidates}
    if len(words) != 1:
        raise DevAnalysisError(
            f"Verify report {job_id} has conflicting recovered-bit fields."
        )
    return words.pop()


def _validate_reported_registry_fields(
    row: dict[str, Any], response: dict[str, Any], *, job_id: str
) -> dict[str, bool]:
    reported: dict[str, bool] = {}
    for field in (
        "exact_registry_match",
        "source_registry_match",
        "correction_applied",
    ):
        row_value = _strict_bool(row.get(field), f"raw row {job_id}.{field}")
        response_value = _strict_bool(
            response.get(field), f"verify response {job_id}.{field}"
        )
        if row_value != response_value:
            raise DevAnalysisError(
                f"Raw/report mismatch for {job_id}.{field}: "
                f"{row_value!r} != {response_value!r}."
            )
        reported[field] = row_value
    corrected = _strict_bool(
        row.get("registry_corrected_match"),
        f"raw row {job_id}.registry_corrected_match",
    )
    expected_corrected = bool(
        reported["source_registry_match"]
        and not reported["exact_registry_match"]
        and reported["correction_applied"]
    )
    if corrected != expected_corrected:
        raise DevAnalysisError(
            f"Inconsistent registry_corrected_match for verify job {job_id}."
        )
    reported["registry_corrected_match"] = corrected
    row_distance = row.get("registry_hamming_distance")
    response_distance = response.get("registry_hamming_distance")
    if row_distance != response_distance:
        raise DevAnalysisError(
            f"Raw/report registry_hamming_distance mismatch for {job_id}."
        )
    return reported


def _load_records(
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_path = run_dir / "benchmark" / "raw_results.jsonl"
    if not raw_path.is_file():
        raise DevAnalysisError(f"Missing benchmark/raw_results.jsonl below {run_dir}.")
    index_dir = run_dir / "api_jobs" / "_index"
    if not index_dir.is_dir():
        raise DevAnalysisError(f"Missing api_jobs/_index below {run_dir}.")

    raw_rows = _read_jsonl(raw_path)
    records: list[dict[str, Any]] = []
    artifact_rows: list[dict[str, str]] = []
    seen_row_keys: set[str] = set()
    seen_jobs: set[str] = set()
    for ordinal, row in enumerate(raw_rows):
        row_key = str(row.get("row_key") or "").strip()
        if not row_key:
            raise DevAnalysisError(f"Raw row {ordinal + 1} has no row_key.")
        if row_key in seen_row_keys:
            raise DevAnalysisError(f"Duplicate row_key: {row_key}")
        seen_row_keys.add(row_key)
        if row.get("status") != "ok":
            raise DevAnalysisError(f"Development row is not successful: {row_key}")
        if row.get("run_class") != SOURCE_RUN_CLASS:
            raise DevAnalysisError(
                f"Expected run_class={SOURCE_RUN_CLASS!r}, got {row.get('run_class')!r}."
            )
        if _strict_bool(row.get("paper_eligible"), f"{row_key}.paper_eligible"):
            raise DevAnalysisError("Development analysis refuses paper-eligible rows.")
        if row.get("split") != "dev":
            raise DevAnalysisError(f"Non-development split in {row_key}.")

        sample_id = str(row.get("sample_id") or "").strip()
        domain = str(row.get("domain") or "").strip()
        attack_id = str(row.get("attack_id") or "").strip()
        attack_name = str(row.get("attack_name") or attack_id.split("__", 1)[0]).strip()
        method_id = str(row.get("method_id") or "").strip()
        if not all((sample_id, domain, attack_id, attack_name, method_id)):
            raise DevAnalysisError(f"Required grouping field is empty in {row_key}.")
        if row.get("seed") is None:
            raise DevAnalysisError(f"Seed is missing in {row_key}.")

        job_id = str(row.get("verify_job_id") or "").strip()
        if not job_id or JOB_ID_PATTERN.fullmatch(job_id) is None:
            raise DevAnalysisError(f"Invalid verify_job_id in {row_key}: {job_id!r}")
        if job_id in seen_jobs:
            raise DevAnalysisError(f"Verify job is reused by multiple rows: {job_id}")
        seen_jobs.add(job_id)
        index_path = (index_dir / f"{job_id}.json").resolve()
        if not _is_below(index_path, run_dir) or not index_path.is_file():
            raise DevAnalysisError(f"Missing run-local index for verify job {job_id}.")
        index_payload = _read_json(index_path, "verify-job index")
        report_path = _resolve_verify_report(run_dir, index_path, index_payload, job_id)
        report = _read_json(report_path, "verify report")
        if report.get("job_id") != job_id or report.get("job_type") != "verify":
            raise DevAnalysisError(f"Verify-report identity mismatch for {job_id}.")
        response = report.get("response")
        if not isinstance(response, dict):
            raise DevAnalysisError(f"Verify report has no response object: {report_path}")
        if response.get("job_id") != job_id or response.get("status") != "ok":
            raise DevAnalysisError(f"Verify response is not a successful {job_id} response.")

        raw_bits = _raw_word(report, response, job_id)
        reported = _validate_reported_registry_fields(row, response, job_id=job_id)
        predicted_area = _finite_float(
            response.get("predicted_mask_area_ratio"),
            f"verify response {job_id}.predicted_mask_area_ratio",
        )
        if not 0.0 <= predicted_area <= 1.0:
            raise DevAnalysisError(
                f"predicted_mask_area_ratio is outside [0, 1] for {job_id}."
            )
        recorded_area = row.get("predicted_tamper_area_ratio")
        if recorded_area is not None and not math.isclose(
            _finite_float(recorded_area, f"{row_key}.predicted_tamper_area_ratio"),
            predicted_area,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise DevAnalysisError(f"Raw/report mask-area mismatch for {job_id}.")

        condition = canonical_condition(row)
        records.append(
            {
                "raw": row,
                "row_key": row_key,
                "sample_id": sample_id,
                "domain": domain,
                "attack_id": attack_id,
                "attack_name": attack_name,
                "condition": condition,
                "method_id": method_id,
                "seed": row["seed"],
                "job_id": job_id,
                "raw_bits": raw_bits,
                "predicted_mask_area_ratio": predicted_area,
                **reported,
            }
        )
        artifact_rows.append(
            {
                "job_id": job_id,
                "index_path": _relative_path(index_path, run_dir),
                "index_sha256": sha256_file(index_path),
                "report_path": _relative_path(report_path, run_dir),
                "report_sha256": sha256_file(report_path),
            }
        )

    artifact_digest = hashlib.sha256()
    for artifact in sorted(artifact_rows, key=lambda item: item["job_id"]):
        artifact_digest.update(
            json.dumps(
                artifact, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        artifact_digest.update(b"\n")
    return records, {
        "raw_results_path": "benchmark/raw_results.jsonl",
        "raw_results_sha256": sha256_file(raw_path),
        "verify_index_path": "api_jobs/_index",
        "verify_artifact_count": len(artifact_rows),
        "verify_artifact_bundle_sha256": artifact_digest.hexdigest(),
    }


def _validate_run_shape(records: list[dict[str, Any]], expected_samples: int) -> None:
    if expected_samples < 1:
        raise DevAnalysisError("expected_samples must be positive.")
    samples = {record["sample_id"] for record in records}
    if len(samples) != expected_samples:
        raise DevAnalysisError(
            f"Expected exactly {expected_samples} samples, found {len(samples)}."
        )
    methods = {record["method_id"] for record in records}
    seeds = {record["seed"] for record in records}
    if len(methods) != 1 or len(seeds) != 1:
        raise DevAnalysisError(
            "Development analysis requires exactly one method and one seed globally."
        )
    per_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        per_sample[record["sample_id"]].append(record)
    condition_sets: dict[str, frozenset[str]] = {}
    for sample_id, sample_rows in per_sample.items():
        domains = {row["domain"] for row in sample_rows}
        identities = {(row["method_id"], row["seed"]) for row in sample_rows}
        conditions = [row["condition"] for row in sample_rows]
        if len(domains) != 1:
            raise DevAnalysisError(f"Domain changes across rows for {sample_id}.")
        if len(identities) != 1:
            raise DevAnalysisError(
                f"Development analysis requires one method/seed per sample: {sample_id}."
            )
        if len(conditions) != len(set(conditions)):
            raise DevAnalysisError(f"Duplicate canonical condition for {sample_id}.")
        condition_sets[sample_id] = frozenset(conditions)
    unique_condition_sets = set(condition_sets.values())
    if len(unique_condition_sets) != 1:
        raise DevAnalysisError("Samples do not share one complete canonical-condition grid.")

    definitions: dict[str, str] = {}
    for record in records:
        row = record["raw"]
        params = row.get("attack_params") or {}
        definition = json.dumps(
            {
                "attack_name": str(
                    row.get("attack_name") or record["attack_name"]
                ).lower(),
                "attack_params": {
                    str(key).lower(): _condition_component(value)
                    for key, value in sorted(params.items(), key=lambda item: str(item[0]))
                },
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        existing = definitions.setdefault(record["condition"], definition)
        if existing != definition:
            raise DevAnalysisError(
                f"Canonical-condition collision: {record['condition']}"
            )


def _require_run_local_file(path: Path, run_dir: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not _is_below(resolved, run_dir) or not resolved.is_file():
        raise DevAnalysisError(f"Missing or unsafe run-local {label}: {resolved}")
    return resolved


def _registry_payload_candidates(
    run_dir: Path, method_id: str, embed_job_id: str
) -> tuple[Path, ...]:
    return (
        run_dir
        / "benchmark"
        / "api_jobs"
        / method_id
        / embed_job_id
        / "embed"
        / "payload.json",
        run_dir / "api_jobs" / embed_job_id / "embed" / "payload.json",
    )


def _select_registry_payload(
    run_dir: Path, method_id: str, embed_job_id: str
) -> Path:
    matches: list[Path] = []
    for candidate in _registry_payload_candidates(run_dir, method_id, embed_job_id):
        resolved = candidate.resolve()
        if _is_below(resolved, run_dir) and resolved.is_file() and resolved not in matches:
            matches.append(resolved)
    if len(matches) != 1:
        raise DevAnalysisError(
            "Expected exactly one run-local payload artifact for "
            f"{embed_job_id}; found {len(matches)}."
        )
    return matches[0]


def _references_from_registry_snapshot(
    run_dir: Path,
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]] | None:
    registry_dir = (run_dir / "source-registry-snapshot").resolve()
    if not registry_dir.exists():
        return None
    if not _is_below(registry_dir, run_dir) or not registry_dir.is_dir():
        raise DevAnalysisError(f"Unsafe source-registry-snapshot: {registry_dir}")

    samples = sorted({record["sample_id"] for record in records})
    sample_domains: dict[str, str] = {}
    methods = {record["method_id"] for record in records}
    if len(methods) != 1:
        raise DevAnalysisError("Registry reconstruction requires exactly one method.")
    method_id = next(iter(methods))
    for record in records:
        existing = sample_domains.setdefault(record["sample_id"], record["domain"])
        if existing != record["domain"]:
            raise DevAnalysisError(
                f"Domain changes across rows for {record['sample_id']}."
            )

    registry_paths = sorted(registry_dir.glob("*.json"))
    if len(registry_paths) != len(samples):
        raise DevAnalysisError(
            "Registry snapshot size does not match the development sample set: "
            f"{len(registry_paths)} != {len(samples)}."
        )

    references: dict[str, dict[str, Any]] = {}
    artifact_rows: list[dict[str, str]] = []
    seen_ids: set[int] = set()
    seen_words: set[str] = set()
    owner_prefix = f"paper:{method_id}:"
    for registry_path in registry_paths:
        registry_path = _require_run_local_file(
            registry_path, run_dir, "registry record"
        )
        registry = _read_json(registry_path, "registry record")
        if registry.get("schema_version") != "cogniguard_source_registry_v2":
            raise DevAnalysisError(f"Unsupported registry schema: {registry_path}")
        if (
            registry.get("capsule_schema") != "hmac_source_capsule_v1"
            or registry.get("auth_level") != "hmac_registry"
        ):
            raise DevAnalysisError(
                f"Registry record is not an HMAC source capsule: {registry_path}"
            )
        owner_id = str(registry.get("owner_id") or "")
        if not owner_id.startswith(owner_prefix):
            raise DevAnalysisError(f"Unexpected registry owner binding: {registry_path}")
        sample_id = owner_id[len(owner_prefix) :]
        if sample_id not in sample_domains or sample_id in references:
            raise DevAnalysisError(
                f"Registry sample binding is missing or duplicated: {sample_id!r}"
            )
        embed_job_id = str(registry.get("embed_job_id") or "")
        if not embed_job_id or JOB_ID_PATTERN.fullmatch(embed_job_id) is None:
            raise DevAnalysisError(
                f"Invalid registry embed_job_id: {embed_job_id!r}"
            )
        payload_path = _select_registry_payload(run_dir, method_id, embed_job_id)
        payload = _read_json(payload_path, "embed payload")
        if (
            payload.get("capsule_schema") != "hmac_source_capsule_v1"
            or payload.get("auth_level") != "hmac_registry"
        ):
            raise DevAnalysisError(f"Payload is not HMAC-authenticated: {payload_path}")

        bits = _binary_word(payload.get("capsule_bits"), "registered capsule bits")
        try:
            copyright_id = int(registry.get("copyright_id"))
        except (TypeError, ValueError) as exc:
            raise DevAnalysisError(
                f"Invalid registry copyright id: {registry_path}"
            ) from exc
        if registry_path.name != f"{copyright_id:05d}.json":
            raise DevAnalysisError(
                f"Registry filename/id mismatch: {registry_path}"
            )
        if int(payload.get("copyright_id", -1)) != copyright_id:
            raise DevAnalysisError(
                f"Payload/registry copyright id mismatch: {registry_path}"
            )
        payload_id = str(registry.get("payload_id") or "")
        if not payload_id or str(payload.get("payload_id") or "") != payload_id:
            raise DevAnalysisError(
                f"Payload/registry payload id mismatch: {registry_path}"
            )
        capsule_hash = hashlib.sha256(bits.encode("utf-8")).hexdigest()
        if capsule_hash != str(registry.get("capsule_bits_sha256") or ""):
            raise DevAnalysisError(
                f"Payload codeword hash mismatch: {registry_path}"
            )
        if not hmac.compare_digest(
            str(payload.get("auth_hash") or ""),
            str(registry.get("auth_hash") or ""),
        ):
            raise DevAnalysisError(
                f"Payload/registry authentication hash mismatch: {registry_path}"
            )
        if copyright_id in seen_ids or bits in seen_words:
            raise DevAnalysisError("Registry snapshot contains duplicate ids or codewords.")
        seen_ids.add(copyright_id)
        seen_words.add(bits)
        references[sample_id] = {
            "sample_id": sample_id,
            "domain": sample_domains[sample_id],
            "bits": bits,
            "source_condition": "registry_payload_artifact",
            "source_job_id": embed_job_id,
        }
        artifact_rows.append(
            {
                "sample_id": sample_id,
                "registry_path": _relative_path(registry_path, run_dir),
                "registry_sha256": sha256_file(registry_path),
                "payload_path": _relative_path(payload_path, run_dir),
                "payload_sha256": sha256_file(payload_path),
            }
        )

    if set(references) != set(samples):
        raise DevAnalysisError("Registry snapshot does not exactly bind the sample set.")
    digest = hashlib.sha256()
    for artifact in sorted(artifact_rows, key=lambda row: row["sample_id"]):
        digest.update(
            json.dumps(
                artifact, ensure_ascii=True, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return references, {
        "policy": "authenticated_run_local_registry_snapshot_and_embed_payload",
        "selected_from_registry_payload": len(references),
        "selected_from_clean": 0,
        "selected_from_non_clean": 0,
        "exact_candidates_considered": 0,
        "samples_with_multiple_distinct_exact_words": 0,
        "registry_artifact_count": len(artifact_rows) * 2,
        "registry_artifact_bundle_sha256": digest.hexdigest(),
    }


def _select_references(
    records: list[dict[str, Any]],
    *,
    run_dir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    registry_references = _references_from_registry_snapshot(run_dir, records)
    if registry_references is not None:
        return registry_references

    per_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["exact_registry_match"]:
            per_sample[record["sample_id"]].append(record)
    samples = sorted({record["sample_id"] for record in records})
    missing = [sample_id for sample_id in samples if not per_sample.get(sample_id)]
    if missing:
        preview = ", ".join(missing[:5])
        raise DevAnalysisError(
            f"No exact_registry_match is available for {len(missing)} sample(s): {preview}"
        )

    references: dict[str, dict[str, Any]] = {}
    clean_count = 0
    conflicting_exact_words = 0
    exact_candidate_count = 0
    for sample_id in samples:
        candidates = sorted(
            per_sample[sample_id],
            key=lambda row: (
                row["condition"] != "clean",
                row["condition"],
                row["row_key"],
            ),
        )
        exact_candidate_count += len(candidates)
        if len({candidate["raw_bits"] for candidate in candidates}) > 1:
            conflicting_exact_words += 1
        selected = candidates[0]
        clean_count += int(selected["condition"] == "clean")
        references[sample_id] = {
            "sample_id": sample_id,
            "domain": selected["domain"],
            "bits": selected["raw_bits"],
            "source_condition": selected["condition"],
            "source_job_id": selected["job_id"],
        }
    return references, {
        "policy": "prefer_clean_then_lexicographically_first_exact_registry_match",
        "selected_from_clean": clean_count,
        "selected_from_non_clean": len(samples) - clean_count,
        "exact_candidates_considered": exact_candidate_count,
        "samples_with_multiple_distinct_exact_words": conflicting_exact_words,
    }


def _offline_lookup(
    raw_bits: str, references: dict[str, dict[str, Any]], expected_sample: str, radius: int
) -> str:
    candidates = [
        sample_id
        for sample_id, reference in references.items()
        if hamming_distance(raw_bits, reference["bits"]) <= radius
    ]
    if not candidates:
        return "no_candidate"
    if len(candidates) > 1:
        return "ambiguous"
    return "correct_unique" if candidates[0] == expected_sample else "wrong_unique"


def _validate_bit_accuracy_and_simulate(
    records: list[dict[str, Any]], references: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    for record in records:
        reference = references[record["sample_id"]]["bits"]
        distance = hamming_distance(record["raw_bits"], reference)
        recomputed = 1.0 - distance / MESSAGE_BITS
        recorded = _finite_float(
            record["raw"].get("bit_accuracy"), f"{record['row_key']}.bit_accuracy"
        )
        if not 0.0 <= recorded <= 1.0 or not math.isclose(
            recorded, recomputed, rel_tol=0.0, abs_tol=1e-12
        ):
            raise DevAnalysisError(
                f"bit_accuracy mismatch for {record['row_key']}: "
                f"recorded={recorded}, recomputed={recomputed}."
            )
        recorded_ber = record["raw"].get("bit_error_rate")
        if recorded_ber is not None and not math.isclose(
            _finite_float(recorded_ber, f"{record['row_key']}.bit_error_rate"),
            1.0 - recomputed,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise DevAnalysisError(f"bit_error_rate mismatch for {record['row_key']}.")
        record["hamming_to_reference"] = distance
        record["recomputed_bit_accuracy"] = recomputed
        record["offline_lookup"] = {
            radius: _offline_lookup(
                record["raw_bits"], references, record["sample_id"], radius
            )
            for radius in RADII
        }
    return {
        "validated_rows": len(records),
        "mismatch_count": 0,
        "absolute_tolerance": 1e-12,
        "reference_bit_width": MESSAGE_BITS,
    }


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate a quantile of an empty sequence.")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(
        sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction
    )


def _numeric_stats(values: Iterable[Any], label: str) -> dict[str, Any]:
    normalized = sorted(
        _finite_float(value, label) for value in values if value is not None
    )
    if not normalized:
        return {
            "count": 0,
            "mean": None,
            "stddev_population": None,
            "min": None,
            "p50": None,
            "p95": None,
            "max": None,
        }
    return {
        "count": len(normalized),
        "mean": statistics.fmean(normalized),
        "stddev_population": statistics.pstdev(normalized),
        "min": normalized[0],
        "p50": _quantile(normalized, 0.50),
        "p95": _quantile(normalized, 0.95),
        "max": normalized[-1],
    }


def _rate(records: Sequence[dict[str, Any]], field: str) -> dict[str, Any]:
    count = sum(int(bool(record[field])) for record in records)
    return {"count": count, "total": len(records), "rate": count / len(records)}


def _summarize(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("Cannot summarize an empty record group.")
    hamming_values = [int(record["hamming_to_reference"]) for record in records]
    hamming_summary = _numeric_stats(hamming_values, "hamming_to_reference")
    hamming_summary["histogram"] = {
        str(distance): count
        for distance, count in sorted(Counter(hamming_values).items())
    }

    offline: dict[str, Any] = {}
    for radius in RADII:
        outcomes = Counter(record["offline_lookup"][radius] for record in records)
        counts = {
            outcome: int(outcomes.get(outcome, 0))
            for outcome in (
                "correct_unique",
                "wrong_unique",
                "ambiguous",
                "no_candidate",
            )
        }
        offline[str(radius)] = {
            "radius": radius,
            "lookup_count": len(records),
            "counts": counts,
            "rates": {
                outcome: count / len(records) for outcome, count in counts.items()
            },
        }

    return {
        "row_count": len(records),
        "sample_count": len({record["sample_id"] for record in records}),
        "reported_registry": {
            field: _rate(records, field)
            for field in (
                "exact_registry_match",
                "registry_corrected_match",
                "source_registry_match",
                "correction_applied",
            )
        },
        "bit_accuracy": _numeric_stats(
            (record["recomputed_bit_accuracy"] for record in records),
            "recomputed_bit_accuracy",
        ),
        "hamming_to_reference": hamming_summary,
        "mask": {
            metric: _numeric_stats(
                (
                    record["predicted_mask_area_ratio"]
                    if metric == "predicted_mask_area_ratio"
                    else record["raw"].get(metric)
                    for record in records
                ),
                metric,
            )
            for metric in MASK_METRICS
        },
        "quality": {
            metric: _numeric_stats(
                (record["raw"].get(metric) for record in records), metric
            )
            for metric in QUALITY_METRICS
        },
        "latency_seconds": {
            "verify": _numeric_stats(
                (record["raw"].get("verify_latency_seconds") for record in records),
                "verify_latency_seconds",
            )
        },
        "offline_codebook_lookup": offline,
    }


def _grouped(
    records: Sequence[dict[str, Any]], key: Callable[[dict[str, Any]], str]
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[key(record)].append(record)
    return {name: _summarize(groups[name]) for name in sorted(groups)}


def _domain_condition_groups(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    domains: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        domains[record["domain"]][record["condition"]].append(record)
    return {
        domain: {
            condition: _summarize(domains[domain][condition])
            for condition in sorted(domains[domain])
        }
        for domain in sorted(domains)
    }


def _condition_definitions(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    definitions: dict[str, dict[str, Any]] = {}
    for record in records:
        definitions.setdefault(
            record["condition"],
            {
                "attack_name": record["attack_name"],
                "attack_params": record["raw"].get("attack_params") or {},
            },
        )
    return {condition: definitions[condition] for condition in sorted(definitions)}


def _codebook_summary(references: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ordered = [references[sample_id] for sample_id in sorted(references)]
    distances: list[int] = []
    for index, reference in enumerate(ordered):
        for prior in ordered[:index]:
            distances.append(hamming_distance(reference["bits"], prior["bits"]))
    histogram = Counter(distances)
    minimum = min(distances) if distances else None
    serialization = "".join(
        f"{reference['sample_id']}\t{reference['bits']}\n" for reference in ordered
    )
    return {
        "entry_count": len(ordered),
        "bit_width": MESSAGE_BITS,
        "codebook_sha256": hashlib.sha256(serialization.encode("utf-8")).hexdigest(),
        "pairwise_distance": {
            "pair_count": len(distances),
            "d_min": minimum,
            "pairs_at_d_min": (
                int(histogram.get(minimum, 0)) if minimum is not None else 0
            ),
            "mean": statistics.fmean(distances) if distances else None,
            "max": max(distances) if distances else None,
            "histogram": {
                str(distance): count for distance, count in sorted(histogram.items())
            },
        },
    }


def analyze_run(run_dir: str | Path, *, expected_samples: int = 117) -> dict[str, Any]:
    """Return a deterministic development-only analysis for ``run_dir``."""

    resolved_run = Path(run_dir).expanduser().resolve()
    if not resolved_run.is_dir():
        raise DevAnalysisError(f"RUN directory does not exist: {resolved_run}")
    records, inputs = _load_records(resolved_run)
    _validate_run_shape(records, expected_samples)
    references, reference_selection = _select_references(
        records, run_dir=resolved_run
    )
    bit_validation = _validate_bit_accuracy_and_simulate(records, references)

    conditions = sorted({record["condition"] for record in records})
    methods = sorted({record["method_id"] for record in records})
    seeds = sorted({record["seed"] for record in records}, key=str)
    domains = sorted({record["domain"] for record in records})
    return {
        "schema_version": SCHEMA_VERSION,
        "result_class": RESULT_CLASS,
        "run_class": "dev_tuning_offline_analysis",
        "source_run_class": SOURCE_RUN_CLASS,
        "paper_eligible": False,
        "scope": {
            "split": "dev",
            "sample_count": len(references),
            "row_count": len(records),
            "methods": methods,
            "seeds": seeds,
            "domains": domains,
            "canonical_conditions": conditions,
            "canonical_condition_definitions": _condition_definitions(records),
            "network_access_required": False,
            "model_or_secret_access_required": False,
        },
        "inputs": inputs,
        "reference_selection": reference_selection,
        "bit_accuracy_validation": bit_validation,
        "development_codebook": _codebook_summary(references),
        "offline_simulation": {
            "radii": list(RADII),
            "raw_word_policy": "reuse_the_same_64_bit_verify_word_at_every_radius",
            "lookup_policy": "one_closed_set_codebook_lookup_per_row_per_radius",
            "candidate_rule": "all_development_codewords_with_hamming_distance_le_radius",
            "outcomes": [
                "correct_unique",
                "wrong_unique",
                "ambiguous",
                "no_candidate",
            ],
        },
        "aggregates": {
            "overall": _summarize(records),
            "by_attack_name": _grouped(records, lambda row: row["attack_name"]),
            "by_attack_id": _grouped(records, lambda row: row["attack_id"]),
            "by_canonical_condition": _grouped(
                records, lambda row: row["condition"]
            ),
            "by_domain": _grouped(records, lambda row: row["domain"]),
            "by_domain_and_canonical_condition": _domain_condition_groups(records),
        },
        "formal_3000_registry": {
            "recalculation_required": True,
            "development_results_transferable": False,
            "required_action": (
                "Rebuild the formal 3000-image registry, re-extract its reference "
                "codebook, and recompute pairwise d_min plus every radius-0..5 lookup."
            ),
            "reason": (
                "Codebook distance, ambiguity, wrong-source acceptance, and radius "
                "outcomes depend on the complete registry; this report uses only the "
                "development registry."
            ),
        },
    }


def write_analysis(payload: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output)
    return output


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = Path(args.run).expanduser().resolve()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else run_dir / "development_only_analysis.json"
    )
    try:
        payload = analyze_run(run_dir, expected_samples=args.expected_samples)
        written = write_analysis(payload, output)
    except (DevAnalysisError, OSError) as exc:
        raise SystemExit(f"Development analysis failed: {exc}") from exc
    print(
        json.dumps(
            {
                "result_class": RESULT_CLASS,
                "output": str(written),
                "sha256": sha256_file(written),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
