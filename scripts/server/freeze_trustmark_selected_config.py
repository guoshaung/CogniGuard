#!/usr/bin/env python3
"""Create a fresh TrustMark config bound to a selected paper benchmark.

The source TrustMark YAML remains immutable. Formal scientific inputs are
resolved exclusively from the explicit selected benchmark YAML; generic
dataset environment overrides are deliberately ignored.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

import yaml

from protection.supporting.image_watermark.experiments.manifest import (
    dataset_roots_from_config,
    load_manifest,
    manifest_path_from_config,
    validate_manifest_lock,
)
from scripts.server.freeze_image_watermark_channel_vote_formal_config import (
    ChannelVoteFormalFreezeError,
    validate_frozen_channel_vote_formal_config,
)


EVIDENCE_SCHEMA_VERSION = "cogniguard.trustmark.selected_config_binding.v1"
FORMAL_SELECTION_SCHEMA_VERSION = "cogniguard_image_channel_vote_formal_selection_v1"
REQUIRED_METHOD_FIELDS = (
    "model_variant",
    "ecc_schema",
    "strength",
    "device",
    "concentrate_wm_region",
    "required_package_version",
    "required_source_commit",
)


class TrustMarkSelectedFreezeError(RuntimeError):
    """Raised when a fresh TrustMark/selected-benchmark binding is unsafe."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_yaml(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise TrustMarkSelectedFreezeError(
            f"{label} is not valid YAML: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise TrustMarkSelectedFreezeError(f"{label} must be a YAML mapping: {path}")
    return payload


def _relative_reference(target: Path, *, base: Path) -> str:
    try:
        return Path(os.path.relpath(target, start=base)).as_posix()
    except ValueError:
        return str(target)


def _resolve_config_path(value: Any, *, config_path: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise TrustMarkSelectedFreezeError(f"{label} must be a non-empty path.")
    candidate = Path(os.path.expandvars(value)).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def _validate_baseline(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    experiment = payload.get("experiment")
    method = payload.get("method")
    if not isinstance(experiment, dict) or not isinstance(method, dict):
        raise TrustMarkSelectedFreezeError(
            "TrustMark baseline requires experiment and method mappings."
        )
    if (
        experiment.get("mode") != "formal"
        or experiment.get("strict_fail_closed") is not True
        or experiment.get("attack_scope") != "traditional_only"
        or experiment.get("save_attacked_images") is not False
    ):
        raise TrustMarkSelectedFreezeError(
            "TrustMark baseline must remain formal, strict, traditional_only, and "
            "use hash-only attacked-image retention."
        )
    missing = [name for name in REQUIRED_METHOD_FIELDS if name not in method]
    if missing:
        raise TrustMarkSelectedFreezeError(
            "TrustMark baseline is missing official method fields: "
            + ", ".join(missing)
        )
    if "selected_benchmark_evidence" in payload:
        raise TrustMarkSelectedFreezeError(
            "Source TrustMark config is already bound to a selected benchmark."
        )
    output_root = experiment.get("output_root")
    if not isinstance(output_root, str) or not output_root.strip():
        raise TrustMarkSelectedFreezeError(
            "TrustMark baseline experiment.output_root must be a non-empty path."
        )
    return experiment, method


def _validate_selected_benchmark(payload: Mapping[str, Any]) -> None:
    experiment = payload.get("experiment")
    manifest = payload.get("manifest")
    selection = payload.get("formal_selection")
    if (
        not isinstance(experiment, dict)
        or experiment.get("strict_paper_mode") is not True
        or experiment.get("fail_fast") is not True
        or experiment.get("split") != "test"
        or int(experiment.get("max_samples", 0) or 0) != 0
        or experiment.get("paper_eligible") is not True
        or experiment.get("development_only") is not False
        or not isinstance(manifest, dict)
        or manifest.get("verify_hashes") is not True
        or manifest.get("require_lock") is not True
    ):
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark is not a strict locked formal test configuration."
        )
    if (
        not isinstance(selection, dict)
        or selection.get("schema_version") != FORMAL_SELECTION_SCHEMA_VERSION
        or selection.get("status") != "frozen"
        or selection.get("selection_source")
        != "development_only_channel_vote_confirmation"
        or selection.get("selection_split") != "dev"
        or selection.get("formal_test_rows_consumed") != 0
    ):
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark lacks frozen development-only selection evidence."
        )


