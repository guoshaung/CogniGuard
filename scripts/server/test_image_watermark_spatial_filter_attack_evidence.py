from __future__ import annotations

import copy
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import AttackSpec, apply_traditional_attack
from scripts.server.image_watermark_spatial_filter_attack_evidence import (
    SPATIAL_FILTER_ATTACK_IDS,
    SpatialFilterAttackEvidenceError,
    validate_spatial_filter_attack_evidence,
)


SEED = 20260802
SAMPLE_ID = "source:sample-001"
SOURCE_SHA256 = "1" * 64
RATIO_BY_ATTACK_ID = {
    "erasing__area_ratio-0.05": 0.05,
    "erasing__area_ratio-0.15": 0.15,
    "erasing__area_ratio-0.25": 0.25,
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_sha256(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _valid_bundle(tmp_path: Path) -> tuple[Path, list[dict], dict[str, object]]:
    benchmark_root = tmp_path / "candidate" / "benchmark"
    clean_path = benchmark_root / "api_jobs" / "embed_001" / "embed" / "watermarked.png"
    clean_path.parent.mkdir(parents=True)
    image = Image.new("RGB", (64, 64), (30, 80, 140))
    image.save(clean_path)

    common = {
        "sample_id": SAMPLE_ID,
        "seed": SEED,
        "image_sha256": SOURCE_SHA256,
        "traditional_attack_artifact_retention": "hash_only",
    }
    rows: list[dict] = [
        {
            **common,
            "attack_id": "clean",
            "attack_name": "clean",
            "attack_family": "clean",
            "attack_params": {},
            "attack_implementation_level": "identity",
            "attack_truth_bbox": None,
            "attacked_image_sha256": _file_sha256(clean_path),
            "attacked_image_path": str(clean_path),
            "attacked_image_retained": True,
        }
    ]
    for attack_id, ratio in RATIO_BY_ATTACK_ID.items():
        attacked, metadata = apply_traditional_attack(
            image,
            AttackSpec(
                name="erasing",
                family="removal",
                params={"area_ratio": ratio, "expanded_name": attack_id},
            ),
            seed=SEED,
        )
        rows.append(
            {
                **common,
                "attack_id": attack_id,
                "attack_name": "erasing",
                "attack_family": "removal",
                "attack_params": {"area_ratio": ratio},
                "attack_implementation_level": "deterministic_transform",
                "attack_truth_bbox": metadata["truth_bbox"],
                "attacked_image_sha256": _png_sha256(attacked),
                "attacked_image_path": None,
                "attacked_image_retained": False,
            }
        )
    samples = {
        SAMPLE_ID: SimpleNamespace(sample_id=SAMPLE_ID, sha256=SOURCE_SHA256)
    }
    return benchmark_root, rows, samples


def _validate(
    benchmark_root: Path, rows: list[dict], samples: dict[str, object]
):
    return validate_spatial_filter_attack_evidence(
        rows,
        benchmark_root=benchmark_root,
        sample_by_id=samples,
        expected_seeds=(SEED,),
        expected_attack_ids=SPATIAL_FILTER_ATTACK_IDS,
    )


def test_authenticates_complete_attack_cross_product(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)

    result = _validate(benchmark_root, rows, samples)

    assert len(result.authenticated_attack_map) == 4
    assert len(result.canonical_identity_sha256) == 64
    assert result.authenticated_attack_map[(SAMPLE_ID, SEED, "clean")][
        "attack_truth_bbox"
    ] is None
    assert result.authenticated_attack_map[
        (SAMPLE_ID, SEED, "erasing__area_ratio-0.05")
    ]["attack_truth_bbox"] == rows[1]["attack_truth_bbox"]


def test_rejects_forged_truth_bbox(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)
    forged = copy.deepcopy(rows)
    forged[1]["attack_truth_bbox"][0] += 1

    with pytest.raises(
        SpatialFilterAttackEvidenceError, match="truth bbox differs"
    ):
        _validate(benchmark_root, forged, samples)


def test_rejects_forged_attack_params(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)
    forged = copy.deepcopy(rows)
    forged[1]["attack_params"] = {"area_ratio": 0.06}

    with pytest.raises(
        SpatialFilterAttackEvidenceError, match="attack declaration"
    ):
        _validate(benchmark_root, forged, samples)


def test_rejects_erasing_sha_drift(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)
    forged = copy.deepcopy(rows)
    forged[1]["attacked_image_sha256"] = "f" * 64

    with pytest.raises(SpatialFilterAttackEvidenceError, match="PNG SHA-256"):
        _validate(benchmark_root, forged, samples)


def test_rejects_clean_path_escape(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)
    forged = copy.deepcopy(rows)
    outside = tmp_path / "outside.png"
    Image.new("RGB", (64, 64), (30, 80, 140)).save(outside)
    forged[0]["attacked_image_path"] = str(outside)
    forged[0]["attacked_image_sha256"] = _file_sha256(outside)

    with pytest.raises(SpatialFilterAttackEvidenceError, match="escapes benchmark_root"):
        _validate(benchmark_root, forged, samples)


def test_rejects_clean_symlink_inside_candidate(tmp_path: Path) -> None:
    benchmark_root, rows, samples = _valid_bundle(tmp_path)
    clean_path = Path(rows[0]["attacked_image_path"])
    target = clean_path.with_name("watermarked-target.png")
    clean_path.replace(target)
    try:
        clean_path.symlink_to(target)
    except OSError:
        pytest.skip("The current platform does not permit creating test symlinks.")

    with pytest.raises(SpatialFilterAttackEvidenceError, match="symlink or junction"):
        _validate(benchmark_root, rows, samples)
