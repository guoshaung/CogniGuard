"""Fail-closed preflight for the pinned official Watermark Anything baseline."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from protection.supporting.image_watermark.official_baselines.wam_official_contract import (
    OFFICIAL_WAM_MIT,
    WamPinnedContract,
    pinned_provenance,
    validate_contract,
)


class WamPreflightError(RuntimeError):
    """Raised when a WAM installation does not match the pinned contract."""


@dataclass(frozen=True)
class DependencyPin:
    distribution: str
    import_name: str
    version: str | None


DEPENDENCY_PINS: tuple[DependencyPin, ...] = (
    DependencyPin("torch", "torch", "2.5.1"),
    DependencyPin("torchvision", "torchvision", "0.20.1"),
    DependencyPin("omegaconf", "omegaconf", "2.3.0"),
    DependencyPin("einops", "einops", "0.8.0"),
    DependencyPin("pycocotools", "pycocotools", "2.0.8"),
    DependencyPin("timm", "timm", "1.0.11"),
    DependencyPin("opencv-python", "cv2", "4.10.0.84"),
    DependencyPin("lpips", "lpips", "0.1.4"),
    DependencyPin("scikit-image", "skimage", "0.24.0"),
    DependencyPin("scikit-learn", "sklearn", "1.5.2"),
    DependencyPin("numpy", "numpy", "1.26.4"),
    DependencyPin("Pillow", "PIL", "10.4.0"),
    DependencyPin("PyYAML", "yaml", None),
)

REQUIRED_REPOSITORY_FILES: tuple[str, ...] = (
    "LICENSE",
    "configs/all_augs_multi_wm.yaml",
    "configs/attenuation.yaml",
    "configs/embedder.yaml",
    "configs/extractor.yaml",
    "watermark_anything/augmentation/augmenter.py",
    "watermark_anything/models/__init__.py",
    "watermark_anything/models/wam.py",
    "watermark_anything/modules/jnd.py",
    "watermark_anything/data/metrics.py",
    "watermark_anything/data/transforms.py",
)

_DEVICE_PATTERN = re.compile(r"(?:cpu|cuda(?::(?P<index>0|[1-9][0-9]*))?)\Z")


def sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise WamPreflightError(f"git {' '.join(args)} failed: {exc}") from exc
    return completed.stdout.strip()


def _base_version(version: str) -> str:
    return version.split("+", 1)[0]


def _device_index(device: str) -> int | None:
    """Validate the deliberately small WAM device boundary."""

    match = _DEVICE_PATTERN.fullmatch(device)
    if match is None:
        raise WamPreflightError(
            "device must be exactly 'cpu', 'cuda', or 'cuda:<non-negative-index>'."
        )
    if device == "cpu":
        return None
    value = match.group("index")
    return 0 if value is None else int(value)


def _add_check(
    report: dict[str, Any], name: str, passed: bool, detail: str, **evidence: Any
) -> None:
    item: dict[str, Any] = {
        "name": name,
        "passed": bool(passed),
        "detail": detail,
    }
    if evidence:
        item["evidence"] = evidence
    report["checks"].append(item)
    if not passed:
        report["ready"] = False


def _check_dependencies(report: dict[str, Any], *, device: str) -> None:
    versions: dict[str, str | None] = {}
    modules: dict[str, Any] = {}
    for pin in DEPENDENCY_PINS:
        try:
            installed = importlib.metadata.version(pin.distribution)
            module = importlib.import_module(pin.import_name)
            modules[pin.import_name] = module
        except Exception as exc:  # import failures are readiness failures
            versions[pin.distribution] = None
            _add_check(
                report,
                f"dependency:{pin.distribution}",
                False,
                f"missing or not importable: {type(exc).__name__}: {exc}",
                required_version=pin.version,
            )
            continue
        versions[pin.distribution] = installed
        matches = pin.version is None or _base_version(installed) == pin.version
        _add_check(
            report,
            f"dependency:{pin.distribution}",
            matches,
            "installed and importable"
            if matches
            else "version differs from official pin",
            installed_version=installed,
            required_version=pin.version,
        )

    report["runtime"]["dependencies"] = versions
    torch_module = modules.get("torch")
    if device.startswith("cuda"):
        try:
            requested_index = _device_index(device)
        except WamPreflightError:
            return
        cuda_available = bool(
            torch_module is not None and torch_module.cuda.is_available()
        )
        device_count = int(torch_module.cuda.device_count()) if cuda_available else 0
        index_available = bool(
            cuda_available
            and requested_index is not None
            and requested_index < device_count
        )
        _add_check(
            report,
            "runtime:cuda",
            index_available,
            "requested CUDA device is available"
            if index_available
            else "requested CUDA device is unavailable",
            requested_device=device,
            requested_index=requested_index,
            device_count=device_count,
        )
        if index_available:
            report["runtime"]["cuda_version"] = torch_module.version.cuda
            report["runtime"]["cuda_device_name"] = torch_module.cuda.get_device_name(
                requested_index
            )
            report["runtime"]["resolved_device"] = f"cuda:{requested_index}"
    else:
        report["runtime"]["resolved_device"] = "cpu"


def run_preflight(
    repo_root: str | Path,
    checkpoint_path: str | Path,
    *,
    device: str = "cuda",
    check_dependencies: bool = True,
    contract: WamPinnedContract = OFFICIAL_WAM_MIT,
) -> dict[str, Any]:
    """Audit a local checkout and checkpoint without loading pickle weights.

    The public/default path is permanently pinned to :data:`OFFICIAL_WAM_MIT`.
    ``contract`` exists so the validator can be tested with tiny fixtures; the
    production backend never exposes an override.
    """

    validate_contract(contract)
    try:
        _device_index(device)
    except WamPreflightError as exc:
        device_error = str(exc)
    else:
        device_error = None
    repo = Path(repo_root).expanduser().resolve()
    checkpoint = Path(checkpoint_path).expanduser().resolve()
    params = repo / contract.params_relative_path
    report: dict[str, Any] = {
        "schema_version": "cogniguard.wam.preflight.v1",
        "ready": True,
        "provenance": (
            pinned_provenance()
            if contract == OFFICIAL_WAM_MIT
            else {
                "official_release": contract.to_dict(),
                "fixture_contract": True,
            }
        ),
        "runtime": {
            "python": sys.version.split()[0],
            "device_requested": device,
        },
        "artifacts": {
            "repository_root": str(repo),
            "checkpoint_path": str(checkpoint),
            "params_path": str(params),
        },
        "checks": [],
    }

    _add_check(
        report,
        "runtime:device_syntax",
        device_error is None,
        "device syntax is within the audited boundary"
        if device_error is None
        else device_error,
        requested_device=device,
    )

    _add_check(report, "repository:exists", repo.is_dir(), "repository directory")
    if repo.is_dir():
        try:
            head = _git(repo, "rev-parse", "HEAD")
            _add_check(
                report,
                "repository:commit",
                head == contract.repository_commit,
                "checkout commit matches pin"
                if head == contract.repository_commit
                else "commit mismatch",
                actual=head,
                expected=contract.repository_commit,
            )
            dirty = _git(repo, "status", "--porcelain", "--untracked-files=all")
            _add_check(
                report,
                "repository:tracked_and_untracked_files_clean",
                dirty == "",
                "checkout contains only pinned tracked files"
                if dirty == ""
                else "checkout is modified or contains untracked shadow files",
                porcelain=dirty.splitlines(),
            )
            # Retain the old machine-readable name for downstream audit readers,
            # while making it clear that the stronger check includes untracked files.
            _add_check(
                report,
                "repository:tracked_files_clean",
                dirty == "",
                "tracked files are unchanged and no untracked files exist"
                if dirty == ""
                else "tracked changes or untracked files detected",
            )
            report["artifacts"]["repository_commit"] = head
        except WamPreflightError as exc:
            _add_check(report, "repository:git_metadata", False, str(exc))

        missing_repo_files = [
            relative
            for relative in REQUIRED_REPOSITORY_FILES
            if not (repo / relative).is_file()
        ]
        _add_check(
            report,
            "repository:required_files",
            not missing_repo_files,
            "all pinned inference files exist"
            if not missing_repo_files
            else "files missing",
            missing=missing_repo_files,
        )
        if not missing_repo_files:
            report["artifacts"]["repository_source_sha256"] = {
                relative: sha256_file(repo / relative)
                for relative in REQUIRED_REPOSITORY_FILES
            }

        license_path = repo / "LICENSE"
        if license_path.is_file():
            license_text = license_path.read_text(encoding="utf-8", errors="replace")
            is_mit = "MIT License" in license_text
            _add_check(
                report,
                "repository:license",
                is_mit and contract.checkpoint_license == "MIT",
                "MIT repository/checkpoint variant"
                if is_mit
                else "MIT license text missing",
                declared_checkpoint_license=contract.checkpoint_license,
                license_sha256=sha256_file(license_path),
            )

    _add_check(
        report,
        "checkpoint:exists",
        checkpoint.is_file(),
        "checkpoint file exists"
        if checkpoint.is_file()
        else "checkpoint file is missing",
    )
    if checkpoint.is_file():
        actual_size = checkpoint.stat().st_size
        _add_check(
            report,
            "checkpoint:bytes",
            actual_size == contract.checkpoint_bytes,
            "checkpoint byte count matches"
            if actual_size == contract.checkpoint_bytes
            else "byte count mismatch",
            actual=actual_size,
            expected=contract.checkpoint_bytes,
        )
        actual_checkpoint_sha = sha256_file(checkpoint)
        _add_check(
            report,
            "checkpoint:sha256",
            actual_checkpoint_sha == contract.checkpoint_sha256,
            "checkpoint SHA256 matches"
            if actual_checkpoint_sha == contract.checkpoint_sha256
            else "SHA256 mismatch",
            actual=actual_checkpoint_sha,
            expected=contract.checkpoint_sha256,
        )
        report["artifacts"]["checkpoint_bytes"] = actual_size
        report["artifacts"]["checkpoint_sha256"] = actual_checkpoint_sha

    _add_check(
        report,
        "params:exists",
        params.is_file(),
        "params.json exists" if params.is_file() else "params.json is missing",
    )
    if params.is_file():
        actual_params_sha = sha256_file(params)
        _add_check(
            report,
            "params:sha256",
            actual_params_sha == contract.params_sha256,
            "params SHA256 matches"
            if actual_params_sha == contract.params_sha256
            else "params SHA256 mismatch",
            actual=actual_params_sha,
            expected=contract.params_sha256,
        )
        try:
            params_payload = json.loads(params.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _add_check(report, "params:json", False, f"invalid JSON: {exc}")
        else:
            expected_fields = {
                "nbits": contract.message_bits,
                "scaling_w": contract.scaling_w,
                "scaling_i": contract.scaling_i,
                "img_size_extractor": contract.detector_size,
            }
            actual_fields = {name: params_payload.get(name) for name in expected_fields}
            _add_check(
                report,
                "params:native_semantics",
                actual_fields == expected_fields,
                "32-bit/1+32-channel runtime parameters are pinned"
                if actual_fields == expected_fields
                else "runtime parameters differ from the pinned native semantics",
                actual=actual_fields,
                expected=expected_fields,
                detector_channels=contract.detector_channels,
                detection_channels=contract.watermark_detection_channels,
                message_channels=contract.message_logit_channels,
            )
            config_paths = [
                params_payload.get(name)
                for name in (
                    "embedder_config",
                    "augmentation_config",
                    "extractor_config",
                    "attenuation_config",
                )
            ]
            missing_configs = [
                str(relative)
                for relative in config_paths
                if not isinstance(relative, str) or not (repo / relative).is_file()
            ]
            _add_check(
                report,
                "params:referenced_configs",
                not missing_configs,
                "all referenced configs exist"
                if not missing_configs
                else "referenced configs missing",
                missing=missing_configs,
            )

    if check_dependencies:
        _check_dependencies(report, device=device)
    else:
        report["runtime"]["dependency_check"] = "skipped_by_caller"

    report["ready"] = bool(
        report["ready"] and all(check["passed"] for check in report["checks"])
    )
    return report


def require_ready(report: dict[str, Any]) -> None:
    """Raise rather than allowing a caller to run an unverified baseline."""

    if report.get("ready") is True:
        return
    failed = [
        check.get("name", "unknown")
        for check in report.get("checks", [])
        if not check.get("passed")
    ]
    raise WamPreflightError(
        "Official WAM preflight failed closed: " + ", ".join(failed or ["unknown"])
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--skip-dependency-check",
        action="store_true",
        help="Audit artifacts only. The inference backend never uses this bypass.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_preflight(
        args.repo_root,
        args.checkpoint,
        device=args.device,
        check_dependencies=not args.skip_dependency_check,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output_json:
        output = args.output_json.expanduser().resolve()
        if output.exists():
            raise WamPreflightError(
                f"Refusing to overwrite preflight evidence: {output}"
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp-{uuid.uuid4().hex}")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        os.replace(temporary, output)
    print(rendered)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
