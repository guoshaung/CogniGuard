"""Run pinned WAM on the same portable manifest and traditional attack grid.

This is an independent baseline track: it reads the existing benchmark YAML
and JSONL manifest but never edits or registers itself in the public paper
configuration.  AIGC attacks are deliberately excluded until attacked images
and aligned ground-truth masks can be shared identically across methods.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
import re
import shutil
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import (
    AttackSpec,
    apply_traditional_attack,
    expand_attack_specs,
    truth_mask_from_half_open_bbox,
)
from protection.supporting.image_watermark.experiments.manifest import (
    DATASET_MANIFEST_ENV,
    DATASET_ROOTS_ENV,
    ImageSample,
    dataset_roots_from_config,
    load_manifest,
    manifest_path_from_config,
    validate_manifest_lock,
)
from protection.supporting.image_watermark.experiments.metrics import LPIPSEvaluator, image_quality_metrics
from protection.supporting.image_watermark.official_baselines.wam_official_adapter import (
    OfficialWamBackend,
    WamDependencyError,
    WamOfficialAdapter,
)
from protection.supporting.image_watermark.official_baselines.wam_official_contract import (
    NATIVE_SEMANTICS,
    OFFICIAL_WAM_MIT,
)
from scripts.server.freeze_image_watermark_channel_vote_formal_config import (
    ChannelVoteFormalFreezeError,
    validate_frozen_channel_vote_formal_config,
)


class WamManifestError(RuntimeError):
    """Raised when same-manifest invariants cannot be satisfied."""


RUN_MODES = {"formal", "smoke"}
_SAFE_COMPONENT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}\Z")
FORMAL_SOURCE_QUOTAS = {
    "cogniguard_edufig_v2": 1200,
    "open_images_v7_license_audited": 600,
    "nasa_images_policy_audited": 400,
    "met_open_access_cc0": 800,
}
FORMAL_SEEDS = (20260802, 20260803, 20260804)
FORMAL_MAX_PIPELINE_FAILURE_RATE = 0.0
FORMAL_FAILED_ATTACK_DIAGNOSTIC_LIMIT = 50
FORMAL_TRADITIONAL_ATTACK_IDS = (
    "clean",
    "jpeg__quality-90",
    "jpeg__quality-70",
    "jpeg__quality-50",
    "jpeg__quality-30",
    "webp__quality-90",
    "webp__quality-70",
    "webp__quality-50",
    "resize__scale-0.5",
    "resize__scale-0.75",
    "resize__scale-1.25",
    "resize__scale-1.5",
    "random_crop__keep-0.9",
    "random_crop__keep-0.75",
    "random_crop__keep-0.5",
    "rotate__degrees-2",
    "rotate__degrees-5",
    "rotate__degrees-10",
    "gaussian_blur__radius-0.5",
    "gaussian_blur__radius-1.0",
    "gaussian_blur__radius-2.0",
    "gaussian_noise__sigma-2.0",
    "gaussian_noise__sigma-5.0",
    "gaussian_noise__sigma-10.0",
    "brightness__factor-0.8",
    "brightness__factor-1.2",
    "contrast__factor-0.8",
    "contrast__factor-1.2",
    "saturation__factor-0.7",
    "saturation__factor-1.3",
    "median_filter__size-3",
    "median_filter__size-5",
    "erasing__area_ratio-0.05",
    "erasing__area_ratio-0.15",
    "erasing__area_ratio-0.25",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sample_slug(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()


def _artifact_slug(value: str) -> str:
    """Return a non-traversing, collision-resistant artifact component."""

    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip(".-_")[:64]
    if not normalized or not _SAFE_COMPONENT.fullmatch(normalized):
        normalized = "item"
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{normalized}-{suffix}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _source_file_sha256(subject: Any) -> tuple[str, str]:
    source = inspect.getsourcefile(subject)
    if not source:
        raise WamManifestError(f"Cannot resolve source file for {subject!r}.")
    path = Path(source).resolve()
    return str(path), _file_sha256(path)


def _attack_id(spec: AttackSpec) -> str:
    return str(spec.params.get("expanded_name") or spec.name)


def _native_message(sample_id: str, seed: int) -> str:
    """Derive reproducible native bits without creating a registry mapping."""

    digest = hashlib.sha256(
        f"wam-native-32|{seed}|{sample_id}".encode("utf-8")
    ).digest()
    return "".join(f"{byte:08b}" for byte in digest[:4])


def _image_sha256(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    digest = hashlib.sha256()
    digest.update(f"RGB:{rgb.width}x{rgb.height}\x00".encode("ascii"))
    digest.update(rgb.tobytes())
    return digest.hexdigest()


def _mean(values: list[float]) -> float | None:
    return None if not values else float(np.mean(values))


def _summarize(
    rows: list[dict[str, Any]], negative_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["attack_id"])].append(row)
    by_attack: dict[str, Any] = {}
    for attack_id, group in sorted(grouped.items()):
        successful = [row for row in group if row.get("pipeline_success") is True]
        localizations = [
            row["localization_same_attack_gt"]
            for row in successful
            if row.get("localization_same_attack_gt") is not None
        ]
        by_attack[attack_id] = {
            "rows": len(group),
            "pipeline_success_rate": _mean(
                [float(row.get("pipeline_success") is True) for row in group]
            ),
            "pipeline_failure_rate": _mean(
                [float(row.get("pipeline_success") is not True) for row in group]
            ),
            "native_decode_available_rate": _mean(
                [float(row["native_decode_available"]) for row in group]
            ),
            "native_32bit_raw_bit_accuracy_strict_mean": _mean(
                [float(row["native_32bit_raw_bit_accuracy_strict"]) for row in group]
            ),
            "native_32bit_raw_exact_rate": _mean(
                [float(row["native_32bit_raw_exact"]) for row in group]
            ),
            "native_watermark_detected_area_fraction_mean": _mean(
                [
                    float(row["native_watermark_area_fraction"])
                    for row in successful
                    if row["native_watermark_area_fraction"] is not None
                ]
            ),
            "native_watermark_mean_probability_mean": _mean(
                [
                    float(row["native_watermark_mean_probability"])
                    for row in successful
                    if row["native_watermark_mean_probability"] is not None
                ]
            ),
            "native_watermark_p95_probability_mean": _mean(
                [
                    float(row["native_watermark_p95_probability"])
                    for row in successful
                    if row["native_watermark_p95_probability"] is not None
                ]
            ),
            "detect_and_decode_latency_ms_mean": _mean(
                [
                    float(row["detect_and_decode_latency_ms"])
                    for row in successful
                    if row["detect_and_decode_latency_ms"] is not None
                ]
            ),
            "same_gt_localization_rows": len(localizations),
            "derived_tamper_iou_mean": _mean(
                [
                    float(
                        item["derived_tamper_from_watermark_absence_within_support"][
                            "iou"
                        ]
                    )
                    for item in localizations
                ]
            ),
        }
    embed_keys: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        embed_keys[(str(row["sample_id"]), int(row["seed"]))] = row
    embeds = list(embed_keys.values())
    successful_embeds = [
        row for row in embeds if row.get("embed_pipeline_success") is True
    ]
    return {
        "schema_version": "cogniguard.wam.manifest_summary.v1",
        "method_id": OFFICIAL_WAM_MIT.method_id,
        "rows": len(rows),
        "unique_samples": len({str(row["sample_id"]) for row in rows}),
        "unique_sample_seed_embeds": len(embeds),
        "pipeline_success_rate": _mean(
            [float(row.get("pipeline_success") is True) for row in rows]
        ),
        "pipeline_failure_rate": _mean(
            [float(row.get("pipeline_success") is not True) for row in rows]
        ),
        "failed_rows": sum(row.get("pipeline_success") is not True for row in rows),
        "common_embedding_metrics": {
            "psnr_db_mean": _mean(
                [
                    float(row["psnr_db"])
                    for row in successful_embeds
                    if row["psnr_db"] is not None
                ]
            ),
            "ssim_mean": _mean(
                [
                    float(row["ssim"])
                    for row in successful_embeds
                    if row["ssim"] is not None
                ]
            ),
            "lpips_mean": _mean(
                [
                    float(row["lpips"])
                    for row in successful_embeds
                    if row["lpips"] is not None
                ]
            ),
            "embed_latency_ms_mean": _mean(
                [
                    float(row["embed_latency_ms"])
                    for row in successful_embeds
                    if row["embed_latency_ms"] is not None
                ]
            ),
        },
        "native_wam_by_attack": by_attack,
        "original_image_negative_controls": {
            "rows": len(negative_rows),
            "pipeline_failure_rate": _mean(
                [
                    float(row.get("pipeline_success") is not True)
                    for row in negative_rows
                ]
            ),
            "unique_samples": len({str(row["sample_id"]) for row in negative_rows}),
            "detected_area_fraction_mean": _mean(
                [
                    float(row["detected_area_fraction"])
                    for row in negative_rows
                    if row.get("pipeline_success") is True
                    and row["detected_area_fraction"] is not None
                ]
            ),
            "mean_probability_mean": _mean(
                [
                    float(row["mean_probability"])
                    for row in negative_rows
                    if row.get("pipeline_success") is True
                    and row["mean_probability"] is not None
                ]
            ),
            "p95_probability_mean": _mean(
                [
                    float(row["p95_probability"])
                    for row in negative_rows
                    if row.get("pipeline_success") is True
                    and row["p95_probability"] is not None
                ]
            ),
            "image_level_false_positive_rate": None,
            "image_level_false_positive_rate_status": (
                "not_computed_no_pinned_official_image_level_threshold"
            ),
        },
        "registry_metrics": "not_applicable",
        "cogniguard_64bit_hmac_capsule_equivalent": False,
    }


def _same_gt_mask(
    attack: AttackSpec,
    metadata: dict[str, Any],
    size: tuple[int, int],
) -> np.ndarray | None:
    if attack.name == "clean":
        return np.zeros((size[1], size[0]), dtype=np.bool_)
    bbox = metadata.get("truth_bbox")
    if not bbox:
        return None
    truth = truth_mask_from_half_open_bbox(size, bbox)
    return np.asarray(truth, dtype=np.uint8) >= 128


class WamManifestRunner:
    def __init__(
        self,
        config_path: str | Path,
        output_dir: str | Path,
        adapter: WamOfficialAdapter,
        *,
        mode: str,
        manifest_path: str | Path | None = None,
        split: str | None = None,
        seeds: Sequence[int] | None = None,
        attack_ids: Sequence[str] | None = None,
        limit: int = 0,
        lpips_enabled: bool = True,
        allow_test_backend: bool = False,
    ) -> None:
        self.config_path = Path(config_path).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.adapter = adapter
        self.mode = str(mode)
        if self.mode not in RUN_MODES:
            raise WamManifestError(f"mode must be one of {sorted(RUN_MODES)}.")
        self.manifest_override = (
            None
            if manifest_path is None
            else Path(manifest_path).expanduser().resolve()
        )
        self.split_override = split
        self.seed_override = None if seeds is None else [int(seed) for seed in seeds]
        self.attack_filter = None if attack_ids is None else set(attack_ids)
        self.limit = int(limit)
        self.lpips_enabled = bool(lpips_enabled)
        self.allow_test_backend = bool(allow_test_backend)
        self._manifest_lock_audit: dict[str, Any] | None = None
        self._input_resolution_audit: dict[str, Any] = {}
        self._formal_selection_capabilities: dict[str, Any] | None = None

        provenance = self.adapter.backend.runtime_provenance()
        real_runtime = bool(
            isinstance(self.adapter.backend, OfficialWamBackend)
            and provenance.get("real_official_runtime") is True
            and provenance.get("adapter_backend_injected") is False
        )
        if not self.allow_test_backend and not real_runtime:
            raise WamManifestError(
                "A manifest run requires the preflighted OfficialWamBackend; "
                "injected/mock backends are test-only and require "
                "allow_test_backend=True."
            )
        self._real_official_runtime = real_runtime
        self._paper_eligible_runtime = bool(
            real_runtime and not self.allow_test_backend
        )

        if self.mode == "formal":
            selectors = {
                "manifest override": self.manifest_override is not None,
                "split override": self.split_override is not None,
                "seed override": self.seed_override is not None,
                "attack filter": self.attack_filter is not None,
                "limit": self.limit != 0,
                "LPIPS disabled": not self.lpips_enabled,
            }
            forbidden = [name for name, present in selectors.items() if present]
            if forbidden:
                raise WamManifestError(
                    "formal mode forbids partial/override selectors: "
                    + ", ".join(forbidden)
                )
        elif self.limit <= 0:
            raise WamManifestError("smoke mode requires an explicit positive limit.")

    def _inputs(
        self,
    ) -> tuple[
        dict[str, Any],
        Path,
        list[ImageSample],
        list[ImageSample],
        list[AttackSpec],
        list[int],
    ]:
        try:
            config = (
                yaml.safe_load(
                    os.path.expandvars(self.config_path.read_text(encoding="utf-8"))
                )
                or {}
            )
            if not isinstance(config, dict):
                raise ValueError("Benchmark YAML root must be a mapping.")
            manifest_config = dict(config.get("manifest") or {})
            # A formal baseline is bound to the explicitly reviewed benchmark
            # YAML.  In particular, a sourced secure environment must not
            # silently redirect it to a different manifest or dataset roots.
            resolution_environ = {} if self.mode == "formal" else None
            manifest_path = self.manifest_override or manifest_path_from_config(
                self.config_path,
                environ=resolution_environ,
            )
            roots = dataset_roots_from_config(
                self.config_path,
                environ=resolution_environ,
            )
            all_rows = load_manifest(
                manifest_path,
                dataset_roots=roots,
                require_files=True,
                verify_hashes=bool(manifest_config.get("verify_hashes", True)),
            )
            self._manifest_lock_audit = None
            if self.mode == "formal":
                if manifest_config.get("require_lock") is not True:
                    raise ValueError(
                        "Formal benchmark manifest.require_lock must be true."
                    )
                self._manifest_lock_audit = validate_manifest_lock(
                    manifest_path,
                    all_rows,
                    config_path=self.config_path,
                    dataset_roots=roots,
                )
                if not self.allow_test_backend:
                    self._validate_formal_selected_config()
        except WamManifestError:
            raise
        except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
            raise WamManifestError(f"Dataset input resolution failed: {exc}") from exc
        self._input_resolution_audit = {
            "authority": (
                "explicit_benchmark_config_yaml"
                if self.mode == "formal"
                else "benchmark_config_with_documented_environment_overrides"
            ),
            "benchmark_config_authoritative": self.mode == "formal",
            "environment_overrides_allowed": self.mode != "formal",
            "ignored_environment_override_presence": {
                DATASET_MANIFEST_ENV: bool(
                    str(os.environ.get(DATASET_MANIFEST_ENV, "") or "").strip()
                )
                if self.mode == "formal"
                else False,
                DATASET_ROOTS_ENV: bool(
                    str(os.environ.get(DATASET_ROOTS_ENV, "") or "").strip()
                )
                if self.mode == "formal"
                else False,
            },
        }
        experiment = dict(config.get("experiment") or {})
        split = self.split_override or str(experiment.get("split") or "test")
        selected = sorted(
            (row for row in all_rows if row.split == split),
            key=lambda row: row.sample_id,
        )
        if self.limit < 0:
            raise WamManifestError("limit cannot be negative")
        if self.limit:
            selected = selected[: self.limit]
        if not selected:
            raise WamManifestError(f"No rows selected for split={split!r}.")

        specs = expand_attack_specs(
            list(((config.get("attacks") or {}).get("traditional") or []))
        )
        known = {_attack_id(spec) for spec in specs}
        if self.attack_filter is not None:
            unknown = sorted(self.attack_filter - known)
            if unknown:
                raise WamManifestError(
                    f"Unknown expanded traditional attacks: {unknown}"
                )
            specs = [spec for spec in specs if _attack_id(spec) in self.attack_filter]
        if not specs:
            raise WamManifestError("At least one traditional attack is required.")
        seeds = self.seed_override or [
            int(seed) for seed in (experiment.get("seeds") or [20260802])
        ]
        if not seeds or any(seed < 0 for seed in seeds):
            raise WamManifestError("Seeds must be non-negative integers.")
        if len(set(seeds)) != len(seeds):
            raise WamManifestError("Seeds must be unique.")

        if self.mode == "formal":
            self._validate_formal_inputs(
                config=config,
                all_rows=all_rows,
                selected=selected,
                specs=specs,
                seeds=seeds,
                split=split,
            )
        return config, manifest_path, all_rows, selected, specs, seeds

    def _validate_formal_selected_config(self) -> None:
        """Replay the selected channel-vote chain before granting formal status."""

        try:
            capabilities = validate_frozen_channel_vote_formal_config(self.config_path)
        except ChannelVoteFormalFreezeError as exc:
            raise WamManifestError(
                "Formal WAM benchmark is not an authentic channel-vote selected "
                f"configuration: {exc}"
            ) from exc
        self._formal_selection_capabilities = dict(capabilities)

    def _validate_formal_inputs(
        self,
        *,
        config: dict[str, Any],
        all_rows: list[ImageSample],
        selected: list[ImageSample],
        specs: list[AttackSpec],
        seeds: list[int],
        split: str,
    ) -> None:
        experiment = dict(config.get("experiment") or {})
        if experiment.get("strict_paper_mode") is not True:
            raise WamManifestError("formal mode requires strict_paper_mode=true.")
        if experiment.get("fail_fast") is not True:
            raise WamManifestError("formal mode requires fail_fast=true.")
        configured_split = str(experiment.get("split") or "")
        if split != "test" or configured_split != "test":
            raise WamManifestError(
                "formal mode is permanently bound to the test split."
            )
        if int(experiment.get("max_samples", 0) or 0) != 0:
            raise WamManifestError("formal mode requires experiment.max_samples=0.")
        metrics = dict(config.get("metrics") or {})
        lpips = dict(metrics.get("lpips") or {})
        if (
            metrics.get("require_reference_ssim") is not True
            or lpips.get("enabled") is not True
            or lpips.get("required") is not True
        ):
            raise WamManifestError(
                "formal mode requires reference SSIM and required shared LPIPS."
            )

        requirements = dict(config.get("data_requirements") or {})
        expected_total = int(requirements.get("expected_total_samples", 0) or 0)
        if expected_total != 3000 or len(all_rows) != expected_total:
            raise WamManifestError(
                "formal manifest must contain exactly 3000 rows; "
                f"configured={expected_total}, observed={len(all_rows)}."
            )
        sample_ids = [row.sample_id for row in all_rows]
        image_hashes = [row.sha256 for row in all_rows]
        if (
            len(set(sample_ids)) != 3000
            or len(set(image_hashes)) != 3000
            or any(not value for value in image_hashes)
        ):
            raise WamManifestError(
                "formal manifest requires 3000 unique sample IDs and image SHA256 values."
            )
        selected_ids = [row.sample_id for row in selected]
        if len(set(selected_ids)) != len(selected_ids):
            raise WamManifestError("formal selected test sample IDs are not unique.")
        enabled = [
            dict(item)
            for item in (config.get("datasets") or [])
            if bool((item or {}).get("enabled", False))
        ]
        quotas = {
            str(item.get("name") or ""): int(item.get("required_samples", 0) or 0)
            for item in enabled
        }
        if (
            len(enabled) != 4
            or len(quotas) != 4
            or "" in quotas
            or any(value <= 0 for value in quotas.values())
            or sum(quotas.values()) != 3000
        ):
            raise WamManifestError(
                "formal config must define four positive exact source quotas summing to 3000."
            )
        if quotas != FORMAL_SOURCE_QUOTAS:
            raise WamManifestError(
                "formal source quotas differ from the frozen 1200/600/400/800 contract: "
                f"{quotas}."
            )
        observed = Counter(row.source_dataset for row in all_rows)
        if dict(observed) != quotas:
            raise WamManifestError(
                f"formal source quotas mismatch: expected={quotas}, observed={dict(observed)}."
            )

        minimum_test = int(requirements.get("minimum_test_samples", 0) or 0)
        minimum_domains = int(requirements.get("minimum_domains", 0) or 0)
        minimum_datasets = int(requirements.get("minimum_datasets", 0) or 0)
        if minimum_test < 500 or len(selected) < minimum_test:
            raise WamManifestError(
                f"formal test gate requires at least {max(500, minimum_test)} rows; "
                f"observed={len(selected)}."
            )
        selected_sources = {row.source_dataset for row in selected}
        if minimum_datasets != 4 or selected_sources != set(quotas):
            raise WamManifestError(
                "formal test split must cover exactly all four configured sources."
            )
        if (
            minimum_domains < 4
            or len({row.domain for row in selected}) < minimum_domains
        ):
            raise WamManifestError("formal test split does not meet the domain gate.")

        configured_seeds = [int(value) for value in (experiment.get("seeds") or [])]
        if tuple(configured_seeds) != FORMAL_SEEDS or tuple(seeds) != FORMAL_SEEDS:
            raise WamManifestError(
                "formal mode requires the complete configured seed list."
            )
        configured_attacks = expand_attack_specs(
            list(((config.get("attacks") or {}).get("traditional") or []))
        )
        expected_attack_ids = [_attack_id(spec) for spec in configured_attacks]
        observed_attack_ids = [_attack_id(spec) for spec in specs]
        if (
            tuple(expected_attack_ids) != FORMAL_TRADITIONAL_ATTACK_IDS
            or tuple(observed_attack_ids) != FORMAL_TRADITIONAL_ATTACK_IDS
        ):
            raise WamManifestError(
                "formal mode requires the complete ordered traditional attack grid."
            )

    def run(self) -> dict[str, Any]:
        config, manifest_path, all_rows, samples, specs, seeds = self._inputs()
        if self.output_dir == self.output_dir.parent:
            raise WamManifestError("Output directory cannot be a filesystem root.")
        if self.output_dir.exists():
            raise WamManifestError(
                f"Refusing to overwrite an existing output path: {self.output_dir}"
            )
        self.output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging = self.output_dir.parent / (
            f".{_artifact_slug(self.output_dir.name)}.wam-tmp-{uuid.uuid4().hex}"
        )
        staging.mkdir(exist_ok=False)
        raw_path = staging / "raw_results.jsonl"
        raw_temporary = staging / ".raw_results.jsonl.tmp"
        negative_path = staging / "original_negative_controls.jsonl"
        negative_temporary = staging / ".original_negative_controls.jsonl.tmp"

        selected_ids = [sample.sample_id for sample in samples]
        selected_ids_digest = hashlib.sha256(
            "\n".join(selected_ids).encode("utf-8")
        ).hexdigest()
        adapter_source, adapter_sha = _source_file_sha256(WamOfficialAdapter)
        attacks_source, attacks_sha = _source_file_sha256(apply_traditional_attack)
        runner_source, runner_sha = _source_file_sha256(WamManifestRunner)
        source_counts = dict(Counter(row.source_dataset for row in all_rows))
        selected_source_counts = dict(Counter(row.source_dataset for row in samples))
        row_paper_eligible = bool(
            self.mode == "formal" and self._paper_eligible_runtime
        )
        configured_max_failure_rate = float(
            (config.get("experiment") or {}).get(
                "max_pipeline_failure_rate", FORMAL_MAX_PIPELINE_FAILURE_RATE
            )
        )
        if not 0.0 <= configured_max_failure_rate <= 1.0:
            raise WamManifestError(
                "experiment.max_pipeline_failure_rate must be in [0, 1]."
            )
        if (
            self.mode == "formal"
            and configured_max_failure_rate != FORMAL_MAX_PIPELINE_FAILURE_RATE
        ):
            raise WamManifestError(
                "formal mode freezes max_pipeline_failure_rate at 0.0."
            )
        attack_runtime = {
            "numpy_version": importlib.metadata.version("numpy"),
            "pillow_version": importlib.metadata.version("Pillow"),
            "required_numpy_version": "1.26.4",
            "required_pillow_version": "10.4.0",
        }
        environment = {
            "schema_version": "cogniguard.wam.manifest_environment.v2",
            "method_id": OFFICIAL_WAM_MIT.method_id,
            "mode": self.mode,
            "paper_eligible_on_complete": row_paper_eligible,
            "formal_max_pipeline_failure_rate": configured_max_failure_rate,
            "test_backend_allowed": self.allow_test_backend,
            "real_official_runtime": self._real_official_runtime,
            "scope": "same_manifest_frozen_test_traditional_attacks_only",
            "public_config_modified": False,
            "manifest_path": str(manifest_path),
            "manifest_sha256": _file_sha256(manifest_path),
            "manifest_lock": self._manifest_lock_audit,
            "input_resolution": self._input_resolution_audit,
            "manifest_total_samples": len(all_rows),
            "manifest_source_counts": source_counts,
            "benchmark_config_path": str(self.config_path),
            "benchmark_config_sha256": _file_sha256(self.config_path),
            "channel_vote_formal_selection_capabilities": (
                self._formal_selection_capabilities
            ),
            "evaluation_split": samples[0].split,
            "selected_samples": len(samples),
            "selected_source_counts": selected_source_counts,
            "selected_sample_ids_sha256": selected_ids_digest,
            "selected_sample_ids_sha256_semantics": (
                "sha256(utf8(newline_join(sorted_sample_ids))); no trailing newline"
            ),
            "seeds": seeds,
            "attack_ids": [_attack_id(spec) for spec in specs],
            "lpips_enabled": self.lpips_enabled,
            "native_semantics": NATIVE_SEMANTICS,
            "runtime_provenance": self.adapter.backend.runtime_provenance(),
            "local_source_sha256": {
                "wam_official_adapter": {"path": adapter_source, "sha256": adapter_sha},
                "traditional_attacks": {"path": attacks_source, "sha256": attacks_sha},
                "wam_manifest_runner": {"path": runner_source, "sha256": runner_sha},
            },
            "traditional_attack_runtime": attack_runtime,
            "artifact_retention": {
                "watermarked_clean_images": (
                    "hash_only_deleted_after_complete_attack_grid"
                    if self.mode == "formal"
                    else "retained"
                ),
                "nonclean_attacked_images": (
                    "hash_only_deleted_after_success"
                    if self.mode == "formal"
                    else "retained_for_smoke_diagnostics"
                ),
                "failed_attack_diagnostic": (
                    "retain_up_to_50_nonclean_failed_attacks_then_hash_only"
                ),
                "formal_failed_attack_diagnostic_limit": (
                    FORMAL_FAILED_ATTACK_DIAGNOSTIC_LIMIT
                ),
            },
            "formal_contract": {
                "global_manifest_exact_total": 3000 if self.mode == "formal" else None,
                "global_manifest_exact_source_counts": (
                    source_counts if self.mode == "formal" else None
                ),
                "frozen_test_sample_ids_sha256": selected_ids_digest,
                "complete_configured_seeds": self.mode == "formal",
                "complete_traditional_attack_grid": self.mode == "formal",
            },
            "limitations": [
                "AIGC attack artifacts are excluded until every method consumes the same attacked image and aligned GT mask.",
                "Native 32-bit exact recovery is not a CogniGuard 64-bit registry match.",
                "No image-level WAM presence/FPR threshold is invented; pixel score and area are primary.",
            ],
        }

        rows: list[dict[str, Any]] = []
        negative_rows: list[dict[str, Any]] = []
        retained_failed_attack_diagnostics = 0
        try:
            _atomic_write_json(staging / "environment.json", environment)
            selected_path = staging / "selected_test_samples.jsonl"
            selected_tmp = staging / ".selected_test_samples.jsonl.tmp"
            with selected_tmp.open("x", encoding="utf-8", newline="\n") as handle:
                for sample in samples:
                    handle.write(
                        json.dumps(
                            {
                                "sample_id": sample.sample_id,
                                "source_dataset": sample.source_dataset,
                                "domain": sample.domain,
                                "split": sample.split,
                                "source_sha256": sample.sha256,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )
            os.replace(selected_tmp, selected_path)

            with (
                raw_temporary.open("x", encoding="utf-8", newline="\n") as raw_handle,
                negative_temporary.open(
                    "x", encoding="utf-8", newline="\n"
                ) as negative_handle,
            ):
                for sample in samples:
                    with Image.open(sample.image_path) as source:
                        original = np.asarray(source.convert("RGB"), dtype=np.uint8)

                    negative_base = {
                        "schema_version": "cogniguard.wam.original_negative.v1",
                        "method_id": OFFICIAL_WAM_MIT.method_id,
                        "mode": self.mode,
                        "paper_eligible": row_paper_eligible,
                        "sample_id": sample.sample_id,
                        "source_dataset": sample.source_dataset,
                        "split": sample.split,
                        "source_sha256": sample.sha256,
                        "attacks_source_sha256": attacks_sha,
                        "attack_numpy_version": attack_runtime["numpy_version"],
                        "attack_pillow_version": attack_runtime["pillow_version"],
                        "control": "original_unwatermarked_image",
                        "image_level_watermark_present": None,
                    }
                    try:
                        negative_verified = self.adapter.verify(
                            original,
                            _native_message(sample.sample_id, seeds[0]),
                            attack_id="original_unwatermarked_negative_control",
                        )
                    except WamDependencyError:
                        raise
                    except Exception as exc:
                        negative_row = {
                            **negative_base,
                            "status": "inference_error",
                            "pipeline_success": False,
                            "paper_eligible": False,
                            "pixel_probability_threshold": 0.5,
                            "detected_area_fraction": None,
                            "mean_probability": None,
                            "max_probability": None,
                            "p95_probability": None,
                            "image_level_decision_status": "inference_failed",
                            "detect_aggregate_and_decode_latency_ms": None,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:2000],
                        }
                    else:
                        negative_detection = negative_verified.record[
                            "native_watermark_detection"
                        ]
                        negative_scores = negative_detection["presence_score_summary"]
                        negative_row = {
                            **negative_base,
                            "status": "ok",
                            "pipeline_success": True,
                            "pixel_probability_threshold": negative_detection[
                                "pixel_probability_threshold"
                            ],
                            "detected_area_fraction": negative_detection[
                                "detected_area_fraction"
                            ],
                            "mean_probability": negative_scores["mean_probability"],
                            "max_probability": negative_scores["max_probability"],
                            "p95_probability": negative_scores["p95_probability"],
                            "image_level_decision_status": negative_detection[
                                "image_level_decision_status"
                            ],
                            "detect_aggregate_and_decode_latency_ms": negative_verified.record[
                                "common_metrics"
                            ]["detect_aggregate_and_decode_latency_ms"],
                            "error_type": None,
                            "error": None,
                        }
                    negative_rows.append(negative_row)
                    negative_handle.write(
                        json.dumps(negative_row, ensure_ascii=False, sort_keys=True)
                        + "\n"
                    )
                    negative_handle.flush()

                    for seed in seeds:
                        message = _native_message(sample.sample_id, seed)
                        try:
                            embedded = self.adapter.embed(original, message)
                        except WamDependencyError:
                            raise
                        except Exception as exc:
                            for spec in specs:
                                attack_id = _attack_id(spec)
                                failure_row = {
                                    "schema_version": "cogniguard.wam.manifest_row.v2",
                                    "row_key": (
                                        f"{OFFICIAL_WAM_MIT.method_id}|{sample.sample_id}|{seed}|{attack_id}"
                                    ),
                                    "status": "inference_error",
                                    "pipeline_success": False,
                                    "embed_pipeline_success": False,
                                    "method_id": OFFICIAL_WAM_MIT.method_id,
                                    "mode": self.mode,
                                    "paper_eligible": False,
                                    "sample_id": sample.sample_id,
                                    "source_dataset": sample.source_dataset,
                                    "domain": sample.domain,
                                    "split": sample.split,
                                    "source_sha256": sample.sha256,
                                    "seed": seed,
                                    "attack_id": attack_id,
                                    "attack_name": spec.name,
                                    "attack_family": spec.family,
                                    "attack_params": {
                                        key: value
                                        for key, value in spec.params.items()
                                        if key != "expanded_name"
                                    },
                                    "attack_implementation_level": (
                                        "not_run_embed_inference_failed"
                                    ),
                                    "attack_truth_bbox": None,
                                    "attacked_image_sha256": None,
                                    "attacked_artifact_retention": "not_created",
                                    "attacks_source_sha256": attacks_sha,
                                    "attack_numpy_version": attack_runtime[
                                        "numpy_version"
                                    ],
                                    "attack_pillow_version": attack_runtime[
                                        "pillow_version"
                                    ],
                                    "native_message_bits": 32,
                                    "native_message_derivation": (
                                        "sha256('wam-native-32|seed|sample_id')[:32 bits]; no registry"
                                    ),
                                    "native_decode_available": False,
                                    "native_32bit_raw_bit_accuracy": None,
                                    "native_32bit_raw_bit_accuracy_strict": 0.0,
                                    "native_32bit_raw_exact": False,
                                    "native_watermark_area_fraction": None,
                                    "native_watermark_mean_probability": None,
                                    "native_watermark_max_probability": None,
                                    "native_watermark_p95_probability": None,
                                    "image_level_watermark_present": None,
                                    "image_level_decision_status": "inference_failed",
                                    "localization_same_attack_gt": None,
                                    "psnr_db": None,
                                    "ssim": None,
                                    "lpips": None,
                                    "embed_latency_ms": None,
                                    "detect_aggregate_and_decode_latency_ms": None,
                                    "detect_and_decode_latency_ms": None,
                                    "watermarked_image_path": None,
                                    "watermarked_image_sha256": None,
                                    "watermarked_image_bytes": None,
                                    "watermarked_artifact_retention": "not_created",
                                    "attacked_image_path": None,
                                    "registry_mapping": "none",
                                    "registry_lookup_performed": False,
                                    "cogniguard_64bit_hmac_capsule_equivalent": False,
                                    "error_stage": "embed_inference",
                                    "error_type": type(exc).__name__,
                                    "error": str(exc)[:2000],
                                }
                                rows.append(failure_row)
                                raw_handle.write(
                                    json.dumps(
                                        failure_row,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                    )
                                    + "\n"
                                )
                                raw_handle.flush()
                            continue
                        relative_dir = (
                            Path("artifacts")
                            / _sample_slug(sample.sample_id)
                            / f"seed-{seed}"
                        )
                        sample_dir = staging / relative_dir
                        sample_dir.mkdir(parents=True, exist_ok=False)
                        relative_watermarked = relative_dir / "watermarked.png"
                        watermarked_path = staging / relative_watermarked
                        Image.fromarray(embedded.watermarked_image, mode="RGB").save(
                            watermarked_path
                        )
                        watermarked_image_sha256 = _file_sha256(watermarked_path)
                        watermarked_image_bytes = watermarked_path.stat().st_size
                        recorded_watermarked_path = (
                            None
                            if self.mode == "formal"
                            else relative_watermarked.as_posix()
                        )
                        watermarked_retention = (
                            "hash_only_deleted_after_complete_attack_grid"
                            if self.mode == "formal"
                            else "retained"
                        )
                        for spec in specs:
                            attack_id = _attack_id(spec)
                            if spec.name == "clean":
                                attacked = Image.fromarray(
                                    embedded.watermarked_image, mode="RGB"
                                )
                                metadata = {
                                    "attack_name": "clean",
                                    "attack_family": "clean",
                                    "params": {},
                                    "seed": seed,
                                    "implementation_level": "identity",
                                }
                                relative_attacked = relative_watermarked
                            else:
                                attacked, metadata = apply_traditional_attack(
                                    Image.fromarray(
                                        embedded.watermarked_image, mode="RGB"
                                    ),
                                    spec,
                                    seed=seed,
                                )
                                relative_attacked = relative_dir / (
                                    f"attack-{_artifact_slug(attack_id)}.png"
                                )
                                attacked.save(staging / relative_attacked)
                            attacked_array = np.asarray(
                                attacked.convert("RGB"), dtype=np.uint8
                            )
                            attacked_image_sha256 = _image_sha256(attacked)
                            gt = _same_gt_mask(spec, metadata, attacked.size)
                            try:
                                verified = self.adapter.verify(
                                    attacked_array,
                                    message,
                                    attack_gt_tamper_mask=gt,
                                    attack_id=attack_id,
                                )
                            except WamDependencyError:
                                raise
                            except Exception as exc:
                                if self.mode == "formal":
                                    if spec.name == "clean":
                                        failed_attacked_path = None
                                        failed_retention = "hash_only_shared_watermarked_deleted_after_grid"
                                    elif (
                                        retained_failed_attack_diagnostics
                                        < FORMAL_FAILED_ATTACK_DIAGNOSTIC_LIMIT
                                    ):
                                        failed_attacked_path: str | None = (
                                            relative_attacked.as_posix()
                                        )
                                        failed_retention = (
                                            "retained_failed_inference_diagnostic"
                                        )
                                        retained_failed_attack_diagnostics += 1
                                    else:
                                        (staging / relative_attacked).unlink()
                                        failed_attacked_path = None
                                        failed_retention = (
                                            "hash_only_failed_diagnostic_limit_reached"
                                        )
                                else:
                                    failed_attacked_path = relative_attacked.as_posix()
                                    failed_retention = (
                                        "retained_failed_inference_diagnostic"
                                    )
                                common_embed = embedded.record["common_metrics"]
                                failure_row = {
                                    "schema_version": "cogniguard.wam.manifest_row.v2",
                                    "row_key": (
                                        f"{OFFICIAL_WAM_MIT.method_id}|{sample.sample_id}|{seed}|{attack_id}"
                                    ),
                                    "status": "inference_error",
                                    "pipeline_success": False,
                                    "embed_pipeline_success": True,
                                    "method_id": OFFICIAL_WAM_MIT.method_id,
                                    "mode": self.mode,
                                    "paper_eligible": False,
                                    "sample_id": sample.sample_id,
                                    "source_dataset": sample.source_dataset,
                                    "domain": sample.domain,
                                    "split": sample.split,
                                    "source_sha256": sample.sha256,
                                    "seed": seed,
                                    "attack_id": attack_id,
                                    "attack_name": spec.name,
                                    "attack_family": metadata["attack_family"],
                                    "attack_params": {
                                        key: value
                                        for key, value in spec.params.items()
                                        if key != "expanded_name"
                                    },
                                    "attack_implementation_level": metadata[
                                        "implementation_level"
                                    ],
                                    "attack_truth_bbox": metadata.get("truth_bbox"),
                                    "attacked_image_sha256": attacked_image_sha256,
                                    "attacked_artifact_retention": failed_retention,
                                    "attacks_source_sha256": attacks_sha,
                                    "attack_numpy_version": attack_runtime[
                                        "numpy_version"
                                    ],
                                    "attack_pillow_version": attack_runtime[
                                        "pillow_version"
                                    ],
                                    "native_message_bits": 32,
                                    "native_message_derivation": (
                                        "sha256('wam-native-32|seed|sample_id')[:32 bits]; no registry"
                                    ),
                                    "native_decode_available": False,
                                    "native_32bit_raw_bit_accuracy": None,
                                    "native_32bit_raw_bit_accuracy_strict": 0.0,
                                    "native_32bit_raw_exact": False,
                                    "native_watermark_area_fraction": None,
                                    "native_watermark_mean_probability": None,
                                    "native_watermark_max_probability": None,
                                    "native_watermark_p95_probability": None,
                                    "image_level_watermark_present": None,
                                    "image_level_decision_status": "inference_failed",
                                    "localization_same_attack_gt": None,
                                    "psnr_db": common_embed["psnr_db"],
                                    "ssim": common_embed["ssim"],
                                    "lpips": common_embed["lpips"],
                                    "embed_latency_ms": common_embed[
                                        "embed_latency_ms"
                                    ],
                                    "detect_aggregate_and_decode_latency_ms": None,
                                    "detect_and_decode_latency_ms": None,
                                    "watermarked_image_path": recorded_watermarked_path,
                                    "watermarked_image_sha256": (
                                        watermarked_image_sha256
                                    ),
                                    "watermarked_image_bytes": watermarked_image_bytes,
                                    "watermarked_artifact_retention": (
                                        watermarked_retention
                                    ),
                                    "attacked_image_path": failed_attacked_path,
                                    "registry_mapping": "none",
                                    "registry_lookup_performed": False,
                                    "cogniguard_64bit_hmac_capsule_equivalent": False,
                                    "error_stage": "verify_inference",
                                    "error_type": type(exc).__name__,
                                    "error": str(exc)[:2000],
                                }
                                rows.append(failure_row)
                                raw_handle.write(
                                    json.dumps(
                                        failure_row,
                                        ensure_ascii=False,
                                        sort_keys=True,
                                    )
                                    + "\n"
                                )
                                raw_handle.flush()
                                continue
                            if self.mode == "formal":
                                recorded_attacked_path: str | None = None
                                if spec.name != "clean":
                                    (staging / relative_attacked).unlink()
                                    attacked_retention = (
                                        "hash_only_deleted_after_successful_verify"
                                    )
                                else:
                                    attacked_retention = "hash_only_shared_watermarked_deleted_after_grid"
                            else:
                                recorded_attacked_path = relative_attacked.as_posix()
                                attacked_retention = "retained"
                            recovery = verified.record["native_32bit_message_recovery"]
                            detection = verified.record["native_watermark_detection"]
                            presence_scores = detection["presence_score_summary"]
                            common_embed = embedded.record["common_metrics"]
                            row = {
                                "schema_version": "cogniguard.wam.manifest_row.v2",
                                "row_key": (
                                    f"{OFFICIAL_WAM_MIT.method_id}|{sample.sample_id}|{seed}|{attack_id}"
                                ),
                                "method_id": OFFICIAL_WAM_MIT.method_id,
                                "status": "ok",
                                "pipeline_success": True,
                                "embed_pipeline_success": True,
                                "mode": self.mode,
                                "paper_eligible": row_paper_eligible,
                                "sample_id": sample.sample_id,
                                "source_dataset": sample.source_dataset,
                                "domain": sample.domain,
                                "split": sample.split,
                                "source_sha256": sample.sha256,
                                "seed": seed,
                                "attack_id": attack_id,
                                "attack_name": spec.name,
                                "attack_family": metadata["attack_family"],
                                "attack_params": {
                                    key: value
                                    for key, value in spec.params.items()
                                    if key != "expanded_name"
                                },
                                "attack_implementation_level": metadata[
                                    "implementation_level"
                                ],
                                "attack_truth_bbox": metadata.get("truth_bbox"),
                                "attacked_image_sha256": attacked_image_sha256,
                                "attacked_artifact_retention": attacked_retention,
                                "attacks_source_sha256": attacks_sha,
                                "attack_numpy_version": attack_runtime["numpy_version"],
                                "attack_pillow_version": attack_runtime[
                                    "pillow_version"
                                ],
                                "native_message_bits": 32,
                                "native_message_derivation": (
                                    "sha256('wam-native-32|seed|sample_id')[:32 bits]; no registry"
                                ),
                                "native_decode_available": recovery["recovered_bits"]
                                is not None,
                                "native_32bit_raw_bit_accuracy": recovery[
                                    "raw_bit_accuracy"
                                ],
                                "native_32bit_raw_bit_accuracy_strict": (
                                    0.0
                                    if recovery["raw_bit_accuracy"] is None
                                    else float(recovery["raw_bit_accuracy"])
                                ),
                                "native_32bit_raw_exact": recovery["raw_exact"],
                                "native_watermark_area_fraction": detection[
                                    "detected_area_fraction"
                                ],
                                "native_watermark_mean_probability": presence_scores[
                                    "mean_probability"
                                ],
                                "native_watermark_max_probability": presence_scores[
                                    "max_probability"
                                ],
                                "native_watermark_p95_probability": presence_scores[
                                    "p95_probability"
                                ],
                                "image_level_watermark_present": None,
                                "image_level_decision_status": detection[
                                    "image_level_decision_status"
                                ],
                                "localization_same_attack_gt": verified.record[
                                    "localization_same_attack_gt"
                                ],
                                "psnr_db": common_embed["psnr_db"],
                                "ssim": common_embed["ssim"],
                                "lpips": common_embed["lpips"],
                                "embed_latency_ms": common_embed["embed_latency_ms"],
                                "detect_aggregate_and_decode_latency_ms": verified.record[
                                    "common_metrics"
                                ]["detect_aggregate_and_decode_latency_ms"],
                                "detect_and_decode_latency_ms": verified.record[
                                    "common_metrics"
                                ]["detect_and_decode_latency_ms"],
                                "watermarked_image_path": recorded_watermarked_path,
                                "watermarked_image_sha256": watermarked_image_sha256,
                                "watermarked_image_bytes": watermarked_image_bytes,
                                "watermarked_artifact_retention": watermarked_retention,
                                "attacked_image_path": recorded_attacked_path,
                                "registry_mapping": "none",
                                "registry_lookup_performed": False,
                                "cogniguard_64bit_hmac_capsule_equivalent": False,
                                "error_stage": None,
                                "error_type": None,
                                "error": None,
                            }
                            rows.append(row)
                            raw_handle.write(
                                json.dumps(row, ensure_ascii=False, sort_keys=True)
                                + "\n"
                            )
                            raw_handle.flush()
                        if self.mode == "formal":
                            watermarked_path.unlink()
            os.replace(raw_temporary, raw_path)
            os.replace(negative_temporary, negative_path)

            expected_rows = len(samples) * len(seeds) * len(specs)
            expected_row_keys = {
                f"{OFFICIAL_WAM_MIT.method_id}|{sample.sample_id}|{seed}|{_attack_id(spec)}"
                for sample in samples
                for seed in seeds
                for spec in specs
            }
            observed_row_keys = [str(row["row_key"]) for row in rows]
            if (
                len(rows) != expected_rows
                or len(set(observed_row_keys)) != expected_rows
                or set(observed_row_keys) != expected_row_keys
                or len(negative_rows) != len(samples)
            ):
                raise WamManifestError(
                    "Incomplete WAM grid or original-negative controls: "
                    f"expected rows={expected_rows}/negatives={len(samples)}, "
                    f"observed rows={len(rows)}/negatives={len(negative_rows)}."
                )
            summary = _summarize(rows, negative_rows)
            max_failure_rate = configured_max_failure_rate
            row_failure_rate = float(summary["pipeline_failure_rate"] or 0.0)
            negative_failure_rate = float(
                summary["original_image_negative_controls"]["pipeline_failure_rate"]
                or 0.0
            )
            observed_failure_rate = max(row_failure_rate, negative_failure_rate)
            final_paper_eligible = bool(
                row_paper_eligible and observed_failure_rate <= max_failure_rate
            )
            if self.mode == "smoke":
                paper_claim_status = "invalid_smoke_run"
            elif not self._paper_eligible_runtime:
                paper_claim_status = "invalid_test_or_injected_backend"
            elif observed_failure_rate > max_failure_rate:
                paper_claim_status = (
                    "invalid_pipeline_failure_rate_exceeds_formal_limit"
                )
            else:
                paper_claim_status = (
                    "eligible_audited_formal_traditional_scope_complete"
                )
            if row_paper_eligible and not final_paper_eligible:
                revised_raw = staging / ".raw_results.paper-status.tmp"
                with revised_raw.open("x", encoding="utf-8", newline="\n") as handle:
                    for row in rows:
                        row["paper_eligible"] = False
                        handle.write(
                            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                        )
                os.replace(revised_raw, raw_path)
                revised_negative = staging / ".negative_controls.paper-status.tmp"
                with revised_negative.open(
                    "x", encoding="utf-8", newline="\n"
                ) as handle:
                    for row in negative_rows:
                        row["paper_eligible"] = False
                        handle.write(
                            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                        )
                os.replace(revised_negative, negative_path)
            summary.update(
                {
                    "manifest_sha256": environment["manifest_sha256"],
                    "benchmark_config_sha256": environment["benchmark_config_sha256"],
                    "channel_vote_formal_selection_capabilities": (
                        self._formal_selection_capabilities
                    ),
                    "mode": self.mode,
                    "paper_eligible": final_paper_eligible,
                    "paper_eligibility_status": (
                        "audited_formal_traditional_scope_complete"
                        if final_paper_eligible
                        else paper_claim_status
                    ),
                    "paper_claim_status": paper_claim_status,
                    "formal_max_pipeline_failure_rate": max_failure_rate,
                    "observed_claim_failure_rate": observed_failure_rate,
                    "retained_failed_attack_diagnostics": (
                        retained_failed_attack_diagnostics
                    ),
                    "scope": environment["scope"],
                    "expected_rows": expected_rows,
                    "observed_rows": len(rows),
                    "selected_sample_ids_sha256": selected_ids_digest,
                    "aigc_included": False,
                    "full_public_attack_suite_complete": False,
                    "output_directory_atomic_publish": True,
                    "output_files": {
                        "raw_results": "raw_results.jsonl",
                        "original_negative_controls": (
                            "original_negative_controls.jsonl"
                        ),
                        "selected_test_samples": "selected_test_samples.jsonl",
                        "environment": "environment.json",
                        "summary": "summary.json",
                    },
                }
            )
            _atomic_write_json(staging / "summary.json", summary)
            if self.output_dir.exists():
                raise WamManifestError(
                    f"Output path appeared during the run; refusing overwrite: {self.output_dir}"
                )
            staging.rename(self.output_dir)
            return summary
        except BaseException:
            if staging.exists():
                shutil.rmtree(staging)
            raise


def _shared_adapter(
    backend: OfficialWamBackend,
    config_path: Path,
    *,
    skip_lpips: bool,
) -> WamOfficialAdapter:
    config = (
        yaml.safe_load(os.path.expandvars(config_path.read_text(encoding="utf-8")))
        or {}
    )

    def ssim_evaluator(reference: np.ndarray, candidate: np.ndarray) -> float:
        metrics = image_quality_metrics(
            Image.fromarray(reference, mode="RGB"),
            Image.fromarray(candidate, mode="RGB"),
        )
        return float(metrics["ssim"])

    lpips_evaluator = None
    lpips_config = dict(((config.get("metrics") or {}).get("lpips") or {}))
    if bool(lpips_config.get("enabled", False)) and not skip_lpips:
        evaluator = LPIPSEvaluator(
            network=str(lpips_config.get("network") or "alex"),
            device=str(lpips_config.get("device") or "auto"),
        )

        def lpips_evaluator(reference: np.ndarray, candidate: np.ndarray) -> float:
            return evaluator(
                Image.fromarray(reference, mode="RGB"),
                Image.fromarray(candidate, mode="RGB"),
            )

    return WamOfficialAdapter(
        backend,
        ssim_evaluator=ssim_evaluator,
        lpips_evaluator=lpips_evaluator,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=sorted(RUN_MODES),
        required=True,
        help="formal enforces the complete frozen protocol; smoke is never paper-eligible.",
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--benchmark-config", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--split")
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument(
        "--attack",
        action="append",
        help="Expanded traditional attack id; repeat. Omit for the full traditional grid.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--skip-lpips",
        action="store_true",
        help="Smoke only. Results explicitly retain lpips=null.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    backend = OfficialWamBackend(args.repo_root, args.checkpoint, device=args.device)
    adapter = _shared_adapter(
        backend, args.benchmark_config.resolve(), skip_lpips=args.skip_lpips
    )
    runner = WamManifestRunner(
        args.benchmark_config,
        args.output_dir,
        adapter,
        mode=args.mode,
        manifest_path=args.manifest,
        split=args.split,
        seeds=args.seed,
        attack_ids=args.attack,
        limit=args.limit,
        lpips_enabled=not args.skip_lpips,
    )
    summary = runner.run()
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
