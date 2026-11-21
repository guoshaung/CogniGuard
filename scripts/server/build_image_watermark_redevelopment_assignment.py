#!/usr/bin/env python3
"""Lock the post-failure tuning/calibration/confirmation/test role assignment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from protection.supporting.image_watermark.experiments.manifest import (
    dataset_roots_from_config,
    load_manifest,
    manifest_path_from_config,
    validate_manifest_lock,
)
from scripts.server.audit_image_watermark_redevelopment_history import (
    LEDGER_SCHEMA_VERSION,
    sha256_file,
)
from scripts.server.image_watermark_redevelopment_protocol import (
    ASSIGNMENT_SCHEMA_VERSION,
    CALIBRATION_DATASET_QUOTAS,
    CONFIRMATION_DATASET_QUOTAS,
    DATASET_ORDER,
    EXPECTED_FORMAL_SAMPLES,
    EXPECTED_FORMAL_SPLITS,
    EXPECTED_ROLE_COUNTS,
    HISTORY_AUDIT_CUTOFF_UTC,
    PROTOCOL_ID,
    SPLIT_SEED,
)


RAW_DOMAIN_MINIMUM_COUNT = 2
CALIBRATION_STRATUM_MINIMUM = 2
CONFIRMATION_STRATUM_MINIMUM = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an immutable v3 role assignment from untouched train rows."
    )
    parser.add_argument("--source", required=True, help="Frozen formal YAML.")
    parser.add_argument(
        "--ledger",
        action="append",
        required=True,
        help="Usage ledger to union; repeat for local and server evidence.",
    )
    parser.add_argument("--output", required=True, help="Fresh assignment JSONL.")
    parser.add_argument(
        "--lock-output",
        default=None,
        help="Fresh lock JSON; defaults to OUTPUT.lock.json.",
    )
    return parser.parse_args()


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON input: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input is not an object: {path}")
    return payload


def _selection_key(row: Any, role: str) -> str:
    material = "|".join(
        (
            SPLIT_SEED,
            role,
            row.source_dataset,
            row.domain,
            row.source_family,
            row.sha256,
            row.sample_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _analysis_strata(train_rows: list[Any]) -> dict[str, str]:
    domain_counts = Counter(row.domain for row in train_rows)
    result: dict[str, str] = {}
    for row in train_rows:
        if domain_counts[row.domain] >= 15:
            result[row.sample_id] = row.domain
        elif row.source_dataset == "met_open_access_cc0":
            result[row.sample_id] = "met_other_sparse"
        elif row.source_dataset == "nasa_images_policy_audited":
            result[row.sample_id] = "nasa_other_sparse"
        else:
            result[row.sample_id] = f"{row.source_dataset}_other_sparse"
    stratum_counts = Counter(result.values())
    too_small = {name: count for name, count in stratum_counts.items() if count < 15}
    if too_small:
        raise ValueError(
            "Reporting strata cannot satisfy 2/4 calibration/confirmation minima: "
            f"{too_small}"
        )
    return result


def _allocate_role(
    *,
    role: str,
    untouched: list[Any],
    unavailable: set[str],
    quotas: dict[str, int],
    strata: dict[str, str],
    stratum_minimum: int,
    covered_domains: set[tuple[str, str]],
) -> set[str]:
    selected: set[str] = set()

    def available(rows: Iterable[Any]) -> list[Any]:
        return [
            row
            for row in rows
            if row.sample_id not in unavailable and row.sample_id not in selected
        ]

    by_dataset_domain: dict[tuple[str, str], list[Any]] = defaultdict(list)
    by_dataset_stratum: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for row in untouched:
        by_dataset_domain[(row.source_dataset, row.domain)].append(row)
        by_dataset_stratum[(row.source_dataset, strata[row.sample_id])].append(row)

    for key in sorted(covered_domains):
        candidates = sorted(
            available(by_dataset_domain[key]), key=lambda row: _selection_key(row, role)
        )
        if not candidates:
            raise ValueError(f"Role {role} cannot cover raw domain {key}.")
        selected.add(candidates[0].sample_id)

    for key in sorted(by_dataset_stratum):
        current = sum(
            1
            for sample_id in selected
            if any(
                row.sample_id == sample_id
                and (row.source_dataset, strata[row.sample_id]) == key
                for row in by_dataset_stratum[key]
            )
        )
        needed = max(0, stratum_minimum - current)
        candidates = sorted(
            available(by_dataset_stratum[key]),
            key=lambda row: _selection_key(row, role),
        )
        if len(candidates) < needed:
            raise ValueError(f"Role {role} cannot meet reporting stratum minimum {key}.")
        selected.update(row.sample_id for row in candidates[:needed])

    rows_by_dataset: dict[str, list[Any]] = defaultdict(list)
    for row in untouched:
        rows_by_dataset[row.source_dataset].append(row)
    row_by_id = {row.sample_id: row for row in untouched}
    for dataset in DATASET_ORDER:
        already = sum(
            1 for sample_id in selected if row_by_id[sample_id].source_dataset == dataset
        )
        remaining = quotas[dataset] - already
        if remaining < 0:
            raise ValueError(
                f"Role {role} coverage minima exceed the exact quota for {dataset}."
            )
        candidates = sorted(
            available(rows_by_dataset[dataset]),
            key=lambda row: _selection_key(row, role),
        )
        if len(candidates) < remaining:
            raise ValueError(
                f"Role {role} has insufficient untouched rows for {dataset}: "
                f"needed={remaining}, available={len(candidates)}."
            )
        selected.update(row.sample_id for row in candidates[:remaining])

    observed = Counter(row_by_id[sample_id].source_dataset for sample_id in selected)
    if dict(observed) != quotas:
        raise RuntimeError(
            f"Role {role} exact source quotas drifted: {dict(observed)} != {quotas}."
        )
    return selected


def build_assignment(
    source_config: Path,
    *,
    ledger_paths: list[Path],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_config = source_config.expanduser().resolve()
    source_manifest = manifest_path_from_config(source_config, environ={})
    roots = dataset_roots_from_config(source_config, environ={})
    rows = load_manifest(
        source_manifest,
        dataset_roots=roots,
        require_files=True,
        verify_hashes=False,
    )
    split_counts = Counter(row.split for row in rows)
    if len(rows) != EXPECTED_FORMAL_SAMPLES or dict(split_counts) != EXPECTED_FORMAL_SPLITS:
        raise ValueError("Formal manifest does not match the frozen 3000/split contract.")
    lock_audit = validate_manifest_lock(
        source_manifest,
        rows,
        config_path=source_config,
        dataset_roots=roots,
    )
    row_by_id = {row.sample_id: row for row in rows}
    ledgers: list[dict[str, Any]] = []
    touched_ids: set[str] = set()
    ledger_evidence_hits: Counter[str] = Counter()
    full_source_validation_ledgers = 0
    for raw_path in ledger_paths:
        path = raw_path.expanduser().resolve()
        ledger = _read_json(path)
        declared_payload_sha256 = ledger.get("ledger_payload_sha256")
        authenticated_payload = dict(ledger)
        authenticated_payload.pop("ledger_payload_sha256", None)
        if (
            ledger.get("schema_version") != LEDGER_SCHEMA_VERSION
            or ledger.get("protocol_id") != PROTOCOL_ID
            or ledger.get("source_formal_manifest_sha256") != sha256_file(source_manifest)
            or ledger.get("unreadable_file_count") != 0
            or ledger.get("audit_cutoff_utc") != HISTORY_AUDIT_CUTOFF_UTC
            or ledger.get("skipped_after_cutoff_count") != 0
            or ledger.get("hash_output_images") is not True
            or type(ledger.get("hashed_image_files")) is not int
            or ledger.get("hashed_image_files", -1) < 0
            or declared_payload_sha256
            != hashlib.sha256(
                _canonical_json(authenticated_payload).encode("utf-8")
            ).hexdigest()
        ):
            raise ValueError(f"Usage ledger is incomplete or targets another manifest: {path}")
        validation_mode = ledger.get("source_validation_mode")
        if validation_mode not in {
            "portable_inventory_identity_only",
            "full_manifest_lock_and_upstream_artifacts",
        }:
            raise ValueError(f"Usage ledger source validation mode is invalid: {path}")
        if validation_mode == "full_manifest_lock_and_upstream_artifacts":
            full_source_validation_ledgers += 1
        touched_rows = ledger.get("touched_rows")
        if (
            not isinstance(touched_rows, list)
            or ledger.get("touched_total") != len(touched_rows)
        ):
            raise ValueError(f"Usage ledger touched-row count is inconsistent: {path}")
        for item in touched_rows:
            if not isinstance(item, dict) or item.get("sample_id") not in row_by_id:
                raise ValueError(f"Usage ledger contains an unknown sample row: {path}")
            sample_id = str(item["sample_id"])
            source_row = row_by_id[sample_id]
            if (
                item.get("source_family") != source_row.source_family
                or item.get("sha256") != source_row.sha256
                or item.get("source_dataset") != source_row.source_dataset
                or item.get("domain") != source_row.domain
                or item.get("formal_split") != source_row.split
                or type(item.get("evidence_hit_count")) is not int
                or item.get("evidence_hit_count", 0) <= 0
                or not isinstance(item.get("evidence"), list)
                or not item.get("evidence")
            ):
                raise ValueError(f"Usage ledger sample evidence is unauthenticated: {path}")
            touched_ids.add(sample_id)
            ledger_evidence_hits[sample_id] += int(item.get("evidence_hit_count") or 0)
        ledgers.append(
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "payload_sha256": ledger.get("ledger_payload_sha256"),
                "scan_roots": ledger.get("scan_roots"),
                "scanned_files": ledger.get("scanned_files"),
                "scanned_bytes": ledger.get("scanned_bytes"),
                "touched_total": ledger.get("touched_total"),
                "source_validation_mode": validation_mode,
                "audit_cutoff_utc": ledger.get("audit_cutoff_utc"),
                "hashed_image_files": ledger.get("hashed_image_files"),
            }
        )

    if full_source_validation_ledgers < 1:
        raise ValueError(
            "At least one usage ledger must fully validate the server-side source "
            "manifest lock and upstream artifacts."
        )

    train_rows = [row for row in rows if row.split == "train"]
    untouched = [row for row in train_rows if row.sample_id not in touched_ids]
    untouched_counts = Counter(row.source_dataset for row in untouched)
    minimum_required = {
        dataset: CALIBRATION_DATASET_QUOTAS[dataset]
        + CONFIRMATION_DATASET_QUOTAS[dataset]
        for dataset in DATASET_ORDER
    }
    shortages = {
        dataset: {"required": minimum_required[dataset], "available": untouched_counts[dataset]}
        for dataset in DATASET_ORDER
        if untouched_counts[dataset] < minimum_required[dataset]
    }
    if shortages:
        raise ValueError(
            "Untouched train pool is insufficient; collect new data instead of "
            f"weakening the protocol: {shortages}"
        )
    strata = _analysis_strata(train_rows)
    domain_counts = Counter((row.source_dataset, row.domain) for row in train_rows)
    covered_domains = {
        key for key, count in domain_counts.items() if count >= RAW_DOMAIN_MINIMUM_COUNT
    }
    untouched_domain_counts = Counter(
        (row.source_dataset, row.domain) for row in untouched
    )
    uncovered = sorted(key for key in covered_domains if untouched_domain_counts[key] < 2)
    if uncovered:
        raise ValueError(
            "History use prevents raw-domain coverage in both new holdouts: "
            f"{uncovered}. Add new data."
        )

    calibration = _allocate_role(
        role="calibration",
        untouched=untouched,
        unavailable=set(),
        quotas=CALIBRATION_DATASET_QUOTAS,
        strata=strata,
        stratum_minimum=CALIBRATION_STRATUM_MINIMUM,
        covered_domains=covered_domains,
    )
    confirmation = _allocate_role(
        role="confirmation",
        untouched=untouched,
        unavailable=set(calibration),
        quotas=CONFIRMATION_DATASET_QUOTAS,
        strata=strata,
        stratum_minimum=CONFIRMATION_STRATUM_MINIMUM,
        covered_domains=covered_domains,
    )
    assignment_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.split == "test":
            role = "formal_test_sealed"
        elif row.split == "dev":
            role = "legacy_observed_dev"
        elif row.sample_id in calibration:
            role = "calibration"
        elif row.sample_id in confirmation:
            role = "confirmation"
        else:
            role = "tuning"
        assignment_rows.append(
            {
                "sample_id": row.sample_id,
                "source_family": row.source_family,
                "sha256": row.sha256,
                "source_dataset": row.source_dataset,
                "domain": row.domain,
                "formal_split": row.split,
                "redevelopment_role": role,
                "analysis_stratum": (
                    strata[row.sample_id] if row.split == "train" else row.domain
                ),
                "selection_key": (
                    _selection_key(row, role)
                    if role in {"calibration", "confirmation"}
                    else None
                ),
                "history_touched": row.sample_id in touched_ids,
                "history_evidence_hit_count": int(
                    ledger_evidence_hits[row.sample_id]
                ),
            }
        )
    assignment_rows.sort(key=lambda item: (item["source_dataset"], item["sample_id"]))
    role_counts = Counter(item["redevelopment_role"] for item in assignment_rows)
    if dict(role_counts) != EXPECTED_ROLE_COUNTS:
        raise RuntimeError(
            f"Role counts drifted: {dict(role_counts)} != {EXPECTED_ROLE_COUNTS}."
        )
    for role in ("calibration", "confirmation"):
        selected_rows = [
            item for item in assignment_rows if item["redevelopment_role"] == role
        ]
        if any(item["history_touched"] for item in selected_rows):
            raise RuntimeError(f"Touched data leaked into {role}.")
        for field in ("sample_id", "source_family", "sha256"):
            if len({item[field] for item in selected_rows}) != len(selected_rows):
                raise RuntimeError(f"Duplicate {field} within {role}.")
    calibration_rows = {
        item["sample_id"] for item in assignment_rows if item["redevelopment_role"] == "calibration"
    }
    confirmation_rows = {
        item["sample_id"] for item in assignment_rows if item["redevelopment_role"] == "confirmation"
    }
    if calibration_rows & confirmation_rows:
        raise RuntimeError("Calibration and confirmation assignments overlap.")

    assignment_text = "".join(
        _canonical_json(item) + "\n" for item in assignment_rows
    )
    lock: dict[str, Any] = {
        "schema_version": ASSIGNMENT_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "split_seed": SPLIT_SEED,
        "source_formal_config": str(source_config),
        "source_formal_config_sha256": sha256_file(source_config),
        "source_formal_manifest": str(source_manifest),
        "source_formal_manifest_sha256": sha256_file(source_manifest),
        "source_formal_manifest_lock": lock_audit,
        "history_ledgers": ledgers,
        "history_touched_total": len(touched_ids),
        "history_touched_train": sum(
            1 for sample_id in touched_ids if row_by_id[sample_id].split == "train"
        ),
        "formal_split_counts": dict(split_counts),
        "role_counts": dict(role_counts),
        "calibration_dataset_quotas": CALIBRATION_DATASET_QUOTAS,
        "confirmation_dataset_quotas": CONFIRMATION_DATASET_QUOTAS,
        "covered_raw_domain_count": len(covered_domains),
        "covered_raw_domains": [list(key) for key in sorted(covered_domains)],
        "analysis_stratum_counts": dict(
            sorted(Counter(strata.values()).items())
        ),
        "assignment_rows": len(assignment_rows),
        "assignment_sha256": hashlib.sha256(assignment_text.encode("utf-8")).hexdigest(),
        "formal_test_identity_sha256": hashlib.sha256(
            "".join(
                f"{item['sample_id']}\t{item['source_family']}\t{item['sha256']}\n"
                for item in assignment_rows
                if item["redevelopment_role"] == "formal_test_sealed"
            ).encode("utf-8")
        ).hexdigest(),
        "formal_test_rows_consumed": 0,
        "limitations": [
            "source_family and exact SHA isolation do not prove semantic near-duplicate independence",
            "local history evidence is not an externally trusted append-only audit log",
        ],
    }
    lock["lock_payload_sha256"] = hashlib.sha256(
        _canonical_json(lock).encode("utf-8")
    ).hexdigest()
    return assignment_rows, lock


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    lock_output = (
        Path(args.lock_output).expanduser().resolve()
        if args.lock_output
        else output.with_suffix(output.suffix + ".lock.json")
    )
    if output == lock_output or output.exists() or lock_output.exists():
        raise FileExistsError("Refusing to overwrite a v3 role assignment bundle.")
    rows, lock = build_assignment(
        Path(args.source),
        ledger_paths=[Path(value) for value in args.ledger],
    )
    assignment_text = "".join(_canonical_json(item) + "\n" for item in rows)
    if hashlib.sha256(assignment_text.encode("utf-8")).hexdigest() != lock[
        "assignment_sha256"
    ]:
        raise RuntimeError("Assignment hash changed before write.")
    _atomic_write(output, assignment_text)
    lock["assignment_path"] = str(output)
    lock["assignment_file_sha256"] = sha256_file(output)
    lock.pop("lock_payload_sha256", None)
    lock["lock_payload_sha256"] = hashlib.sha256(
        _canonical_json(lock).encode("utf-8")
    ).hexdigest()
    _atomic_write(
        lock_output,
        json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(
        json.dumps(
            {
                "status": "created",
                "assignment": str(output),
                "assignment_sha256": sha256_file(output),
                "lock": str(lock_output),
                "lock_sha256": sha256_file(lock_output),
                "role_counts": lock["role_counts"],
                "history_touched_train": lock["history_touched_train"],
                "formal_test_rows_consumed": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
