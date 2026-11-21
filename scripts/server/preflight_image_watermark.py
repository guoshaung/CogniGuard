#!/usr/bin/env python3
"""Fail-fast deployment checks for the CogniGuard image-watermark service.

The check is deliberately read-only apart from the optional JSON report.  It
does not download models, modify checkpoints, or print the registry secret.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_MANIFEST = (
    PROJECT_ROOT / "deploy" / "image_watermark" / "assets.manifest.example.json"
)
DEFAULT_MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-inpainting"
HF_COMMIT_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
# Minimal offline snapshot consumed by load_diffusers_pipe when it requests
# variant="fp16", use_safetensors=True, and disables the safety checker.  Keep
# this list explicit: component directories alone do not prove that the LFS
# blobs were downloaded successfully.
INPAINTING_FP16_REQUIRED_FILES = (
    "config.json",
    "feature_extractor/preprocessor_config.json",
    "model_index.json",
    "scheduler/scheduler_config.json",
    "text_encoder/config.json",
    "text_encoder/model.fp16.safetensors",
    "tokenizer/merges.txt",
    "tokenizer/special_tokens_map.json",
    "tokenizer/tokenizer_config.json",
    "tokenizer/vocab.json",
    "unet/config.json",
    "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.fp16.safetensors",
)
PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "changeme",
    "replace-me",
    "replace_with_a_random_secret",
    "your-secret-here",
}


class CheckReport:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def add(self, name: str, status: str, message: str, **details: Any) -> None:
        if status not in {"pass", "warning", "error"}:
            raise ValueError(f"Unsupported status: {status}")
        row: dict[str, Any] = {"name": name, "status": status, "message": message}
        if details:
            row["details"] = details
        self.checks.append(row)

    @property
    def errors(self) -> int:
        return sum(row["status"] == "error" for row in self.checks)

    @property
    def warnings(self) -> int:
        return sum(row["status"] == "warning" for row in self.checks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a Linux/GPU host before running the image-watermark API or benchmark."
    )
    parser.add_argument(
        "--project-root",
        default=os.environ.get("SCE_LOCGUARD_PROJECT_ROOT", str(PROJECT_ROOT)),
        help="Absolute CogniGuard checkout path visible to the API and benchmark processes.",
    )
    parser.add_argument(
        "--shared-root",
        default=os.environ.get("COGNIGUARD_SHARED_ROOT", ""),
        help="Shared mount containing the checkout, outputs, and (normally) datasets.",
    )
    parser.add_argument(
        "--output-root",
        default=os.environ.get("SCE_LOCGUARD_OUTPUT_DIR", ""),
        help="Job artifact directory; defaults to <project>/var/outputs/sce_locguard_jobs.",
    )
    parser.add_argument(
        "--asset-manifest",
        default=os.environ.get(
            "COGNIGUARD_WATERMARK_ASSET_MANIFEST", str(DEFAULT_ASSET_MANIFEST)
        ),
        help="JSON file containing relative asset paths and expected SHA-256 digests.",
    )
    parser.add_argument(
        "--benchmark-config",
        default=os.environ.get("COGNIGUARD_WATERMARK_BENCHMARK_CONFIG", ""),
        help="Optional benchmark YAML; dataset roots and a manifest path are discovered from it.",
    )
    parser.add_argument(
        "--expected-api-url",
        default=os.environ.get("SCE_LOCGUARD_BASE_URL", ""),
        help="Require the enabled editguard_wrapper.base_url in the benchmark YAML to match this URL.",
    )
    parser.add_argument(
        "--dataset-manifest",
        default=os.environ.get("COGNIGUARD_WATERMARK_DATASET_MANIFEST", ""),
        help="Portable JSONL image manifest. Overrides a path discovered from --benchmark-config.",
    )
    parser.add_argument(
        "--dataset-root",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Dataset root mapping; repeat for every source_dataset. Overrides YAML/environment mappings.",
    )
    parser.add_argument(
        "--hf-cache",
        default=os.environ.get("HF_HOME", ""),
        help="Offline Hugging Face cache used by the service; defaults to <project>/assets/models/hf_cache.",
    )
    parser.add_argument(
        "--model-id",
        default=os.environ.get("SCE_LOCGUARD_INPAINT_MODEL_ID", DEFAULT_MODEL_ID),
    )
    parser.add_argument(
        "--model-revision",
        default=os.environ.get("SCE_LOCGUARD_INPAINT_MODEL_REVISION", ""),
        help="Exact cached Hugging Face snapshot commit required for formal runs.",
    )
    parser.add_argument(
        "--secret-file",
        default=os.environ.get("SCE_LOCGUARD_REGISTRY_SECRET_FILE", ""),
        help="Optional mode-0600 file containing the registry HMAC secret. Its content is never reported.",
    )
    parser.add_argument("--min-dataset-samples", type=int, default=1)
    parser.add_argument("--min-test-samples", type=int, default=1)
    parser.add_argument("--min-source-datasets", type=int, default=1)
    parser.add_argument("--min-content-domains", type=int, default=1)
    parser.add_argument("--require-linux", action="store_true")
    parser.add_argument("--require-cuda", action="store_true")
    parser.add_argument("--require-secret", action="store_true")
    parser.add_argument("--require-shared-root", action="store_true")
    parser.add_argument("--require-asset-hashes", action="store_true")
    parser.add_argument("--require-hf-cache", action="store_true")
    parser.add_argument("--require-dataset-files", action="store_true")
    parser.add_argument("--require-license-metadata", action="store_true")
    parser.add_argument("--require-deterministic", action="store_true")
    parser.add_argument("--skip-package-check", action="store_true")
    parser.add_argument(
        "--output-json",
        default="",
        help="Write the complete check report to this path.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print only JSON (useful in CI/Slurm logs)."
    )
    return parser.parse_args(argv)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _expand_path(value: str, *, base: Path | None = None) -> Path:
    expanded = Path(os.path.expandvars(value)).expanduser()
    if not expanded.is_absolute() and base is not None:
        expanded = base / expanded
    return expanded.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_platform(args: argparse.Namespace, report: CheckReport) -> None:
    is_linux = platform.system() == "Linux"
    linux_status = (
        "pass" if is_linux else ("error" if args.require_linux else "warning")
    )
    report.add(
        "platform.linux",
        linux_status,
        "Linux host detected."
        if is_linux
        else "This deployment bundle targets Linux; current host is not Linux.",
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
    )
    supported_python = (3, 10) <= sys.version_info[:2] < (3, 13)
    report.add(
        "runtime.python",
        "pass" if supported_python else "error",
        "Python version is inside the supported 3.10-3.12 deployment range."
        if supported_python
        else "Use Python 3.10, 3.11, or 3.12 for the legacy EditGuard and diffusion dependency stack.",
        version=platform.python_version(),
        executable=sys.executable,
    )


def check_paths(
    args: argparse.Namespace, project_root: Path, report: CheckReport
) -> tuple[Path | None, Path]:
    required_project_entries = [
        project_root / 'protection' / 'image_watermark' / "api" / "server.py",
        project_root / 'third_party' / 'editguard' / "options" / "test_editguard.yml",
        project_root / 'assets' / 'checkpoints' / "clean.pth",
    ]
    missing = [str(path) for path in required_project_entries if not path.exists()]
    report.add(
        "paths.project_root",
        "error" if missing else "pass",
        "Project root contains the API, EditGuard config, and primary checkpoint."
        if not missing
        else "Project checkout is incomplete for real watermark inference.",
        project_root=str(project_root),
        missing=missing,
    )

    output_root = (
        _expand_path(args.output_root, base=project_root)
        if args.output_root
        else (project_root / 'var' / 'outputs' / "sce_locguard_jobs").resolve()
    )
    output_parent = output_root if output_root.exists() else output_root.parent
    while not output_parent.exists() and output_parent != output_parent.parent:
        output_parent = output_parent.parent
    writable = output_parent.exists() and os.access(output_parent, os.W_OK)
    report.add(
        "paths.output_root",
        "pass" if writable else "error",
        "Output path exists or has a writable parent."
        if writable
        else "Output path has no writable parent.",
        output_root=str(output_root),
        checked_parent=str(output_parent),
    )

    shared_root: Path | None = None
    if args.shared_root:
        shared_root = _expand_path(args.shared_root)
        valid = (
            shared_root.is_dir()
            and _is_relative_to(project_root, shared_root)
            and _is_relative_to(output_root, shared_root)
        )
        report.add(
            "paths.shared_root_contract",
            "pass" if valid else "error",
            "Project and output paths are inside the configured shared root."
            if valid
            else "Shared root must exist and contain both project and output paths.",
            shared_root=str(shared_root),
            project_root=str(project_root),
            output_root=str(output_root),
        )
    else:
        status = "error" if args.require_shared_root else "warning"
        report.add(
            "paths.shared_root_contract",
            status,
            "COGNIGUARD_SHARED_ROOT is not configured; cross-process path visibility cannot be checked.",
        )
    return shared_root, output_root


def check_secret(args: argparse.Namespace, report: CheckReport) -> None:
    env_secret = os.environ.get("SCE_LOCGUARD_REGISTRY_SECRET", "").strip()
    file_secret = ""
    secret_file: Path | None = None
    if args.secret_file:
        secret_file = _expand_path(args.secret_file)
        if not secret_file.is_file():
            report.add(
                "security.secret_file",
                "error",
                "Configured registry secret file does not exist.",
                path=str(secret_file),
            )
        else:
            try:
                file_secret = secret_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                report.add(
                    "security.secret_file",
                    "error",
                    f"Cannot read registry secret file: {exc}",
                    path=str(secret_file),
                )
            else:
                mode_ok = True
                if os.name == "posix":
                    mode = stat.S_IMODE(secret_file.stat().st_mode)
                    mode_ok = mode & 0o077 == 0
                    report.add(
                        "security.secret_file_permissions",
                        "pass" if mode_ok else "error",
                        "Registry secret file permissions do not expose group/other bits."
                        if mode_ok
                        else "Registry secret file must be mode 0600 (or stricter).",
                        path=str(secret_file),
                        mode=oct(mode),
                    )
    if env_secret and file_secret and env_secret != file_secret:
        report.add(
            "security.secret_consistency",
            "error",
            "Environment and file registry secrets differ; use exactly one authoritative value.",
        )
    secret = env_secret or file_secret
    secret_valid = len(secret) >= 32 and secret.lower() not in PLACEHOLDER_SECRETS
    status = "pass" if secret_valid else ("error" if args.require_secret else "warning")
    report.add(
        "security.registry_secret",
        status,
        "A non-placeholder registry secret of at least 32 characters is configured."
        if secret_valid
        else "Configure a random registry secret of at least 32 characters outside the repository.",
        configured=bool(secret),
        source="environment" if env_secret else ("file" if file_secret else "none"),
        minimum_length=32,
    )

    deterministic = os.environ.get(
        "SCE_LOCGUARD_DETERMINISTIC", ""
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    cublas_configured = os.environ.get("CUBLAS_WORKSPACE_CONFIG") in {
        ":4096:8",
        ":16:8",
    }
    python_hash_seed = os.environ.get("PYTHONHASHSEED", "").strip()
    deterministic_contract = (
        deterministic and cublas_configured and python_hash_seed.isdigit()
    )
    report.add(
        "runtime.deterministic_mode",
        "pass"
        if deterministic_contract
        else ("error" if args.require_deterministic else "warning"),
        "Deterministic mode, cuBLAS workspace, and Python hash seed are configured."
        if deterministic_contract
        else "Set SCE_LOCGUARD_DETERMINISTIC, CUBLAS_WORKSPACE_CONFIG, and PYTHONHASHSEED before Python starts.",
        enabled=deterministic,
        cublas_workspace_configured=cublas_configured,
        python_hash_seed_configured=python_hash_seed.isdigit(),
    )

    for env_name, default_value, check_name in (
        ("SCE_LOCGUARD_RECOVERY_THRESHOLD", 0.28, "runtime.recovery_threshold"),
        ("SCE_LOCGUARD_TAMPER_AREA_THRESHOLD", 0.001, "runtime.tamper_area_threshold"),
    ):
        raw_value = os.environ.get(env_name, "").strip()
        try:
            value = float(raw_value) if raw_value else default_value
            valid = math.isfinite(value) and 0.0 < value < 1.0
        except ValueError:
            value = None
            valid = False
        report.add(
            check_name,
            "pass" if valid else "error",
            f"{env_name} is a finite probability strictly between 0 and 1."
            if valid
            else f"Set {env_name} to a finite number strictly between 0 and 1.",
            value=value,
            source="environment" if raw_value else "frozen_default",
        )

    component_env = "SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO"
    component_raw = os.environ.get(component_env, "").strip()
    try:
        component_ratio = float(component_raw) if component_raw else 0.0
        component_valid = (
            math.isfinite(component_ratio) and 0.0 <= component_ratio < 1.0
        )
    except ValueError:
        component_ratio = None
        component_valid = False
    report.add(
        "runtime.localization_min_component_area_ratio",
        "pass" if component_valid else "error",
        f"{component_env} is a finite ratio in [0, 1)."
        if component_valid
        else f"Set {component_env} to a finite number in [0, 1).",
        value=component_ratio,
        source="environment" if component_raw else "frozen_default",
    )


def check_packages(args: argparse.Namespace, report: CheckReport) -> None:
    if args.skip_package_check:
        report.add(
            "runtime.packages", "warning", "Package discovery was skipped by request."
        )
        return
    packages = [
        ("numpy", "numpy", True),
        ("PIL", "Pillow", True),
        ("cv2", "opencv-python", True),
        ("yaml", "PyYAML", True),
        ("fastapi", "fastapi", True),
        ("uvicorn", "uvicorn", True),
        ("torchvision", "torchvision", True),
        ("diffusers", "diffusers", True),
        ("transformers", "transformers", True),
        ("accelerate", "accelerate", True),
        ("safetensors", "safetensors", True),
        ("einops", "einops", True),
        ("scipy", "scipy", True),
        ("skimage", "scikit-image", True),
        ("lmdb", "lmdb", False),
        ("kornia", "kornia", False),
        ("lpips", "lpips", True),
    ]
    missing_required: list[str] = []
    missing_optional: list[str] = []
    import_failures: dict[str, str] = {}
    versions: dict[str, str] = {}
    for module_name, distribution_name, required in packages:
        if importlib.util.find_spec(module_name) is None:
            (missing_required if required else missing_optional).append(
                distribution_name
            )
            continue
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            import_failures[distribution_name] = f"{type(exc).__name__}: {exc}"[:500]
            (missing_required if required else missing_optional).append(
                distribution_name
            )
            continue
        try:
            versions[distribution_name] = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution_name] = "installed-version-unknown"
    report.add(
        "runtime.packages",
        "error" if missing_required else ("warning" if missing_optional else "pass"),
        "Required server modules are discoverable."
        if not missing_required
        else "Install the missing required modules from protection/supporting/image_watermark/requirements.server.txt.",
        missing_required=missing_required,
        missing_optional=missing_optional,
        import_failures=import_failures,
        versions=versions,
    )


def _nvidia_smi() -> tuple[bool, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return False, "nvidia-smi not found on PATH"
    fields = "index,name,driver_version,memory.total,compute_cap"
    command = [executable, f"--query-gpu={fields}", "--format=csv,noheader,nounits"]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=10, check=False
        )
        if completed.returncode != 0:
            # Older drivers do not expose compute_cap through the query API.
            fields = "index,name,driver_version,memory.total"
            command = [
                executable,
                f"--query-gpu={fields}",
                "--format=csv,noheader,nounits",
            ]
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=10, check=False
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if completed.returncode != 0:
        return False, completed.stderr.strip() or completed.stdout.strip()
    rows = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) in {4, 5}:
            rows.append(
                {
                    "index": parts[0],
                    "name": parts[1],
                    "driver_version": parts[2],
                    "memory_total_mib": parts[3],
                    "compute_capability": parts[4]
                    if len(parts) == 5
                    else "not-reported-by-driver",
                }
            )
    return bool(rows), rows or completed.stdout.strip()


def check_cuda(args: argparse.Namespace, report: CheckReport) -> None:
    try:
        import torch
    except Exception as exc:
        report.add(
            "gpu.pytorch",
            "error" if args.require_cuda else "warning",
            f"PyTorch import failed: {type(exc).__name__}: {exc}",
        )
        return
    cuda_available = bool(torch.cuda.is_available())
    devices: list[dict[str, Any]] = []
    if cuda_available:
        for index in range(torch.cuda.device_count()):
            properties = torch.cuda.get_device_properties(index)
            devices.append(
                {
                    "index": index,
                    "name": properties.name,
                    "total_memory_bytes": int(properties.total_memory),
                    "compute_capability": f"{properties.major}.{properties.minor}",
                }
            )
    report.add(
        "gpu.pytorch_cuda",
        "pass" if cuda_available else ("error" if args.require_cuda else "warning"),
        "PyTorch can access at least one CUDA device."
        if cuda_available
        else "PyTorch cannot access CUDA; real EditGuard inference is unavailable.",
        torch_version=torch.__version__,
        torch_cuda_runtime=torch.version.cuda,
        cudnn_version=torch.backends.cudnn.version(),
        visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES", "not-set"),
        devices=devices,
    )
    smi_ok, smi_details = _nvidia_smi()
    report.add(
        "gpu.nvidia_smi",
        "pass" if smi_ok else ("error" if args.require_cuda else "warning"),
        "NVIDIA driver inventory is available."
        if smi_ok
        else "NVIDIA driver inventory could not be read.",
        inventory=smi_details,
    )


def check_assets(
    args: argparse.Namespace, project_root: Path, report: CheckReport
) -> None:
    manifest_path = _expand_path(args.asset_manifest, base=project_root)
    if not manifest_path.is_file():
        report.add(
            "assets.manifest",
            "error",
            "Asset hash manifest does not exist.",
            path=str(manifest_path),
        )
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.add(
            "assets.manifest",
            "error",
            f"Asset manifest cannot be parsed: {exc}",
            path=str(manifest_path),
        )
        return
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list) or not assets:
        report.add(
            "assets.manifest",
            "error",
            "Asset manifest must contain a non-empty assets list.",
            path=str(manifest_path),
        )
        return
    errors: list[str] = []
    warnings: list[str] = []
    verified: list[dict[str, Any]] = []
    for index, entry in enumerate(assets, start=1):
        if not isinstance(entry, dict):
            errors.append(f"entry {index} is not an object")
            continue
        relative_raw = str(entry.get("path") or "").strip()
        required = bool(entry.get("required", True))
        expected = str(entry.get("sha256") or "").strip().lower()
        if not relative_raw:
            errors.append(f"entry {index} has no path")
            continue
        relative = Path(relative_raw)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(
                f"entry {index} path must be project-relative: {relative_raw}"
            )
            continue
        asset_path = (project_root / relative).resolve()
        if not _is_relative_to(asset_path, project_root):
            errors.append(
                f"entry {index} resolves outside project root: {relative_raw}"
            )
            continue
        if not asset_path.is_file():
            (errors if required else warnings).append(
                f"missing {'required' if required else 'optional'} asset: {relative_raw}"
            )
            continue
        if expected and (
            len(expected) != 64
            or any(char not in "0123456789abcdef" for char in expected)
        ):
            errors.append(f"entry {index} has an invalid SHA-256 value: {relative_raw}")
            continue
        if not expected:
            (errors if args.require_asset_hashes else warnings).append(
                f"no SHA-256 recorded: {relative_raw}"
            )
            actual = ""
        else:
            actual = _sha256(asset_path)
            if actual != expected:
                errors.append(f"SHA-256 mismatch: {relative_raw}")
        verified.append(
            {
                "path": relative.as_posix(),
                "role": str(entry.get("role") or "unspecified"),
                "required": required,
                "size_bytes": asset_path.stat().st_size,
                "sha256_verified": bool(expected and actual == expected),
            }
        )
    report.add(
        "assets.sha256",
        "error" if errors else ("warning" if warnings else "pass"),
        "Asset files match the recorded SHA-256 digests."
        if not errors and not warnings
        else "Asset verification found issues; do not start a paper run until required errors are resolved.",
        manifest=str(manifest_path),
        verified=verified,
        errors=errors,
        warnings=warnings,
    )


def _load_benchmark_config(
    path: str, report: CheckReport
) -> tuple[dict[str, Any], Path | None]:
    if not path:
        return {}, None
    config_path = _expand_path(path, base=PROJECT_ROOT)
    if not config_path.is_file():
        report.add(
            "dataset.benchmark_config",
            "error",
            "Benchmark YAML does not exist.",
            path=str(config_path),
        )
        return {}, config_path
    try:
        import yaml

        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        report.add(
            "dataset.benchmark_config",
            "error",
            f"Benchmark YAML cannot be parsed: {exc}",
            path=str(config_path),
        )
        return {}, config_path
    if not isinstance(config, dict):
        report.add(
            "dataset.benchmark_config",
            "error",
            "Benchmark YAML root must be a mapping.",
            path=str(config_path),
        )
        return {}, config_path
    report.add(
        "dataset.benchmark_config",
        "pass",
        "Benchmark YAML was parsed.",
        path=str(config_path),
    )
    return config, config_path


def _dataset_roots(
    args: argparse.Namespace,
    config: dict[str, Any],
    config_path: Path | None,
    report: CheckReport,
) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    base = config_path.parent if config_path else PROJECT_ROOT
    for source in config.get("datasets") or []:
        if not isinstance(source, dict) or not source.get("enabled", True):
            continue
        name = str(source.get("name") or "").strip()
        value = str(source.get("root") or "").strip()
        if name and value:
            roots[name] = _expand_path(value, base=base)
    env_json = os.environ.get("COGNIGUARD_DATASET_ROOTS_JSON", "").strip()
    if env_json:
        try:
            env_roots = json.loads(env_json)
            if not isinstance(env_roots, dict):
                raise ValueError("root value must be a JSON object")
            for name, value in env_roots.items():
                roots[str(name)] = _expand_path(str(value), base=PROJECT_ROOT)
        except (json.JSONDecodeError, ValueError) as exc:
            report.add(
                "dataset.root_environment",
                "error",
                f"COGNIGUARD_DATASET_ROOTS_JSON is invalid: {exc}",
            )
    for item in args.dataset_root:
        if "=" not in item:
            report.add(
                "dataset.root_argument", "error", f"Expected NAME=PATH, got: {item}"
            )
            continue
        name, value = item.split("=", 1)
        if not name.strip() or not value.strip():
            report.add(
                "dataset.root_argument",
                "error",
                f"Expected non-empty NAME=PATH, got: {item}",
            )
            continue
        roots[name.strip()] = _expand_path(value.strip(), base=PROJECT_ROOT)
    return roots


def _manifest_from_config(config: dict[str, Any], config_path: Path | None) -> str:
    candidates: Iterable[Any] = (
        config.get("manifest"),
        config.get("manifest_path"),
        config.get("dataset_manifest"),
        (config.get("benchmark") or {}).get("manifest")
        if isinstance(config.get("benchmark"), dict)
        else None,
        (config.get("data") or {}).get("manifest")
        if isinstance(config.get("data"), dict)
        else None,
    )
    for value in candidates:
        if isinstance(value, dict):
            value = value.get("path") or value.get("file")
        if value:
            base = config_path.parent if config_path else PROJECT_ROOT
            return str(_expand_path(str(value), base=base))
    return ""


def check_dataset(
    args: argparse.Namespace,
    project_root: Path,
    shared_root: Path | None,
    report: CheckReport,
) -> None:
    config, config_path = _load_benchmark_config(args.benchmark_config, report)
    if config and args.expected_api_url:
        enabled_editguard = [
            method
            for method in config.get("methods") or []
            if isinstance(method, dict)
            and method.get("enabled", True)
            and method.get("id") == "editguard_wrapper"
        ]
        configured_url = (
            str(enabled_editguard[0].get("base_url") or "").rstrip("/")
            if len(enabled_editguard) == 1
            else ""
        )
        expected_url = str(args.expected_api_url).rstrip("/")
        matches = bool(configured_url and configured_url == expected_url)
        report.add(
            "dataset.api_url_contract",
            "pass" if matches else "error",
            "Benchmark editguard_wrapper URL matches the API launcher."
            if matches
            else "Benchmark must contain exactly one enabled editguard_wrapper with the launcher URL.",
            configured=configured_url or None,
            expected=expected_url,
        )
    manifest_raw = args.dataset_manifest or _manifest_from_config(config, config_path)
    if not manifest_raw:
        status = "error" if args.require_dataset_files else "warning"
        report.add(
            "dataset.manifest", status, "No benchmark dataset manifest is configured."
        )
        return
    manifest_path = _expand_path(
        manifest_raw, base=config_path.parent if config_path else project_root
    )
    if not manifest_path.is_file():
        report.add(
            "dataset.manifest",
            "error",
            "Dataset JSONL manifest does not exist.",
            path=str(manifest_path),
        )
        return
    roots = _dataset_roots(args, config, config_path, report)
    root_errors = [name for name, path in roots.items() if not path.is_dir()]
    if root_errors:
        report.add(
            "dataset.roots",
            "error",
            "One or more configured dataset roots do not exist.",
            missing_datasets=root_errors,
            roots={name: str(path) for name, path in roots.items()},
        )
    elif roots:
        outside_shared = [
            name
            for name, path in roots.items()
            if shared_root and not _is_relative_to(path, shared_root)
        ]
        report.add(
            "dataset.roots",
            "error" if outside_shared else "pass",
            "Dataset roots exist and satisfy the shared-root contract."
            if not outside_shared
            else "Dataset roots outside COGNIGUARD_SHARED_ROOT will not be portable across service processes.",
            roots={name: str(path) for name, path in roots.items()},
            outside_shared=outside_shared,
        )
    rows = 0
    invalid_json = 0
    invalid_schema = 0
    duplicate_ids = 0
    duplicate_content_rows = 0
    source_family_split_leakage = 0
    missing_files = 0
    unresolved_files = 0
    unknown_licenses = 0
    missing_dataset_hashes = 0
    dataset_hash_mismatches = 0
    dataset_hashes_verified = 0
    seen: set[str] = set()
    seen_sha256: dict[str, str] = {}
    family_splits: dict[str, str] = {}
    splits: Counter[str] = Counter()
    datasets: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    required_fields = {
        "sample_id",
        "relative_path",
        "split",
        "source_dataset",
        "domain",
        "license_id",
        "provenance",
    }
    manifest_config = (
        config.get("manifest") if isinstance(config.get("manifest"), dict) else {}
    )
    verify_dataset_hashes = bool(manifest_config.get("verify_hashes", False))
    allowed_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                invalid_json += 1
                continue
            if not isinstance(row, dict) or any(
                not str(row.get(field) or "").strip() for field in required_fields
            ):
                invalid_schema += 1
                continue
            sample_id = str(row["sample_id"])
            if sample_id in seen:
                duplicate_ids += 1
            seen.add(sample_id)
            split = str(row["split"])
            source = str(row["source_dataset"])
            if split not in {"train", "dev", "test"}:
                invalid_schema += 1
            splits[split] += 1
            datasets[source] += 1
            domains[str(row["domain"])] += 1
            expected_hash = str(row.get("sha256") or "").strip().lower()
            valid_hash = len(expected_hash) == 64 and all(
                char in "0123456789abcdef" for char in expected_hash
            )
            if valid_hash:
                if expected_hash in seen_sha256:
                    duplicate_content_rows += 1
                else:
                    seen_sha256[expected_hash] = sample_id
            elif verify_dataset_hashes:
                missing_dataset_hashes += 1
            source_family = str(row.get("source_family") or "").strip()
            if source_family:
                previous_split = family_splits.get(source_family)
                if previous_split is not None and previous_split != split:
                    source_family_split_leakage += 1
                else:
                    family_splits[source_family] = split
            if str(row["license_id"]).strip().lower() in {
                "unknown",
                "unspecified",
                "n/a",
                "none",
            }:
                unknown_licenses += 1
            relative = Path(str(row["relative_path"]))
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or relative.suffix.lower() not in allowed_extensions
            ):
                invalid_schema += 1
                continue
            root = roots.get(source)
            if root is None:
                unresolved_files += 1
            else:
                image_path = root / relative
                if not image_path.is_file():
                    missing_files += 1
                elif verify_dataset_hashes:
                    if valid_hash and _sha256(image_path) != expected_hash:
                        dataset_hash_mismatches += 1
                    elif valid_hash:
                        dataset_hashes_verified += 1
    errors: list[str] = []
    warnings: list[str] = []
    experiment = (
        config.get("experiment") if isinstance(config.get("experiment"), dict) else {}
    )
    benchmark_split = str(experiment.get("split") or "test")
    if benchmark_split not in {"train", "dev", "test"}:
        errors.append(f"benchmark config selects unsupported split: {benchmark_split}")
    if rows < max(args.min_dataset_samples, 1):
        errors.append(
            f"manifest has {rows} samples; minimum is {max(args.min_dataset_samples, 1)}"
        )
    if invalid_json:
        errors.append(f"invalid JSON rows: {invalid_json}")
    if invalid_schema:
        errors.append(f"invalid schema/path rows: {invalid_schema}")
    if duplicate_ids:
        errors.append(f"duplicate sample_id rows: {duplicate_ids}")
    if duplicate_content_rows:
        errors.append(f"duplicate SHA-256 content rows: {duplicate_content_rows}")
    if source_family_split_leakage:
        errors.append(
            "source_family rows assigned across multiple splits: "
            f"{source_family_split_leakage}"
        )
    if splits.get(benchmark_split, 0) < max(args.min_test_samples, 1):
        errors.append(
            f"manifest has {splits.get(benchmark_split, 0)} {benchmark_split} samples; "
            f"minimum selected-split count is {max(args.min_test_samples, 1)}"
        )
    if unknown_licenses:
        (errors if args.require_license_metadata else warnings).append(
            f"rows with unknown/unspecified license_id: {unknown_licenses}"
        )
    if len(datasets) < max(args.min_source_datasets, 1):
        errors.append(
            f"manifest has {len(datasets)} source datasets; minimum is {max(args.min_source_datasets, 1)}"
        )
    if len(domains) < max(args.min_content_domains, 1):
        errors.append(
            f"manifest has {len(domains)} content domains; minimum is {max(args.min_content_domains, 1)}"
        )
    if args.require_dataset_files and unresolved_files:
        errors.append(f"rows without a source_dataset root mapping: {unresolved_files}")
    elif unresolved_files:
        warnings.append(
            f"rows without a source_dataset root mapping: {unresolved_files}"
        )
    if missing_files:
        errors.append(f"referenced image files missing: {missing_files}")
    if verify_dataset_hashes and missing_dataset_hashes:
        errors.append(f"rows without a valid SHA-256 value: {missing_dataset_hashes}")
    if dataset_hash_mismatches:
        errors.append(f"dataset SHA-256 mismatches: {dataset_hash_mismatches}")
    report.add(
        "dataset.manifest",
        "error" if errors else ("warning" if warnings else "pass"),
        "Dataset manifest is structurally valid and its referenced files are available."
        if not errors and not warnings
        else "Dataset manifest validation found issues.",
        path=str(manifest_path),
        samples=rows,
        benchmark_split=benchmark_split,
        split_counts=dict(sorted(splits.items())),
        dataset_counts=dict(sorted(datasets.items())),
        domain_counts=dict(sorted(domains.items())),
        resolved_root_count=len(roots),
        verify_hashes=verify_dataset_hashes,
        hashes_verified=dataset_hashes_verified,
        unique_sha256_count=len(seen_sha256),
        duplicate_sha256_content_rows=duplicate_content_rows,
        source_family_count=len(family_splits),
        source_family_split_leakage_count=source_family_split_leakage,
        errors=errors,
        warnings=warnings,
    )
    manifest_config = (
        config.get("manifest") if isinstance(config.get("manifest"), dict) else {}
    )
    if manifest_config.get("require_lock", False):
        if config_path is None:
            report.add(
                "dataset.manifest_lock",
                "error",
                "A required manifest lock cannot be validated without a benchmark config path.",
            )
        else:
            try:
                project_path = str(project_root.resolve())
                if project_path not in sys.path:
                    sys.path.insert(0, project_path)
                from protection.supporting.image_watermark.experiments.manifest import (
                    load_manifest,
                    validate_manifest_lock,
                )

                locked_rows = load_manifest(
                    manifest_path,
                    dataset_roots=roots,
                    require_files=True,
                    verify_hashes=verify_dataset_hashes,
                )
                lock_audit = validate_manifest_lock(
                    manifest_path,
                    locked_rows,
                    config_path=config_path,
                    dataset_roots=roots,
                )
            except (OSError, ValueError) as exc:
                report.add(
                    "dataset.manifest_lock",
                    "error",
                    "Required formal manifest lock validation failed.",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
            else:
                report.add(
                    "dataset.manifest_lock",
                    "pass",
                    "Formal manifest, config, assignment, and upstream locks are bound.",
                    path=lock_audit["lock_path"],
                    sha256=lock_audit["lock_sha256"],
                    assignment_sha256=lock_audit["assignment_sha256"],
                    upstream_datasets=sorted(
                        lock_audit.get("upstream_dataset_locks") or {}
                    ),
                )


def _missing_or_empty_snapshot_files(
    snapshot: Path, required_files: Iterable[str]
) -> list[str]:
    missing: list[str] = []
    for relative_path in required_files:
        candidate = snapshot / relative_path
        try:
            present = candidate.is_file() and candidate.stat().st_size > 0
        except OSError:
            present = False
        if not present:
            missing.append(relative_path)
    return missing


def check_hf_cache(
    args: argparse.Namespace, project_root: Path, report: CheckReport
) -> None:
    cache_root = (
        _expand_path(args.hf_cache, base=project_root)
        if args.hf_cache
        else (project_root / 'assets' / 'models' / "hf_cache").resolve()
    )
    marker = cache_root / f"models--{args.model_id.replace('/', '--')}"
    snapshots = marker / "snapshots"
    contract_supported = args.model_id == DEFAULT_MODEL_ID
    snapshot_dirs = (
        sorted(
            (path for path in snapshots.iterdir() if path.is_dir()),
            key=lambda path: path.name,
        )
        if snapshots.is_dir()
        else []
    )
    complete_snapshots: list[str] = []
    missing_files_by_snapshot: dict[str, list[str]] = {}
    invalid_snapshot_revisions: list[str] = []
    for snapshot in snapshot_dirs:
        if not HF_COMMIT_REVISION_PATTERN.fullmatch(snapshot.name):
            invalid_snapshot_revisions.append(snapshot.name)
        missing = _missing_or_empty_snapshot_files(
            snapshot, INPAINTING_FP16_REQUIRED_FILES
        )
        if missing:
            missing_files_by_snapshot[snapshot.name] = missing
        elif HF_COMMIT_REVISION_PATTERN.fullmatch(snapshot.name):
            complete_snapshots.append(snapshot.name)
    complete_snapshots.sort()
    required_revision = str(args.model_revision or "").strip()
    revision_configured = bool(required_revision)
    revision_is_exact_commit = bool(
        HF_COMMIT_REVISION_PATTERN.fullmatch(required_revision)
    )
    revision_available = (
        contract_supported
        and revision_configured
        and revision_is_exact_commit
        and required_revision in complete_snapshots
    )
    if args.require_hf_cache:
        # A formal/AIGC-required run must bind to one immutable cached snapshot.
        # Accepting an empty revision would let cache state silently select a
        # different model after another snapshot is staged.
        available = contract_supported and marker.is_dir() and revision_available
    else:
        available = (
            contract_supported
            and marker.is_dir()
            and bool(complete_snapshots)
            and (not revision_configured or revision_available)
        )
    if not contract_supported:
        message = (
            "No audited offline fp16 file contract is defined for the configured inpainting model; "
            f"expected {DEFAULT_MODEL_ID}."
        )
    elif args.require_hf_cache and not revision_configured:
        message = (
            "SCE_LOCGUARD_INPAINT_MODEL_REVISION is empty; a formal AIGC run "
            "must name the exact cached snapshot directory."
        )
    elif revision_configured and not revision_is_exact_commit:
        message = (
            "Configured inpainting model revision is not an exact 40-character lowercase commit SHA; "
            "mutable refs and aliases are rejected."
        )
    elif revision_configured and not revision_available:
        missing = missing_files_by_snapshot.get(required_revision)
        message = (
            "Configured inpainting model revision is missing required fp16 inference files."
            if missing
            else "Configured inpainting model revision is not the complete cached fp16 snapshot."
        )
    elif available and revision_configured:
        message = (
            "Offline Stable Diffusion inpainting cache contains every required fp16 safetensors file "
            "for the exact requested revision."
        )
    elif available:
        message = (
            "Offline Stable Diffusion inpainting cache contains a complete fp16 safetensors snapshot; "
            "an exact revision was not required for this non-formal check."
        )
    else:
        message = "Offline inpainting cache is absent/incomplete; required fp16 inference files are unavailable."
    report.add(
        "assets.hf_inpainting_cache",
        "pass" if available else ("error" if args.require_hf_cache else "warning"),
        message,
        cache_root=str(cache_root),
        model_marker=str(marker),
        model_contract=DEFAULT_MODEL_ID,
        model_contract_supported=contract_supported,
        required_files=list(INPAINTING_FP16_REQUIRED_FILES),
        discovered_snapshots=[path.name for path in snapshot_dirs],
        complete_snapshots=complete_snapshots,
        missing_files_by_snapshot=missing_files_by_snapshot,
        invalid_snapshot_revisions=invalid_snapshot_revisions,
        required_revision=required_revision or None,
        required_revision_configured=revision_configured,
        required_revision_is_exact_commit=revision_is_exact_commit,
        required_revision_available=revision_available,
        exact_revision_required=bool(args.require_hf_cache),
        downloads_allowed_by_service=False,
    )


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report = CheckReport()
    project_root = _expand_path(args.project_root)
    check_platform(args, report)
    shared_root, output_root = check_paths(args, project_root, report)
    check_secret(args, report)
    check_packages(args, report)
    check_cuda(args, report)
    check_assets(args, project_root, report)
    check_dataset(args, project_root, shared_root, report)
    check_hf_cache(args, project_root, report)
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed"
        if report.errors
        else "ready_with_warnings"
        if report.warnings
        else "ready",
        "summary": {
            "errors": report.errors,
            "warnings": report.warnings,
            "checks": len(report.checks),
        },
        "deployment_contract": {
            "project_root": str(project_root),
            "shared_root": str(shared_root) if shared_root else None,
            "output_root": str(output_root),
            "uvicorn_workers": 1,
            "secret_value_recorded": False,
        },
        "checks": report.checks,
    }
    return payload, 1 if report.errors else 0


def _write_json(path: str, payload: dict[str, Any]) -> None:
    output = _expand_path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload, exit_code = build_report(args)
    if args.output_json:
        _write_json(args.output_json, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for row in payload["checks"]:
            print(f"[{row['status'].upper():7}] {row['name']}: {row['message']}")
        summary = payload["summary"]
        print(
            f"Preflight status={payload['status']} checks={summary['checks']} "
            f"errors={summary['errors']} warnings={summary['warnings']}"
        )
        if args.output_json:
            print(f"JSON report: {_expand_path(args.output_json)}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
