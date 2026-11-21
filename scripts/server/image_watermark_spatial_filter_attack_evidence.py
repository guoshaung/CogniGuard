"""Independent attack-input authentication for the v3 spatial-filter protocol.

The benchmark retains each clean watermarked PNG but deliberately removes the
three reproducible erasing PNGs after verification.  This module rebuilds those
erasing inputs from the retained clean image and authenticates the raw-row
attack parameters, truth boxes, and input SHA-256 values before any localization
metric is trusted.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import (
    AttackSpec,
    apply_traditional_attack,
    truth_mask_from_half_open_bbox,
)


ATTACK_EVIDENCE_SCHEMA_VERSION = (
    "cogniguard_image_spatial_filter_attack_evidence_v1"
)
SPATIAL_FILTER_ATTACK_IDS = (
    "clean",
    "erasing__area_ratio-0.05",
    "erasing__area_ratio-0.15",
    "erasing__area_ratio-0.25",
)
ERASING_RATIO_BY_ATTACK_ID = {
    "erasing__area_ratio-0.05": 0.05,
    "erasing__area_ratio-0.15": 0.15,
    "erasing__area_ratio-0.25": 0.25,
}
ATTACK_ARTIFACT_RETENTION = "hash_only"


class SpatialFilterAttackEvidenceError(RuntimeError):
    """Raised when a raw attack row cannot be independently authenticated."""


@dataclass(frozen=True, slots=True)
class SpatialFilterAttackEvidenceValidation:
    """Authenticated attack map and its path-independent canonical identity."""

    authenticated_attack_map: dict[tuple[str, int, str], dict[str, Any]]
    canonical_identity_sha256: str


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _valid_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction is not None and is_junction())


def _absolute_lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_real_benchmark_root(value: str | Path) -> tuple[Path, Path]:
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise SpatialFilterAttackEvidenceError(
            "benchmark_root must be an absolute candidate-local directory."
        )
    lexical = _absolute_lexical_path(raw)
    try:
        metadata = lexical.lstat()
    except OSError as exc:
        raise SpatialFilterAttackEvidenceError(
            f"benchmark_root is unavailable: {lexical}"
        ) from exc
    if _link_like(lexical) or not stat.S_ISDIR(metadata.st_mode):
        raise SpatialFilterAttackEvidenceError(
            f"benchmark_root must be a real, non-symlink directory: {lexical}"
        )
    return lexical, lexical.resolve(strict=True)


def _require_regular_file_within(
    value: object,
    *,
    lexical_root: Path,
    resolved_root: Path,
    label: str,
) -> Path:
    if type(value) is not str or not value:
        raise SpatialFilterAttackEvidenceError(f"{label} path is missing.")
    raw = Path(value).expanduser()
    if not raw.is_absolute():
        raise SpatialFilterAttackEvidenceError(f"{label} path must be absolute.")
    lexical = _absolute_lexical_path(raw)
    try:
        relative = lexical.relative_to(lexical_root)
    except ValueError as exc:
        raise SpatialFilterAttackEvidenceError(
            f"{label} escapes benchmark_root: {lexical}"
        ) from exc
    if not relative.parts:
        raise SpatialFilterAttackEvidenceError(f"{label} is not a file path.")

    current = lexical_root
    for index, component in enumerate(relative.parts):
        current = current / component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise SpatialFilterAttackEvidenceError(
                f"{label} is unavailable: {current}"
            ) from exc
        if _link_like(current):
            raise SpatialFilterAttackEvidenceError(
                f"{label} traverses a symlink or junction: {current}"
            )
        final_component = index == len(relative.parts) - 1
        expected_kind = (
            stat.S_ISREG(metadata.st_mode)
            if final_component
            else stat.S_ISDIR(metadata.st_mode)
        )
        if not expected_kind:
            kind = "regular file" if final_component else "directory"
            raise SpatialFilterAttackEvidenceError(
                f"{label} component is not a {kind}: {current}"
            )

    resolved = lexical.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:  # pragma: no cover - protected by component checks
        raise SpatialFilterAttackEvidenceError(
            f"{label} resolves outside benchmark_root: {resolved}"
        ) from exc
    return resolved


def _sha256_stable_file(path: Path, *, label: str) -> str:
    try:
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        raise SpatialFilterAttackEvidenceError(
            f"Unable to hash {label}: {path}"
        ) from exc
    stable_fields = ("st_size", "st_mtime_ns", "st_ino")
    if any(
        getattr(before, field, None) != getattr(after, field, None)
        for field in stable_fields
    ):
        raise SpatialFilterAttackEvidenceError(
            f"{label} changed while its SHA-256 was computed: {path}"
        )
    return digest.hexdigest()


def _png_sha256(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _sample_field(sample: object, name: str) -> object:
    if isinstance(sample, Mapping):
        return sample.get(name)
    return getattr(sample, name, None)


def _normalized_samples(sample_by_id: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(sample_by_id, Mapping) or not sample_by_id:
        raise SpatialFilterAttackEvidenceError("sample_by_id must be non-empty.")
    normalized: dict[str, object] = {}
    for raw_sample_id, sample in sample_by_id.items():
        if type(raw_sample_id) is not str or not raw_sample_id:
            raise SpatialFilterAttackEvidenceError(
                "sample_by_id keys must be non-empty strings."
            )
        declared_id = _sample_field(sample, "sample_id")
        declared_sha256 = _sample_field(sample, "sha256")
        if declared_id != raw_sample_id or not _valid_sha256(declared_sha256):
            raise SpatialFilterAttackEvidenceError(
                f"sample_by_id identity is invalid for {raw_sample_id!r}."
            )
        normalized[raw_sample_id] = sample
    return normalized


def _normalized_seeds(expected_seeds: Sequence[int]) -> tuple[int, ...]:
    if isinstance(expected_seeds, (str, bytes)):
        raise SpatialFilterAttackEvidenceError("expected_seeds must be integers.")
    seeds = tuple(expected_seeds)
    if (
        not seeds
        or any(type(seed) is not int or seed < 0 for seed in seeds)
        or len(set(seeds)) != len(seeds)
    ):
        raise SpatialFilterAttackEvidenceError(
            "expected_seeds must be unique non-negative integers."
        )
    return seeds


def _normalized_attack_ids(expected_attack_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(expected_attack_ids, (str, bytes)):
        raise SpatialFilterAttackEvidenceError("expected_attack_ids must be a sequence.")
    attack_ids = tuple(expected_attack_ids)
    if attack_ids != SPATIAL_FILTER_ATTACK_IDS:
        raise SpatialFilterAttackEvidenceError(
            "expected_attack_ids differ from the frozen clean/three-erasing grid."
        )
    return attack_ids


def _index_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    samples: Mapping[str, object],
    seeds: tuple[int, ...],
    attack_ids: tuple[str, ...],
) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    expected_keys = {
        (sample_id, seed, attack_id)
        for sample_id in samples
        for seed in seeds
        for attack_id in attack_ids
    }
    indexed: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, Mapping):
            raise SpatialFilterAttackEvidenceError(
                f"Raw attack row {index} is not a mapping."
            )
        sample_id = row.get("sample_id")
        seed = row.get("seed")
        attack_id = row.get("attack_id")
        if (
            type(sample_id) is not str
            or type(seed) is not int
            or type(attack_id) is not str
        ):
            raise SpatialFilterAttackEvidenceError(
                f"Raw attack row {index} has malformed identity fields."
            )
        key = (sample_id, seed, attack_id)
        if key not in expected_keys or key in indexed:
            raise SpatialFilterAttackEvidenceError(
                f"Raw attack row cross-product identity is invalid: {key!r}."
            )
        sample_sha256 = _sample_field(samples[sample_id], "sha256")
        if row.get("image_sha256") != sample_sha256:
            raise SpatialFilterAttackEvidenceError(
                f"Raw attack row source-image SHA-256 is invalid: {key!r}."
            )
        indexed[key] = row
    if set(indexed) != expected_keys:
        missing = sorted(expected_keys - set(indexed))
        raise SpatialFilterAttackEvidenceError(
            f"Raw attack-row cross product is incomplete; first missing={missing[:3]!r}."
        )
    return indexed


def _require_common_row_fields(
    row: Mapping[str, Any],
    *,
    key: tuple[str, int, str],
) -> str:
    attacked_sha256 = row.get("attacked_image_sha256")
    if not _valid_sha256(attacked_sha256):
        raise SpatialFilterAttackEvidenceError(
            f"Attacked-image SHA-256 is malformed: {key!r}."
        )
    if row.get("traditional_attack_artifact_retention") != ATTACK_ARTIFACT_RETENTION:
        raise SpatialFilterAttackEvidenceError(
            f"Attack artifact-retention contract is invalid: {key!r}."
        )
    return attacked_sha256


def _authenticate_clean_row(
    row: Mapping[str, Any],
    *,
    key: tuple[str, int, str],
    lexical_root: Path,
    resolved_root: Path,
) -> tuple[Image.Image, dict[str, Any]]:
    attacked_sha256 = _require_common_row_fields(row, key=key)
    if (
        row.get("attack_name") != "clean"
        or row.get("attack_family") != "clean"
        or type(row.get("attack_params")) is not dict
        or row.get("attack_params") != {}
        or row.get("attack_implementation_level") != "identity"
        or row.get("attack_truth_bbox") is not None
        or row.get("attacked_image_retained") is not True
    ):
        raise SpatialFilterAttackEvidenceError(
            f"Clean attack declaration is invalid: {key!r}."
        )
    clean_path = _require_regular_file_within(
        row.get("attacked_image_path"),
        lexical_root=lexical_root,
        resolved_root=resolved_root,
        label=f"Clean watermarked image {key!r}",
    )
    if _sha256_stable_file(clean_path, label="clean watermarked image") != attacked_sha256:
        raise SpatialFilterAttackEvidenceError(
            f"Clean watermarked-image SHA-256 differs from its retained file: {key!r}."
        )
    try:
        with Image.open(clean_path) as handle:
            watermarked = handle.convert("RGB").copy()
    except OSError as exc:
        raise SpatialFilterAttackEvidenceError(
            f"Clean watermarked image is unreadable: {key!r}."
        ) from exc
    return watermarked, {
        "attacked_image_sha256": attacked_sha256,
        "attack_truth_bbox": None,
    }


def _authenticate_erasing_row(
    row: Mapping[str, Any],
    *,
    key: tuple[str, int, str],
    watermarked: Image.Image,
    ratio: float,
) -> dict[str, Any]:
    attacked_sha256 = _require_common_row_fields(row, key=key)
    params = row.get("attack_params")
    if (
        row.get("attack_name") != "erasing"
        or row.get("attack_family") != "removal"
        or type(params) is not dict
        or set(params) != {"area_ratio"}
        or type(params.get("area_ratio")) is not float
        or params.get("area_ratio") != ratio
        or row.get("attack_implementation_level") != "deterministic_transform"
        or row.get("attacked_image_retained") is not False
        or row.get("attacked_image_path") is not None
    ):
        raise SpatialFilterAttackEvidenceError(
            f"Erasing attack declaration is invalid: {key!r}."
        )

    attack_id = key[2]
    attacked, metadata = apply_traditional_attack(
        watermarked,
        AttackSpec(
            name="erasing",
            family="removal",
            params={"area_ratio": ratio, "expanded_name": attack_id},
        ),
        seed=key[1],
    )
    expected_bbox = metadata.get("truth_bbox")
    observed_bbox = row.get("attack_truth_bbox")
    if (
        type(observed_bbox) is not list
        or len(observed_bbox) != 4
        or any(type(value) is not int for value in observed_bbox)
        or observed_bbox != expected_bbox
    ):
        raise SpatialFilterAttackEvidenceError(
            f"Erasing truth bbox differs from deterministic replay: {key!r}."
        )
    try:
        truth_mask_from_half_open_bbox(watermarked.size, observed_bbox)
    except ValueError as exc:  # pragma: no cover - deterministic metadata is bounded
        raise SpatialFilterAttackEvidenceError(
            f"Erasing truth bbox is out of bounds: {key!r}."
        ) from exc
    if _png_sha256(attacked) != attacked_sha256:
        raise SpatialFilterAttackEvidenceError(
            f"Erasing PNG SHA-256 differs from deterministic replay: {key!r}."
        )
    return {
        "attacked_image_sha256": attacked_sha256,
        "attack_truth_bbox": list(observed_bbox),
    }


def validate_spatial_filter_attack_evidence(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    benchmark_root: str | Path,
    sample_by_id: Mapping[str, object],
    expected_seeds: Sequence[int],
    expected_attack_ids: Sequence[str],
) -> SpatialFilterAttackEvidenceValidation:
    """Authenticate the exact clean/erasing input cross product for one candidate.

    The returned identity excludes filesystem paths, so identities from separate
    candidate directories can be compared directly to prove byte-identical
    attack inputs and truth boxes.
    """

    lexical_root, resolved_root = _require_real_benchmark_root(benchmark_root)
    samples = _normalized_samples(sample_by_id)
    seeds = _normalized_seeds(expected_seeds)
    attack_ids = _normalized_attack_ids(expected_attack_ids)
    indexed = _index_rows(
        raw_rows,
        samples=samples,
        seeds=seeds,
        attack_ids=attack_ids,
    )

    authenticated: dict[tuple[str, int, str], dict[str, Any]] = {}
    for sample_id in sorted(samples):
        for seed in seeds:
            clean_key = (sample_id, seed, "clean")
            watermarked, clean_evidence = _authenticate_clean_row(
                indexed[clean_key],
                key=clean_key,
                lexical_root=lexical_root,
                resolved_root=resolved_root,
            )
            authenticated[clean_key] = clean_evidence
            for attack_id, ratio in ERASING_RATIO_BY_ATTACK_ID.items():
                key = (sample_id, seed, attack_id)
                authenticated[key] = _authenticate_erasing_row(
                    indexed[key],
                    key=key,
                    watermarked=watermarked,
                    ratio=ratio,
                )

    identity_rows = [
        {
            "sample_id": sample_id,
            "seed": seed,
            "attack_id": attack_id,
            **authenticated[(sample_id, seed, attack_id)],
        }
        for sample_id, seed, attack_id in sorted(authenticated)
    ]
    identity = _canonical_sha256(
        {
            "schema_version": ATTACK_EVIDENCE_SCHEMA_VERSION,
            "rows": identity_rows,
        }
    )
    return SpatialFilterAttackEvidenceValidation(
        authenticated_attack_map=authenticated,
        canonical_identity_sha256=identity,
    )


__all__ = [
    "ATTACK_EVIDENCE_SCHEMA_VERSION",
    "SPATIAL_FILTER_ATTACK_IDS",
    "SpatialFilterAttackEvidenceError",
    "SpatialFilterAttackEvidenceValidation",
    "validate_spatial_filter_attack_evidence",
]