def _atomic_create_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Same-directory hard-link publication is atomic and, unlike
            # os.replace(), can never clobber a target created concurrently.
            os.link(temporary, path)
        except FileExistsError as exc:
            raise FileExistsError(
                f"Refusing to overwrite existing output: {path}"
            ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def freeze_trustmark_selected_config(
    baseline_config: Path,
    *,
    selected_benchmark_config: Path,
    output_config: Path,
) -> dict[str, Any]:
    baseline_config = baseline_config.expanduser().resolve()
    selected_benchmark_config = selected_benchmark_config.expanduser().resolve()
    output_config = output_config.expanduser().resolve()
    if output_config in {baseline_config, selected_benchmark_config}:
        raise TrustMarkSelectedFreezeError(
            "Output config must not overwrite either immutable input config."
        )
    if output_config.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_config}")

    baseline_sha256 = (
        sha256_file(baseline_config) if baseline_config.is_file() else None
    )
    baseline_payload = _read_yaml(baseline_config, label="TrustMark baseline config")
    baseline_experiment, baseline_method = _validate_baseline(baseline_payload)
    if sha256_file(baseline_config) != baseline_sha256:
        raise TrustMarkSelectedFreezeError(
            "TrustMark baseline changed while it was read."
        )

    selected_sha256 = (
        sha256_file(selected_benchmark_config)
        if selected_benchmark_config.is_file()
        else None
    )
    selected_payload = _read_yaml(
        selected_benchmark_config, label="Selected benchmark config"
    )
    _validate_selected_benchmark(selected_payload)
    try:
        selected_required_capabilities = validate_frozen_channel_vote_formal_config(
            selected_benchmark_config
        )
    except ChannelVoteFormalFreezeError as exc:
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark channel-vote freeze validation failed: " + str(exc)
        ) from exc
    if sha256_file(selected_benchmark_config) != selected_sha256:
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark changed while it was read."
        )

    try:
        selected_manifest = manifest_path_from_config(
            selected_benchmark_config, environ={}
        )
        selected_roots = dataset_roots_from_config(
            selected_benchmark_config, environ={}
        )
        selected_rows = load_manifest(
            selected_manifest,
            dataset_roots=selected_roots,
            require_files=True,
            verify_hashes=True,
        )
        lock_audit = validate_manifest_lock(
            selected_manifest,
            selected_rows,
            config_path=selected_benchmark_config,
            dataset_roots=selected_roots,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise TrustMarkSelectedFreezeError(
            f"Selected benchmark manifest lock validation failed: {exc}"
        ) from exc
    selected_manifest_sha256 = sha256_file(selected_manifest)
    selected_lock_path = Path(str(lock_audit["lock_path"])).resolve()
    selected_lock_sha256 = str(lock_audit["lock_sha256"])

    frozen = copy.deepcopy(baseline_payload)
    frozen_experiment = frozen["experiment"]
    original_output_root = _resolve_config_path(
        baseline_experiment["output_root"],
        config_path=baseline_config,
        label="experiment.output_root",
    )
    frozen_experiment["source_benchmark_config"] = _relative_reference(
        selected_benchmark_config, base=output_config.parent
    )
    frozen_experiment["output_root"] = _relative_reference(
        original_output_root, base=output_config.parent
    )
    frozen["selected_benchmark_evidence"] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "status": "frozen",
        "source_trustmark_config": _relative_reference(
            baseline_config, base=output_config.parent
        ),
        "source_trustmark_config_sha256": baseline_sha256,
        "selected_benchmark_config": _relative_reference(
            selected_benchmark_config, base=output_config.parent
        ),
        "selected_benchmark_config_sha256": selected_sha256,
        "selected_manifest": _relative_reference(
            selected_manifest, base=output_config.parent
        ),
        "selected_manifest_sha256": selected_manifest_sha256,
        "selected_manifest_lock": _relative_reference(
            selected_lock_path, base=output_config.parent
        ),
        "selected_manifest_lock_sha256": selected_lock_sha256,
        "selected_manifest_assignment_sha256": lock_audit["assignment_sha256"],
        "selected_manifest_total_samples": lock_audit["total_samples"],
        "selected_manifest_test_samples": int(
            (lock_audit.get("split_counts") or {}).get("test", 0)
        ),
        "selected_required_capabilities": copy.deepcopy(selected_required_capabilities),
        "generic_dataset_environment_overrides_ignored": True,
    }

    if frozen["method"] != baseline_method:
        raise TrustMarkSelectedFreezeError(
            "Official TrustMark method fields changed during config construction."
        )
    if frozen_experiment.get("attack_scope") != "traditional_only":
        raise TrustMarkSelectedFreezeError(
            "TrustMark attack_scope changed during config construction."
        )

    # Recheck every external binding immediately before publication.
    if sha256_file(baseline_config) != baseline_sha256:
        raise TrustMarkSelectedFreezeError("TrustMark baseline changed before publish.")
    if sha256_file(selected_benchmark_config) != selected_sha256:
        raise TrustMarkSelectedFreezeError("Selected benchmark changed before publish.")
    if sha256_file(selected_manifest) != selected_manifest_sha256:
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark manifest changed before publish."
        )
    if sha256_file(selected_lock_path) != selected_lock_sha256:
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark manifest lock changed before publish."
        )
    repeated_lock_audit = validate_manifest_lock(
        selected_manifest,
        selected_rows,
        config_path=selected_benchmark_config,
        dataset_roots=selected_roots,
    )
    if repeated_lock_audit != lock_audit:
        raise TrustMarkSelectedFreezeError(
            "Selected benchmark lock audit changed before publish."
        )

    output_text = yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False)
    created = False
    try:
        _atomic_create_text(output_config, output_text)
        created = True
        published = _read_yaml(output_config, label="Published TrustMark config")
        published_experiment = published.get("experiment") or {}
        if published.get("method") != baseline_method:
            raise TrustMarkSelectedFreezeError(
                "Published config changed official TrustMark method fields."
            )
        if published_experiment.get("attack_scope") != "traditional_only":
            raise TrustMarkSelectedFreezeError(
                "Published config changed traditional_only attack scope."
            )
        if (
            _resolve_config_path(
                published_experiment.get("source_benchmark_config"),
                config_path=output_config,
                label="Published source_benchmark_config",
            )
            != selected_benchmark_config
        ):
            raise TrustMarkSelectedFreezeError(
                "Published source_benchmark_config does not resolve to selected YAML."
            )
        if (
            _resolve_config_path(
                published_experiment.get("output_root"),
                config_path=output_config,
                label="Published output_root",
            )
            != original_output_root
        ):
            raise TrustMarkSelectedFreezeError(
                "Published output_root was not correctly relocated."
            )
        evidence = published.get("selected_benchmark_evidence") or {}
        if (
            evidence.get("selected_benchmark_config_sha256") != selected_sha256
            or evidence.get("selected_manifest_lock_sha256") != selected_lock_sha256
            or evidence.get("selected_required_capabilities")
            != selected_required_capabilities
        ):
            raise TrustMarkSelectedFreezeError(
                "Published selected-benchmark evidence hashes are incorrect."
            )
    except Exception:
        if created:
            output_config.unlink(missing_ok=True)
        raise

    return {
        "status": "created",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_trustmark_config": str(baseline_config),
        "source_trustmark_config_sha256": baseline_sha256,
        "selected_benchmark_config": str(selected_benchmark_config),
        "selected_benchmark_config_sha256": selected_sha256,
        "selected_manifest": str(selected_manifest),
        "selected_manifest_sha256": selected_manifest_sha256,
        "selected_manifest_lock": str(selected_lock_path),
        "selected_manifest_lock_sha256": selected_lock_sha256,
        "output_config": str(output_config),
        "output_config_sha256": sha256_file(output_config),
        "official_method_fields_preserved": True,
        "traditional_only_preserved": True,
        "selected_required_capabilities": copy.deepcopy(selected_required_capabilities),
        "output_root_relocated": True,
        "generic_dataset_environment_overrides_ignored": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-config", type=Path, required=True)
    parser.add_argument("--selected-benchmark-config", type=Path, required=True)
    parser.add_argument("--output-config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = freeze_trustmark_selected_config(
        args.baseline_config,
        selected_benchmark_config=args.selected_benchmark_config,
        output_config=args.output_config,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
