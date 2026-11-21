from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.manifest import (
    ImageSample,
    manifest_lock_path,
    write_manifest,
)
from scripts.server.build_image_watermark_channel_vote_confirmation import (
    CALIBRATION_SAMPLES,
    CANDIDATE_ID,
    CONFIRMATION_MINIMUM_DOMAINS,
    ChannelVoteConfirmationBuildError,
    EXPECTED_CONFIRMATION_SAMPLES,
    FORMAL_TEST_ROWS_CONSUMED,
    FROZEN_RECOVERY_THRESHOLD,
    PROTOCOL_AMENDMENT_ID,
    PROTOCOL_AMENDMENT_VERSION,
    TIED_CANDIDATE_ID,
    _load_locked_manifest,
    _confirmation_domain_coverage,
    _select_confirmation_complement,
    _selection_rationale_from_report,
    sha256_file,
)


def _sample(index: int, split: str = "dev") -> ImageSample:
    return ImageSample(
        sample_id=f"sample_{index:04d}",
        relative_path=f"images/{index:04d}.png",
        split=split,
        source_dataset=f"dataset_{index % 4}",
        domain=f"domain_{index % 37}",
        license_id="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        provenance=f"fixture:{index}",
        source_family=f"family:{index}",
        sha256=hashlib.sha256(f"image:{index}".encode()).hexdigest(),
        width=8,
        height=8,
    )


def _constraint_checks(passed: int) -> list[dict[str, object]]:
    names = [
        "clean_mean_mask_fpr",
        "clean_p99_mask_fpr",
        "clean_max_mask_fpr",
        "erasing_0.05_mean_mask_iou",
        "erasing_0.15_mean_mask_iou",
        "erasing_0.25_mean_mask_iou",
        "erasing_0.05_p10_mask_iou",
        "erasing_0.15_p10_mask_iou",
        "erasing_0.25_p10_mask_iou",
        "erasing_0.05_iou_at_least_0_75_rate",
        "erasing_0.15_iou_at_least_0_75_rate",
        "erasing_0.25_iou_at_least_0_75_rate",
    ]
    return [
        {
            "name": name,
            "observed": 0.0,
            "operator": "<=",
            "limit": 0.0,
            "passed": index < passed,
        }
        for index, name in enumerate(names)
    ]


def _calibration_report() -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for index, threshold in enumerate(
        (0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36)
    ):
        checks = _constraint_checks(12 if threshold in {0.34, 0.36} else 10)
        if threshold == 0.34:
            checks[2]["passed"] = False
        elif threshold == 0.36:
            checks[3]["passed"] = False
        candidates.append(
            {
                "candidate_id": f"recovery_threshold_{str(threshold).replace('.', 'p')}",
                "recovery_threshold": threshold,
                "constraint_checks": checks,
                "all_constraints_passed": False,
                "selection_metrics": {
                    "clean_mean_mask_fpr": 2.5192e-05,
                    "clean_p99_mask_fpr": 4.406e-04,
                    "clean_max_mask_fpr": 0.002571,
                    "erasing_mean_mask_iou_by_ratio": {
                        "0.05": 0.900784,
                        "0.15": 0.954158,
                        "0.25": 0.967894,
                    },
                },
            }
        )
    return {
        "status": "no_candidate_satisfies_constraints",
        "winner": None,
        "candidate_metrics": candidates,
    }


def test_complement_is_exact_216_disjoint_dev_and_consumes_no_test() -> None:
    dev = [_sample(index) for index in range(333)]
    formal = [
        *dev,
        _sample(10_000, "train"),
        _sample(20_000, "test"),
    ]
    calibration = dev[:CALIBRATION_SAMPLES]

    selected = _select_confirmation_complement(formal, calibration)

    assert len(selected) == EXPECTED_CONFIRMATION_SAMPLES == 216
    assert {row.split for row in selected} == {"dev"}
    assert not {row.sample_id for row in selected}.intersection(
        row.sample_id for row in calibration
    )
    assert FORMAL_TEST_ROWS_CONSUMED == 0
    assert all(row.sample_id != "sample_20000" for row in selected)


def test_confirmation_domain_floor_strengthens_formal_four_to_nine_with_29_observed() -> None:
    coverage = _confirmation_domain_coverage(
        4,
        [f"domain_{index:02d}" for index in range(29)],
    )

    assert coverage == {
        "source_formal_minimum_domains": 4,
        "confirmation_minimum_domains": CONFIRMATION_MINIMUM_DOMAINS,
        "effective_minimum_domains": 9,
        "selected_domain_count": 29,
        "selected_domains": [f"domain_{index:02d}" for index in range(29)],
    }


