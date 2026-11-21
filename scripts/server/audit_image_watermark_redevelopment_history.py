#!/usr/bin/env python3
"""Build a conservative, content-hash-aware usage ledger for the v3 data split."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from protection.supporting.image_watermark.experiments.manifest import (
    MANIFEST_LOCK_SCHEMA_VERSION,
    dataset_roots_from_config,
    load_manifest,
    manifest_assignment_sha256,
    manifest_lock_path,
    manifest_path_from_config,
    validate_manifest_lock,
)
from scripts.server.image_watermark_redevelopment_protocol import (
    ASSIGNMENT_SCHEMA_VERSION,
    EXPECTED_FORMAL_SAMPLES,
    EXPECTED_FORMAL_SPLITS,
    PROTOCOL_ID,
)


LEDGER_SCHEMA_VERSION = "cogniguard_image_redevelopment_usage_ledger_v1"
TEXT_SUFFIXES = frozenset(
    {
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".log",
        ".txt",
        ".csv",
        ".md",
        ".sha256",
    }
)
SHA256_PATTERN = re.compile(rb"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
JSON_STRING_PATTERN = re.compile(rb'"((?:\\.|[^"\\])*)"')
TOKEN_PATTERN = re.compile(rb"[^\s\"'`,;=\[\]{}()<>]+")
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
EVIDENCE_PATH_LIMIT = 12
MATCH_KIND_ORDER = {
    "sample_id": 0,
    "source_family": 1,
    "image_sha256": 2,
    "full_source_path": 3,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit prior image-watermark outputs without opening image content."
    )
    parser.add_argument("--source", required=True, help="Frozen formal YAML.")
    parser.add_argument(
        "--scan-root",
        action="append",
        required=True,
        help="Prior-output root to scan; repeat for multiple roots.",
    )
    parser.add_argument(
        "--hash-output-images",
        action="store_true",
        help=(
            "Hash image files under scan roots and treat an exact formal-source "
            "SHA match as historical use. Image pixels are never decoded."
        ),
    )
    parser.add_argument(
        "--allow-missing-source-files",
        action="store_true",
        help=(
            "Permit an inventory-only workstation audit when external dataset "
            "files are absent. Manifest/config/lock identity is still verified; "
            "the authoritative server audit must omit this option."
        ),
    )
    parser.add_argument(
        "--cutoff-utc",
        default=None,
        help=(
            "Optional inclusive evidence cutoff in ISO-8601 UTC. Files modified "
            "after the cutoff are recorded but not scanned."
        ),
    )
    parser.add_argument("--output", required=True, help="Fresh ledger JSON path.")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _split_counts(rows: Iterable[Any]) -> dict[str, int]:
    counts = Counter(row.split for row in rows)
    return dict(sorted(counts.items()))


def _candidate_files(
    roots: Iterable[Path],
    excluded: set[Path],
    *,
    include_images: bool,
) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            raise FileNotFoundError(f"History scan root is missing: {root}")
        paths = [root] if root.is_file() else root.rglob("*")
        for raw in paths:
            try:
                path = raw.resolve()
            except OSError:
                continue
            if path in seen or path in excluded or not path.is_file():
                continue
            seen.add(path)
            if path.suffix.lower() in TEXT_SUFFIXES or (
                include_images and path.suffix.lower() in IMAGE_SUFFIXES
            ):
                yield path


def _sample_id_tokens(line: bytes, dataset_prefixes: tuple[bytes, ...]) -> set[str]:
    tokens: set[str] = set()
    delimiters = b"\"'\t\r\n ,]}>)"
    for prefix in dataset_prefixes:
        start = 0
        while True:
            index = line.find(prefix, start)
            if index < 0:
                break
            end = index + len(prefix)
            while end < len(line) and line[end] not in delimiters:
                end += 1
            try:
                tokens.add(line[index:end].decode("utf-8"))
            except UnicodeDecodeError:
                pass
            start = max(end, index + 1)
    return tokens


def _exact_string_tokens(line: bytes) -> set[str]:
    """Extract quoted JSON strings and conservative shell/text tokens."""

    tokens: set[str] = set()
    for raw in JSON_STRING_PATTERN.findall(line):
        try:
            value = json.loads(b'"' + raw + b'"')
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(value, str):
            tokens.add(value)
    for raw in TOKEN_PATTERN.findall(line):
        try:
            tokens.add(raw.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return tokens


def _parse_cutoff(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    rendered = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(rendered)
    except ValueError as exc:
        raise ValueError("--cutoff-utc must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise ValueError("--cutoff-utc must include a UTC offset or trailing Z.")
    return parsed.astimezone(timezone.utc)


def _validate_lock_identity_only(
    source_config: Path,
    source_manifest: Path,
    rows: list[Any],
) -> dict[str, Any]:
    """Authenticate portable inventory inputs without requiring external data roots."""

    lock_path = manifest_lock_path(source_manifest)
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid manifest lock: {lock_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest lock must be an object: {lock_path}")
    dataset_counts = Counter(row.source_dataset for row in rows)
    split_counts = Counter(row.split for row in rows)
    expected = {
        "schema_version": MANIFEST_LOCK_SCHEMA_VERSION,
        "manifest_filename": source_manifest.name,
        "manifest_sha256": sha256_file(source_manifest),
        "config_sha256": sha256_file(source_config),
        "total_samples": len(rows),
        "dataset_counts": dict(sorted(dataset_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "unique_sha256_count": len({row.sha256 for row in rows}),
        "unique_source_family_count": len({row.source_family for row in rows}),
        "assignment_sha256": manifest_assignment_sha256(rows),
    }
    mismatches = {
        key: {"expected": expected_value, "observed": payload.get(key)}
        for key, expected_value in expected.items()
        if payload.get(key) != expected_value
    }
    if mismatches:
        raise ValueError(f"Portable manifest lock identity mismatch: {mismatches}")
    result = dict(payload)
    result["lock_path"] = str(lock_path.resolve())
    result["lock_sha256"] = sha256_file(lock_path)
    result["validation_mode"] = "portable_inventory_identity_only"
    return result


def audit_history(
    source_config: Path,
    *,
    scan_roots: list[Path],
    output_path: Path,
    hash_output_images: bool = False,
    allow_missing_source_files: bool = False,
    cutoff_utc: datetime | None = None,
) -> dict[str, Any]:
    source_config = source_config.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite history ledger: {output_path}")
    source_manifest = manifest_path_from_config(source_config, environ={})
    roots = dataset_roots_from_config(source_config, environ={})
    rows = load_manifest(
        source_manifest,
        dataset_roots=roots,
        require_files=not allow_missing_source_files,
        verify_hashes=False,
    )
    if len(rows) != EXPECTED_FORMAL_SAMPLES or _split_counts(rows) != EXPECTED_FORMAL_SPLITS:
        raise ValueError("Formal manifest count/splits differ from the frozen 3000 contract.")
    if allow_missing_source_files:
        lock_audit = _validate_lock_identity_only(
            source_config, source_manifest, rows
        )
        source_validation_mode = "portable_inventory_identity_only"
    else:
        lock_audit = validate_manifest_lock(
            source_manifest,
            rows,
            config_path=source_config,
            dataset_roots=roots,
        )
        source_validation_mode = "full_manifest_lock_and_upstream_artifacts"
    by_sample_id = {row.sample_id: row for row in rows}
    by_sha256 = {row.sha256: row for row in rows}
    by_source_family = {row.source_family: row for row in rows}
    if (
        len(by_sample_id) != len(rows)
        or len(by_sha256) != len(rows)
        or len(by_source_family) != len(rows)
    ):
        raise ValueError("Formal manifest identities are not globally unique.")

    by_full_source_path: dict[str, Any] = {}
    for row in rows:
        root = roots.get(row.source_dataset)
        if root is None:
            raise ValueError(f"Missing dataset root for {row.source_dataset}.")
        path = (Path(root).expanduser().resolve() / row.relative_path).resolve()
        by_full_source_path[str(path)] = row
        by_full_source_path[path.as_posix()] = row

    excluded = {
        source_manifest.resolve(),
        Path(lock_audit["lock_path"]).resolve(),
        source_manifest.with_suffix(".report.json").resolve(),
        output_path,
    }
    dataset_prefixes = tuple(
        f"{name}:".encode("utf-8") for name in sorted({row.source_dataset for row in rows})
    )
    evidence: dict[str, list[dict[str, str]]] = defaultdict(list)
    hit_counts: Counter[str] = Counter()
    scanned_files = 0
    scanned_bytes = 0
    unreadable: list[str] = []
    file_kind_counts: Counter[str] = Counter()
    scanned_text_files = 0
    hashed_image_files = 0
    hashed_image_bytes = 0
    exact_output_image_sha_hits = 0
    skipped_after_cutoff: list[str] = []
    canonical_copy_exclusions: list[str] = []
    canonical_manifest_sha256 = sha256_file(source_manifest)

    def record_hit(
        row: Any,
        *,
        path: Path,
        line_number: int | None,
        match_kind: str,
        evidence_file_sha256: str,
        size: int,
        mtime_utc: str,
    ) -> None:
        hit_counts[row.sample_id] += 1
        if len(evidence[row.sample_id]) >= EVIDENCE_PATH_LIMIT:
            return
        item = {
            "path": str(path),
            "match": match_kind,
            "evidence_file_sha256": evidence_file_sha256,
            "size_bytes": str(size),
            "mtime_utc": mtime_utc,
        }
        if line_number is not None:
            item["line"] = str(line_number)
        evidence[row.sample_id].append(item)

    for path in _candidate_files(
        scan_roots,
        excluded,
        include_images=hash_output_images,
    ):
        try:
            stat = path.stat()
        except (OSError, PermissionError) as exc:
            if len(unreadable) < 100:
                unreadable.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        if cutoff_utc is not None and mtime > cutoff_utc:
            if len(skipped_after_cutoff) < 100:
                skipped_after_cutoff.append(str(path))
            continue
        scanned_files += 1
        file_kind_counts[path.suffix.lower()] += 1
        try:
            size = stat.st_size
            scanned_bytes += size
            file_sha256 = sha256_file(path)
            mtime_text = mtime.isoformat().replace("+00:00", "Z")
            if file_sha256 == canonical_manifest_sha256:
                canonical_copy_exclusions.append(str(path))
                continue
            if path.suffix.lower() in IMAGE_SUFFIXES:
                hashed_image_files += 1
                hashed_image_bytes += size
                row = by_sha256.get(file_sha256)
                if row is not None:
                    exact_output_image_sha_hits += 1
                    record_hit(
                        row,
                        path=path,
                        line_number=None,
                        match_kind="output_image_sha256",
                        evidence_file_sha256=file_sha256,
                        size=size,
                        mtime_utc=mtime_text,
                    )
                continue
            scanned_text_files += 1
            with path.open("rb") as handle:
                for line_number, line in enumerate(handle, start=1):
                    matched: dict[str, set[str]] = defaultdict(set)
                    for raw_sha in SHA256_PATTERN.findall(line.lower()):
                        digest = raw_sha.decode("ascii")
                        row = by_sha256.get(digest)
                        if row is not None:
                            matched[row.sample_id].add("image_sha256")
                    for token in _sample_id_tokens(line, dataset_prefixes):
                        row = by_sample_id.get(token)
                        if row is not None:
                            matched[row.sample_id].add("sample_id")
                    for token in _exact_string_tokens(line):
                        family_row = by_source_family.get(token)
                        if family_row is not None:
                            matched[family_row.sample_id].add("source_family")
                        path_row = by_full_source_path.get(token)
                        if path_row is not None:
                            matched[path_row.sample_id].add("full_source_path")
                    for sample_id, match_kinds in matched.items():
                        match_kind = "+".join(
                            sorted(
                                match_kinds,
                                key=lambda value: MATCH_KIND_ORDER[value],
                            )
                        )
                        record_hit(
                            by_sample_id[sample_id],
                            path=path,
                            line_number=line_number,
                            match_kind=match_kind,
                            evidence_file_sha256=file_sha256,
                            size=size,
                            mtime_utc=mtime_text,
                        )
        except (OSError, PermissionError) as exc:
            if len(unreadable) < 100:
                unreadable.append(f"{path}: {type(exc).__name__}: {exc}")

    touched_rows = []
    for sample_id in sorted(evidence):
        row = by_sample_id[sample_id]
        touched_rows.append(
            {
                "sample_id": row.sample_id,
                "source_family": row.source_family,
                "sha256": row.sha256,
                "source_dataset": row.source_dataset,
                "domain": row.domain,
                "formal_split": row.split,
                "evidence_hit_count": int(hit_counts[sample_id]),
                "evidence": evidence[sample_id],
            }
        )
    touched_by_split = Counter(row["formal_split"] for row in touched_rows)
    touched_train_by_dataset = Counter(
        row["source_dataset"]
        for row in touched_rows
        if row["formal_split"] == "train"
    )
    untouched_train_by_dataset = Counter(
        row.source_dataset
        for row in rows
        if row.split == "train" and row.sample_id not in evidence
    )
    body: dict[str, Any] = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "assignment_schema_version": ASSIGNMENT_SCHEMA_VERSION,
        "audit_scope": (
            "exact sample_id/source_family/source-SHA/full-source-path scan over "
            "text evidence; optional exact output-image SHA scan; canonical "
            "inventory copies excluded; no image decoding, preview, or feature extraction"
        ),
        "source_validation_mode": source_validation_mode,
        "source_formal_config": str(source_config),
        "source_formal_config_sha256": sha256_file(source_config),
        "source_formal_manifest": str(source_manifest),
        "source_formal_manifest_sha256": sha256_file(source_manifest),
        "source_formal_manifest_lock": lock_audit,
        "scan_roots": [str(path.expanduser().resolve()) for path in scan_roots],
        "audit_cutoff_utc": (
            cutoff_utc.isoformat().replace("+00:00", "Z")
            if cutoff_utc is not None
            else None
        ),
        "excluded_paths": sorted(str(path) for path in excluded),
        "canonical_manifest_copy_exclusion_count": len(canonical_copy_exclusions),
        "canonical_manifest_copy_exclusions": sorted(canonical_copy_exclusions),
        "skipped_after_cutoff_count": len(skipped_after_cutoff),
        "skipped_after_cutoff_preview": skipped_after_cutoff,
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "scanned_text_files": scanned_text_files,
        "hash_output_images": hash_output_images,
        "hashed_image_files": hashed_image_files,
        "hashed_image_bytes": hashed_image_bytes,
        "exact_output_image_sha_hits": exact_output_image_sha_hits,
        "scanned_file_suffix_counts": dict(sorted(file_kind_counts.items())),
        "unreadable_file_count": len(unreadable),
        "unreadable_files_preview": unreadable,
        "touched_total": len(touched_rows),
        "touched_by_formal_split": dict(sorted(touched_by_split.items())),
        "touched_train_by_dataset": dict(sorted(touched_train_by_dataset.items())),
        "untouched_train_by_dataset": dict(
            sorted(untouched_train_by_dataset.items())
        ),
        "touched_rows": touched_rows,
    }
    body["ledger_payload_sha256"] = hashlib.sha256(
        _canonical_json(body).encode("utf-8")
    ).hexdigest()
    return body


def main() -> int:
    args = parse_args()
    output = Path(args.output).expanduser().resolve()
    payload = audit_history(
        Path(args.source),
        scan_roots=[Path(value) for value in args.scan_root],
        output_path=output,
        hash_output_images=bool(args.hash_output_images),
        allow_missing_source_files=bool(args.allow_missing_source_files),
        cutoff_utc=_parse_cutoff(args.cutoff_utc),
    )
    _atomic_write_json(output, payload)
    print(
        json.dumps(
            {
                "status": "created",
                "ledger": str(output),
                "ledger_sha256": sha256_file(output),
                "touched_total": payload["touched_total"],
                "touched_by_formal_split": payload["touched_by_formal_split"],
                "untouched_train_by_dataset": payload[
                    "untouched_train_by_dataset"
                ],
                "scanned_files": payload["scanned_files"],
                "scanned_bytes": payload["scanned_bytes"],
                "hashed_image_files": payload["hashed_image_files"],
                "exact_output_image_sha_hits": payload[
                    "exact_output_image_sha_hits"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
