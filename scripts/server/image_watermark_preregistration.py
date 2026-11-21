#!/usr/bin/env python3
"""Local preregistration evidence for image-watermark development protocols.

The claim written by this module is deliberately a *local* commit marker.  It
binds an unpredictable nonce to the frozen config, selected manifest, manifest
lock, and exact candidate run paths before any candidate directory exists.
Candidate executors copy the byte-identical claim into each fresh run, and the
analyzers independently validate both copies.

This cannot prove wall-clock ordering to an external verifier or prove that a
candidate was executed only once.  Those stronger properties require a trusted
append-only external anchor.  The explicit limitation is part of the claim so
the local evidence is not overstated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from protection.supporting.image_watermark.experiments.manifest import manifest_lock_path


CLAIM_SCHEMA_VERSION = "cogniguard_image_preregistration_claim_v1"
CLAIM_FILENAME_SUFFIX = ".preregistration.json"
RUN_COPY_FILENAME = "preregistration-claim.json"
NONCE_ENTROPY_BITS = 256
NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LOCAL_EVIDENCE_LIMITATION = (
    "local_commit_marker_only; external ordering and single-execution require "
    "a trusted append-only anchor"
)
RUN_CLASS_CONTRACT_KEYS = {
    "threshold_calibration_development_only": "threshold_calibration",
    "channel_vote_confirmation_development_only": "channel_vote_confirmation",
    "spatial_filter_calibration_development_only": "spatial_filter_calibration",
    "spatial_filter_confirmation_development_only": "spatial_filter_confirmation",
}


class PreregistrationError(RuntimeError):
    """Raised when preregistration evidence is missing, mutable, or inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_preregistration_nonce() -> str:
    """Return an unpredictable 256-bit nonce encoded as lowercase hex."""

    return secrets.token_hex(NONCE_ENTROPY_BITS // 8)


def validate_preregistration_nonce(value: object) -> str:
    if not isinstance(value, str) or NONCE_PATTERN.fullmatch(value) is None:
        raise PreregistrationError(
            "Preregistration nonce must be exactly 256 bits of lowercase hex."
        )
    return value


def claim_path_for_config(config_path: Path) -> Path:
    config_path = config_path.expanduser().resolve()
    return config_path.with_suffix(config_path.suffix + CLAIM_FILENAME_SUFFIX)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PreregistrationError(
            f"Preregistration config must be a regular non-symlink file: {path}"
        )
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise PreregistrationError(f"Invalid preregistration config: {path}") from exc
    if not isinstance(payload, dict):
        raise PreregistrationError("Preregistration config root must be a mapping.")
    return payload


def _read_json_mapping(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise PreregistrationError(
            f"{label} must be a regular non-symlink file: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreregistrationError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise PreregistrationError(f"{label} must be a JSON object: {path}")
    return payload


def _validate_relative_candidate_paths(values: object) -> tuple[str, ...]:
    if not isinstance(values, list) or not values:
        raise PreregistrationError(
            "Preregistration must declare at least one candidate run path."
        )
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise PreregistrationError(
                "Preregistration candidate run paths must be non-empty strings."
            )
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or value != path.as_posix()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise PreregistrationError(
                f"Unsafe preregistration candidate run path: {value!r}"
            )
        normalized.append(value)
    if len(set(normalized)) != len(normalized):
        raise PreregistrationError(
            "Preregistration candidate run paths must be unique."
        )
    return tuple(normalized)


def build_preregistration_contract(
    *,
    config_path: Path,
    nonce: str,
    expected_candidate_run_relative_paths: Sequence[str],
) -> dict[str, Any]:
    """Build the config-embedded half of the preregistration protocol."""

    nonce = validate_preregistration_nonce(nonce)
    relative_paths = _validate_relative_candidate_paths(
        list(expected_candidate_run_relative_paths)
    )
    claim_path = claim_path_for_config(config_path)
    return {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "nonce": nonce,
        "nonce_entropy_bits": NONCE_ENTROPY_BITS,
        "claim_path": str(claim_path),
        "expected_candidate_run_relative_paths": list(relative_paths),
        "claim_required_before_candidate_execution": True,
        "candidate_artifacts_preexisting_at_claim": False,
        "external_append_only_anchor_present": False,
        "evidence_limitation": LOCAL_EVIDENCE_LIMITATION,
    }


def validate_preregistration_contract(
    contract: Mapping[str, Any],
    *,
    config_path: Path,
) -> dict[str, Any]:
    """Strictly validate a config-embedded preregistration declaration."""

    if not isinstance(contract, Mapping):
        raise PreregistrationError("Preregistration contract must be a mapping.")
    expected_keys = {
        "schema_version",
        "nonce",
        "nonce_entropy_bits",
        "claim_path",
        "expected_candidate_run_relative_paths",
        "claim_required_before_candidate_execution",
        "candidate_artifacts_preexisting_at_claim",
        "external_append_only_anchor_present",
        "evidence_limitation",
    }
    if set(contract) != expected_keys:
        raise PreregistrationError(
            "Preregistration contract fields differ from the frozen schema."
        )
    nonce = validate_preregistration_nonce(contract.get("nonce"))
    config_path = config_path.expanduser().resolve()
    expected_claim_path = claim_path_for_config(config_path)
    raw_claim_path = contract.get("claim_path")
    if not isinstance(raw_claim_path, str) or Path(raw_claim_path).expanduser().resolve() != expected_claim_path:
        raise PreregistrationError(
            "Preregistration claim path is not the config-adjacent frozen path."
        )
    relative_paths = _validate_relative_candidate_paths(
        contract.get("expected_candidate_run_relative_paths")
    )
    if (
        contract.get("schema_version") != CLAIM_SCHEMA_VERSION
        or contract.get("nonce_entropy_bits") != NONCE_ENTROPY_BITS
        or contract.get("claim_required_before_candidate_execution") is not True
        or contract.get("candidate_artifacts_preexisting_at_claim") is not False
        or contract.get("external_append_only_anchor_present") is not False
        or contract.get("evidence_limitation") != LOCAL_EVIDENCE_LIMITATION
    ):
        raise PreregistrationError(
            "Preregistration contract differs from the frozen local-claim protocol."
        )
    return {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "nonce": nonce,
        "claim_path": str(expected_claim_path),
        "expected_candidate_run_relative_paths": list(relative_paths),
    }


def _resolve_protocol(
    config_path: Path,
    *,
    expected_run_class: str | None = None,
) -> tuple[dict[str, Any], str, str, dict[str, Any]]:
    config_path = config_path.expanduser().resolve()
    payload = _read_yaml_mapping(config_path)
    experiment = payload.get("experiment") or {}
    if not isinstance(experiment, dict):
        raise PreregistrationError("Experiment declaration must be a mapping.")
    run_class = experiment.get("run_class")
    if not isinstance(run_class, str) or run_class not in RUN_CLASS_CONTRACT_KEYS:
        raise PreregistrationError(
            f"Unsupported preregistration run class: {run_class!r}"
        )
    if expected_run_class is not None and run_class != expected_run_class:
        raise PreregistrationError(
            f"Preregistration run class mismatch: expected {expected_run_class!r}, "
            f"observed {run_class!r}."
        )
    contract_key = RUN_CLASS_CONTRACT_KEYS[run_class]
    protocol_contract = payload.get(contract_key) or {}
    if not isinstance(protocol_contract, dict):
        raise PreregistrationError(
            f"Config has no valid {contract_key!r} protocol contract."
        )
    preregistration = validate_preregistration_contract(
        protocol_contract.get("preregistration_claim") or {},
        config_path=config_path,
    )
    return payload, run_class, contract_key, preregistration


def _claim_payload(
    config_path: Path,
    *,
    payload: Mapping[str, Any],
    run_class: str,
    contract_key: str,
    preregistration: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_root = config_path.parent.resolve()
    manifest_cfg = payload.get("manifest") or {}
    if not isinstance(manifest_cfg, Mapping):
        raise PreregistrationError("Manifest declaration must be a mapping.")
    raw_manifest_path = manifest_cfg.get("path")
    if not isinstance(raw_manifest_path, str) or not raw_manifest_path:
        raise PreregistrationError("Config does not declare a manifest path.")
    manifest_path = Path(raw_manifest_path).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = config_path.parent / manifest_path
    manifest_path = manifest_path.resolve()
    lock_path = manifest_lock_path(manifest_path)
    if manifest_path.parent != bundle_root or lock_path.parent != bundle_root:
        raise PreregistrationError(
            "Preregistration manifest and lock must be adjacent to the frozen config."
        )
    for path, label in (
        (manifest_path, "selected manifest"),
        (lock_path, "selected manifest lock"),
    ):
        if not path.is_file() or path.is_symlink():
            raise PreregistrationError(
                f"Preregistration {label} must be a regular non-symlink file: {path}"
            )
    return {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "run_class": run_class,
        "contract_key": contract_key,
        "nonce": preregistration["nonce"],
        "bundle_root": str(bundle_root),
        "config": {
            "path": str(config_path),
            "sha256": sha256_file(config_path),
        },
        "manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
        },
        "manifest_lock": {
            "path": str(lock_path),
            "sha256": sha256_file(lock_path),
        },
        "expected_candidate_run_relative_paths": list(
            preregistration["expected_candidate_run_relative_paths"]
        ),
        "claim_committed_before_candidate_execution": True,
        "external_append_only_anchor_present": False,
        "evidence_limitation": LOCAL_EVIDENCE_LIMITATION,
    }


def _assert_candidate_roots_absent(
    bundle_root: Path,
    relative_paths: Sequence[str],
) -> None:
    checked_roots: set[Path] = set()
    for value in relative_paths:
        relative = PurePosixPath(value)
        candidate_root = bundle_root / relative.parts[0]
        if candidate_root in checked_roots:
            continue
        checked_roots.add(candidate_root)
        if _lexists(candidate_root):
            raise PreregistrationError(
                "Refusing to commit preregistration after a candidate root already "
                f"exists: {candidate_root}"
            )


def _exclusive_write_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise PreregistrationError(
            f"Refusing to overwrite preregistration evidence: {path}"
        ) from exc
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def write_preregistration_claim(
    config_path: Path,
    *,
    expected_run_class: str,
) -> dict[str, Any]:
    """Commit a fresh claim after config/manifest/lock, before candidate roots."""

    config_path = config_path.expanduser().resolve()
    payload, run_class, contract_key, preregistration = _resolve_protocol(
        config_path,
        expected_run_class=expected_run_class,
    )
    claim_path = Path(preregistration["claim_path"]).resolve()
    if _lexists(claim_path):
        raise PreregistrationError(
            f"Refusing to overwrite preregistration claim: {claim_path}"
        )
    _assert_candidate_roots_absent(
        config_path.parent,
        preregistration["expected_candidate_run_relative_paths"],
    )
    claim = _claim_payload(
        config_path,
        payload=payload,
        run_class=run_class,
        contract_key=contract_key,
        preregistration=preregistration,
    )
    _exclusive_write_bytes(claim_path, _canonical_json(claim).encode("utf-8"))
    return validate_preregistration_claim(
        config_path,
        claim_path=claim_path,
        expected_run_class=expected_run_class,
    )


def validate_preregistration_claim(
    config_path: Path,
    *,
    claim_path: Path | None = None,
    expected_run_class: str | None = None,
    expected_nonce: str | None = None,
    expected_candidate_run: Path | None = None,
) -> dict[str, Any]:
    """Validate the source claim or a byte-identical candidate-run copy."""

    config_path = config_path.expanduser().resolve()
    payload, run_class, contract_key, preregistration = _resolve_protocol(
        config_path,
        expected_run_class=expected_run_class,
    )
    nonce = preregistration["nonce"]
    if expected_nonce is not None and validate_preregistration_nonce(expected_nonce) != nonce:
        raise PreregistrationError(
            "Runtime preregistration nonce differs from the frozen config."
        )
    source_claim_path = Path(preregistration["claim_path"]).resolve()
    source_claim = _read_json_mapping(
        source_claim_path,
        label="source preregistration claim",
    )
    expected_claim = _claim_payload(
        config_path,
        payload=payload,
        run_class=run_class,
        contract_key=contract_key,
        preregistration=preregistration,
    )
    if source_claim != expected_claim:
        raise PreregistrationError(
            "Source preregistration claim differs from the current frozen bundle."
        )
    source_claim_sha256 = sha256_file(source_claim_path)
    evidence_path = (
        claim_path.expanduser().resolve()
        if claim_path is not None
        else source_claim_path
    )
    evidence_claim = _read_json_mapping(
        evidence_path,
        label="candidate preregistration claim",
    )
    if evidence_claim != source_claim or sha256_file(evidence_path) != source_claim_sha256:
        raise PreregistrationError(
            "Candidate preregistration claim is not byte-identical to the source claim."
        )

    candidate_relative_path: str | None = None
    if expected_candidate_run is not None:
        candidate_run = expected_candidate_run.expanduser().resolve()
        matches = [
            value
            for value in preregistration["expected_candidate_run_relative_paths"]
            if (config_path.parent / PurePosixPath(value)).resolve() == candidate_run
        ]
        if len(matches) != 1:
            raise PreregistrationError(
                "Candidate run directory is not one of the preregistered paths: "
                f"{candidate_run}"
            )
        candidate_relative_path = matches[0]

    return {
        "schema_version": CLAIM_SCHEMA_VERSION,
        "run_class": run_class,
        "nonce": nonce,
        "claim_path": str(evidence_path),
        "claim_sha256": source_claim_sha256,
        "source_claim_path": str(source_claim_path),
        "source_claim_sha256": source_claim_sha256,
        "config_sha256": expected_claim["config"]["sha256"],
        "manifest_sha256": expected_claim["manifest"]["sha256"],
        "manifest_lock_sha256": expected_claim["manifest_lock"]["sha256"],
        "expected_candidate_run_relative_paths": list(
            preregistration["expected_candidate_run_relative_paths"]
        ),
        "candidate_run_relative_path": candidate_relative_path,
        "claim_committed_before_candidate_execution": True,
        "external_append_only_anchor_present": False,
        "evidence_limitation": LOCAL_EVIDENCE_LIMITATION,
    }


def copy_preregistration_claim_to_run(
    config_path: Path,
    *,
    source_claim_path: Path,
    destination_run: Path,
    expected_run_class: str,
    expected_nonce: str,
) -> dict[str, Any]:
    """Copy a validated claim into an already-created, fresh candidate directory."""

    destination_run = destination_run.expanduser().resolve()
    if not destination_run.is_dir() or destination_run.is_symlink():
        raise PreregistrationError(
            f"Candidate destination must be a fresh non-symlink directory: {destination_run}"
        )
    validate_preregistration_claim(
        config_path,
        claim_path=source_claim_path,
        expected_run_class=expected_run_class,
        expected_nonce=expected_nonce,
        expected_candidate_run=destination_run,
    )
    destination = destination_run / RUN_COPY_FILENAME
    _exclusive_write_bytes(destination, source_claim_path.resolve().read_bytes())
    try:
        destination.chmod(0o444)
    except OSError:
        pass
    return validate_preregistration_claim(
        config_path,
        claim_path=destination,
        expected_run_class=expected_run_class,
        expected_nonce=expected_nonce,
        expected_candidate_run=destination_run,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "copy"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True)
        subparser.add_argument("--claim", required=True)
        subparser.add_argument("--run-class", required=True)
        subparser.add_argument("--nonce", required=True)
        subparser.add_argument("--candidate-run", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "copy":
        evidence = copy_preregistration_claim_to_run(
            Path(args.config),
            source_claim_path=Path(args.claim),
            destination_run=Path(args.candidate_run),
            expected_run_class=args.run_class,
            expected_nonce=args.nonce,
        )
    else:
        evidence = validate_preregistration_claim(
            Path(args.config),
            claim_path=Path(args.claim),
            expected_run_class=args.run_class,
            expected_nonce=args.nonce,
            expected_candidate_run=Path(args.candidate_run),
        )
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