def test_confirmation_domain_floor_preserves_stronger_source_floor() -> None:
    coverage = _confirmation_domain_coverage(
        12,
        [f"domain_{index:02d}" for index in range(29)],
    )

    assert coverage["source_formal_minimum_domains"] == 12
    assert coverage["confirmation_minimum_domains"] == 9
    assert coverage["effective_minimum_domains"] == 12
    assert coverage["selected_domain_count"] == 29


def test_confirmation_domain_floor_rejects_insufficient_observed_coverage() -> None:
    with pytest.raises(
        ChannelVoteConfirmationBuildError,
        match="effective minimum is 9",
    ):
        _confirmation_domain_coverage(
            4,
            [f"domain_{index:02d}" for index in range(8)],
        )


def test_complement_rejects_calibration_identity_substitution() -> None:
    dev = [_sample(index) for index in range(333)]
    calibration = dev[:CALIBRATION_SAMPLES]
    calibration[-1] = ImageSample.from_dict(
        {
            **calibration[-1].to_dict(),
            "sha256": "f" * 64,
        }
    )

    with pytest.raises(
        ChannelVoteConfirmationBuildError,
        match="identity-preserving subset",
    ):
        _select_confirmation_complement(dev, calibration)


def test_locked_manifest_tamper_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    image_path = root / "images" / "one.png"
    image_path.parent.mkdir(parents=True)
    Image.new("RGB", (8, 8), "navy").save(image_path)
    manifest_path = tmp_path / "one.jsonl"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "manifest": {"path": str(manifest_path)},
                "datasets": [
                    {"name": "dataset_0", "enabled": True, "root": str(root)}
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    row = ImageSample(
        sample_id="one",
        relative_path="images/one.png",
        split="dev",
        source_dataset="dataset_0",
        domain="fixture",
        license_id="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        provenance="fixture:one",
        source_family="family:one",
        sha256=sha256_file(image_path),
        width=8,
        height=8,
    )
    write_manifest(
        [row],
        manifest_path,
        environ={},
        config_path=config_path,
        upstream_dataset_locks={},
    )
    lock_path = manifest_lock_path(manifest_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["manifest_sha256"] = "0" * 64
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(ChannelVoteConfirmationBuildError, match="lock"):
        _load_locked_manifest(config_path, manifest_path)


def test_calibration_rationale_records_amended_real_11_of_12_tie() -> None:
    rationale = _selection_rationale_from_report(_calibration_report())

    assert rationale["source_candidate_id"] == CANDIDATE_ID.split("__", 1)[0]
    assert rationale["source_recovery_threshold"] == FROZEN_RECOVERY_THRESHOLD
    assert rationale["constraints_passed"] == 11
    assert rationale["constraints_total"] == 12
    assert rationale["sole_failed_constraint"] == "clean_max_mask_fpr"
    assert rationale["pass_count_tie"] is True
    assert rationale["maximum_constraints_passed"] == 11
    assert rationale["pass_count_tie_candidate_ids"] == [
        CANDIDATE_ID.split("__", 1)[0],
        TIED_CANDIDATE_ID,
    ]
    assert rationale["candidate_failure_sets"][
        CANDIDATE_ID.split("__", 1)[0]
    ] == ["clean_max_mask_fpr"]
    assert rationale["candidate_failure_sets"][TIED_CANDIDATE_ID] == [
        "erasing_0.05_mean_mask_iou"
    ]
    assert rationale["protocol_amendment_id"] == PROTOCOL_AMENDMENT_ID
    assert rationale["protocol_amendment_version"] == PROTOCOL_AMENDMENT_VERSION
    assert rationale["posthoc_to_117"] is True
    assert rationale["preregistered_before_216"] is True
    assert rationale["mechanism_eligibility"]["eligible_candidate_ids"] == [
        CANDIDATE_ID.split("__", 1)[0]
    ]
    assert "uniqu" not in rationale["reason"].lower()


def test_calibration_rationale_rejects_unexpected_third_11_of_12_candidate() -> None:
    report = _calibration_report()
    candidates = report["candidate_metrics"]
    assert isinstance(candidates, list)
    second = candidates[0]
    assert isinstance(second, dict)
    second["constraint_checks"] = _constraint_checks(11)

    with pytest.raises(ChannelVoteConfirmationBuildError, match="pass-count tie"):
        _selection_rationale_from_report(report)


def test_calibration_rationale_rejects_same_mechanism_failure_for_tau_0p36() -> None:
    report = _calibration_report()
    candidates = report["candidate_metrics"]
    assert isinstance(candidates, list)
    tied = candidates[-1]
    assert isinstance(tied, dict)
    tied_checks = _constraint_checks(12)
    tied_checks[2]["passed"] = False
    tied["constraint_checks"] = tied_checks

    with pytest.raises(
        ChannelVoteConfirmationBuildError,
        match="Threshold 0.36 must be the tied 11/12 candidate",
    ):
        _selection_rationale_from_report(report)
