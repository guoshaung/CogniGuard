from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from protection.supporting.image_watermark.experiments.localization_artifacts import (
    validate_verify_localization_artifacts,
)
from protection.supporting.image_watermark.experiments.manifest import ImageSample
from scripts.server import (
    analyze_image_watermark_channel_vote_confirmation as confirmation_analyzer,
)
from scripts.server.analyze_image_watermark_channel_vote_confirmation import (
    ChannelVoteConfirmationError,
    _evaluate_protocol_constraints,
    _read_strict_uint16_vote_png,
    _resolve_confirmation_run_directory,
    _validate_confirmation_output_root,
    _validate_observed_domain_coverage,
    _validated_domain_coverage,
    _validate_frozen_parameters,
    _validate_raw_vote_artifacts,
    _validate_required_capabilities,
    _validate_run_rows,
)
from scripts.server.build_image_watermark_channel_vote_confirmation import (
    CANDIDATE_ID,
    CONFIRMATION_MINIMUM_DOMAINS,
    EXPECTED_CONFIRMATION_SAMPLES,
    EXPECTED_ROWS,
    FROZEN_REQUIRED_CAPABILITIES,
    RUN_CLASS,
    RUN_RELATIVE_PATH,
    SELECTION_RULE,
)
from scripts.server.build_image_watermark_threshold_calibration import (
    ATTACK_ARTIFACT_RETENTION,
    ATTACK_CONDITIONS,
    EVALUATION_SEEDS,
)


TEST_REQUIRED_CAPABILITIES = {
    **FROZEN_REQUIRED_CAPABILITIES,
    "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
    "attack_model_revision": "1" * 40,
    "deterministic_mode_enabled": True,
}


def _samples() -> dict[str, ImageSample]:
    rows = [
        ImageSample(
            sample_id=f"sample_{index:03d}",
            relative_path=f"images/{index:03d}.png",
            split="dev",
            source_dataset=f"dataset_{index % 4}",
            domain=f"domain_{index % 20}",
            license_id="CC0-1.0",
            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
            provenance=f"fixture:{index}",
            source_family=f"family:{index}",
            sha256=hashlib.sha256(f"sample:{index}".encode()).hexdigest(),
            width=8,
            height=8,
        )
        for index in range(EXPECTED_CONFIRMATION_SAMPLES)
    ]
    return {row.sample_id: row for row in rows}


def _raw_rows(samples: dict[str, ImageSample]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    verify_index = 0
    for sample in samples.values():
        for seed in EVALUATION_SEEDS:
            for attack_id in ATTACK_CONDITIONS:
                clean = attack_id == "clean"
                ratio = None if clean else float(attack_id.rsplit("-", 1)[1])
                row: dict[str, Any] = {
                    "row_key": (
                        f"editguard_wrapper|{sample.sample_id}|{seed}|{attack_id}"
                    ),
                    "sample_id": sample.sample_id,
                    "image_sha256": sample.sha256,
                    "source_dataset": sample.source_dataset,
                    "status": "ok",
                    "pipeline_success": 1.0,
                    "implementation_level": "real_pipeline",
                    "run_class": RUN_CLASS,
                    "paper_eligible": False,
                    "split": "dev",
                    "method_id": "editguard_wrapper",
                    "traditional_attack_artifact_retention": (
                        ATTACK_ARTIFACT_RETENTION
                    ),
                    "seed": seed,
                    "attack_id": attack_id,
                    "verify_job_id": f"verify_fixture_{verify_index}",
                    "attacked_image_sha256": hashlib.sha256(
                        f"attack:{verify_index}".encode()
                    ).hexdigest(),
                    "attacked_image_retained": clean,
                    "attacked_image_path": "retained.png" if clean else None,
                    "attack_truth_bbox": None if clean else [0, 0, 2, 2],
                    "mask_fpr": 0.0,
                    "predicted_tamper_area_ratio": 0.0 if clean else 0.25,
                    "predicted_mask_nonempty": 0.0 if clean else 1.0,
                    "source_registry_match": 1.0,
                    "image_tamper_detected": 0.0 if clean else 1.0,
                }
                if not clean:
                    row.update(
                        {
                            "attack_params": {"area_ratio": ratio},
                            "mask_iou": 1.0,
                            "mask_dice": 1.0,
                            "mask_precision": 1.0,
                            "mask_recall": 1.0,
                        }
                    )
                rows.append(row)
                verify_index += 1
    return rows


def _contract() -> dict[str, Any]:
    return {
        "candidate_count": 1,
        "parameter_search_allowed": False,
        "posthoc_parameter_change_allowed": False,
        "fallback_candidate_allowed": False,
        "selection_rule": SELECTION_RULE,
        "decision_output": "pass_or_fail_only_no_parameter_selection",
        "candidate": {
            "candidate_id": CANDIDATE_ID,
            **TEST_REQUIRED_CAPABILITIES,
            "run_relative_path": RUN_RELATIVE_PATH,
        },
        "required_capabilities": dict(TEST_REQUIRED_CAPABILITIES),
    }


def _method() -> dict[str, Any]:
    return {
        "id": "editguard_wrapper",
        "required_capabilities": dict(TEST_REQUIRED_CAPABILITIES),
    }


def _domain_payload_and_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    selected_domains = [f"domain_{index:02d}" for index in range(29)]
    payload = {"data_requirements": {"minimum_domains": 9}}
    contract = {
        "source_formal_minimum_domains": 4,
        "confirmation_minimum_domains": CONFIRMATION_MINIMUM_DOMAINS,
        "effective_minimum_domains": 9,
        "selected_domain_count": 29,
        "selected_domains": selected_domains,
    }
    return payload, contract


def _directory_symlink_or_skip(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks are unavailable for this test: {exc}")


def test_confirmation_analyzer_rejects_symlinked_run_directories(
    tmp_path: Path,
) -> None:
    run_root = (tmp_path / "bundle").resolve()
    run_root.mkdir()
    outside_runs = tmp_path / "outside-confirmation-runs"
    outside_runs.mkdir()
    confirmation_runs_root = run_root / "confirmation-run"
    _directory_symlink_or_skip(confirmation_runs_root, outside_runs)

    with pytest.raises(ChannelVoteConfirmationError, match="must not be a symlink"):
        _resolve_confirmation_run_directory(run_root)

    confirmation_runs_root.unlink()
    confirmation_runs_root.mkdir()
    outside_candidate = tmp_path / "outside-confirmation-candidate"
    outside_candidate.mkdir()
    candidate_path = run_root / RUN_RELATIVE_PATH
    _directory_symlink_or_skip(candidate_path, outside_candidate)
    with pytest.raises(ChannelVoteConfirmationError, match="must not be a symlink"):
        _resolve_confirmation_run_directory(run_root)


def test_confirmation_output_root_is_exactly_bound_to_bundle(tmp_path: Path) -> None:
    config_path = (tmp_path / "bundle" / "channel_vote_confirmation.yaml").resolve()
    config_path.parent.mkdir()
    expected = (config_path.parent / RUN_RELATIVE_PATH).resolve()

    assert _validate_confirmation_output_root(
        config_path, {"output_root": str(expected)}
    ) == expected
    for bad in (
        "confirmation-run/relative",
        str((tmp_path / "outside" / CANDIDATE_ID).resolve()),
        str(expected.parent / ".." / expected.parent.name / expected.name),
    ):
        with pytest.raises(ChannelVoteConfirmationError, match="output_root"):
            _validate_confirmation_output_root(config_path, {"output_root": bad})


def test_domain_coverage_contract_replays_source_floor_and_observed_29() -> None:
    payload, contract = _domain_payload_and_contract()

    assert _validated_domain_coverage(
        payload,
        contract,
        source_formal_payload={"data_requirements": {"minimum_domains": 4}},
    ) == contract


def test_manifest_domain_coverage_is_recomputed_from_selected_rows() -> None:
    rows = list(_samples().values())
    observed_domains = sorted({row.domain for row in rows})
    contract = {
        "effective_minimum_domains": 9,
        "selected_domain_count": len(observed_domains),
        "selected_domains": observed_domains,
    }

    assert _validate_observed_domain_coverage(rows, contract) == observed_domains
    contract["selected_domain_count"] -= 1
    with pytest.raises(ChannelVoteConfirmationError, match="manifest domain coverage"):
        _validate_observed_domain_coverage(rows, contract)


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("contract", "source_formal_minimum_domains", 5),
        ("contract", "confirmation_minimum_domains", 8),
        ("contract", "effective_minimum_domains", 10),
        ("contract", "selected_domain_count", 28),
        ("payload", "minimum_domains", 8),
    ],
)
def test_domain_coverage_contract_rejects_tampered_fields(
    target: str,
    field: str,
    value: int,
) -> None:
    payload, contract = _domain_payload_and_contract()
    if target == "payload":
        payload["data_requirements"][field] = value
    else:
        contract[field] = value

    with pytest.raises(ChannelVoteConfirmationError, match="domain"):
        _validated_domain_coverage(
            payload,
            contract,
            source_formal_payload={"data_requirements": {"minimum_domains": 4}},
        )

def test_run_rows_require_all_216_times_3_times_4_cells() -> None:
    samples = _samples()
    rows = _raw_rows(samples)

    grouped = _validate_run_rows(rows, samples_by_id=samples)

    assert len(rows) == EXPECTED_ROWS == 2592
    assert set(grouped) == set(ATTACK_CONDITIONS)
    assert all(
        len(grouped[attack_id])
        == EXPECTED_CONFIRMATION_SAMPLES * len(EVALUATION_SEEDS)
        for attack_id in ATTACK_CONDITIONS
    )


def test_run_rows_reject_missing_and_duplicate_cells() -> None:
    samples = _samples()
    rows = _raw_rows(samples)
    with pytest.raises(ChannelVoteConfirmationError, match="expected 2592"):
        _validate_run_rows(rows[:-1], samples_by_id=samples)

    duplicated = [*rows]
    duplicated[-1] = dict(rows[0])
    with pytest.raises(ChannelVoteConfirmationError, match="duplicated"):
        _validate_run_rows(duplicated, samples_by_id=samples)


def test_capability_gate_rejects_channel_vote_min_mismatch() -> None:
    capabilities = dict(TEST_REQUIRED_CAPABILITIES)
    capabilities["localization_channel_vote_min"] = 1

    with pytest.raises(ChannelVoteConfirmationError, match="capabilities mismatch"):
        _validate_required_capabilities(
            capabilities,
            label="fixture",
            expected=TEST_REQUIRED_CAPABILITIES,
        )


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("candidate", "recovery_threshold", 0.36),
        ("candidate", "localization_channel_vote_min", 1),
        ("method", "localization_channel_vote_min", 1),
    ],
)
def test_frozen_parameter_tamper_is_rejected(
    target: str,
    field: str,
    value: Any,
) -> None:
    contract = _contract()
    method = _method()
    if target == "candidate":
        contract["candidate"][field] = value
    else:
        method["required_capabilities"][field] = value

    with pytest.raises(ChannelVoteConfirmationError, match="differ"):
        _validate_frozen_parameters(contract, method)


def test_constraint_boundaries_are_inclusive_and_pass() -> None:
    checks, passed = _evaluate_protocol_constraints(
        clean_mean=1e-4,
        clean_p99=5e-4,
        clean_max=1e-3,
        erasing_mean_by_ratio={"0.05": 0.90, "0.15": 0.90, "0.25": 0.90},
        erasing_p10_by_ratio={"0.05": 0.75, "0.15": 0.75, "0.25": 0.75},
        erasing_success_rate_by_ratio={
            "0.05": 0.95,
            "0.15": 0.95,
            "0.25": 0.95,
        },
    )

    assert passed is True
    assert len(checks) == 12
    assert all(check["passed"] for check in checks)


@pytest.mark.parametrize(
    ("override", "failed_name"),
    [
        ({"clean_max": 0.0010000001}, "clean_max_mask_fpr"),
        (
            {"erasing_mean_by_ratio": {"0.05": 0.8999999, "0.15": 0.90, "0.25": 0.90}},
            "erasing_0.05_mean_mask_iou",
        ),
        (
            {
                "erasing_success_rate_by_ratio": {
                    "0.05": 0.9499999,
                    "0.15": 0.95,
                    "0.25": 0.95,
                }
            },
            "erasing_0.05_iou_at_least_0_75_rate",
        ),
    ],
)
def test_constraint_epsilon_failure_is_reported(
    override: dict[str, Any],
    failed_name: str,
) -> None:
    values: dict[str, Any] = {
        "clean_mean": 1e-4,
        "clean_p99": 5e-4,
        "clean_max": 1e-3,
        "erasing_mean_by_ratio": {"0.05": 0.90, "0.15": 0.90, "0.25": 0.90},
        "erasing_p10_by_ratio": {"0.05": 0.75, "0.15": 0.75, "0.25": 0.75},
        "erasing_success_rate_by_ratio": {
            "0.05": 0.95,
            "0.15": 0.95,
            "0.25": 0.95,
        },
    }
    values.update(override)

    checks, passed = _evaluate_protocol_constraints(**values)

    assert passed is False
    assert [check["name"] for check in checks if not check["passed"]] == [failed_name]


def test_uint16_vote_png_is_preserved_without_uint8_overflow(tmp_path: Path) -> None:
    votes = np.asarray([[0, 255], [510, 765]], dtype=np.uint16)
    path = tmp_path / "raw_localization_channel_votes.uint16.png"
    Image.fromarray(votes).save(path, format="PNG", compress_level=9)

    observed = _read_strict_uint16_vote_png(path)

    assert observed.dtype == np.dtype("uint16")
    np.testing.assert_array_equal(observed, votes)
    assert int(observed[1, 1]) == 765


def test_vote_png_rejects_8bit_or_non_vote_values(tmp_path: Path) -> None:
    eight_bit = tmp_path / "eight.png"
    Image.fromarray(np.asarray([[0, 255]], dtype=np.uint8)).save(eight_bit)
    with pytest.raises(ChannelVoteConfirmationError, match="16-bit grayscale"):
        _read_strict_uint16_vote_png(eight_bit)

    invalid = tmp_path / "invalid.png"
    Image.fromarray(np.asarray([[0, 254, 510]], dtype=np.uint16)).save(invalid)
    with pytest.raises(ChannelVoteConfirmationError, match="outside"):
        _read_strict_uint16_vote_png(invalid)


def _write_raw_vote_case(run_dir: Path) -> tuple[list[dict[str, Any]], Path]:
    verify_job_id = "verify_raw_vote_fixture"
    verify_dir = run_dir / "benchmark" / "api_jobs" / verify_job_id / "verify"
    verify_dir.mkdir(parents=True)
    votes = np.asarray([[0, 255], [510, 765]], dtype=np.uint16)
    raw_path = verify_dir / "raw_localization_channel_votes.uint16.png"
    Image.fromarray(votes).save(raw_path, format="PNG", compress_level=9)
    predicted = (votes >= 510).astype(np.uint8) * 255
    Image.fromarray(predicted).save(verify_dir / "predicted_mask.png")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    histogram = {"0": 1, "255": 1, "510": 1, "765": 1}
    input_sha256 = hashlib.sha256(b"attacked-input-fixture").hexdigest()
    input_reference = {
        "suffix": ".png",
        "size_bytes": 123,
        "sha256": input_sha256,
    }
    artifact = {
        "path": str(raw_path.resolve()),
        "sha256": digest,
        "histogram": histogram,
        "dtype": "uint16",
        "shape": [2, 2],
        "encoding": "lossless_png_16bit_grayscale_I;16",
    }
    response = {
        **FROZEN_REQUIRED_CAPABILITIES,
        "job_id": verify_job_id,
        "status": "ok",
        "implementation_level": "real_pipeline",
        "report_json_path": str((verify_dir / "verify_report.json").resolve()),
        "predicted_mask_path": str((verify_dir / "predicted_mask.png").resolve()),
        "seed": EVALUATION_SEEDS[0],
        "predicted_mask_area_ratio": 0.5,
        "attack_regime": "localized_tamper_candidate",
        "raw_localization_votes_path": str(raw_path.resolve()),
        "raw_localization_votes_sha256": digest,
        "raw_localization_votes_histogram": histogram,
        "raw_localization_votes_dtype": "uint16",
        "raw_localization_votes_shape": [2, 2],
        "raw_localization_votes_encoding": "lossless_png_16bit_grayscale_I;16",
    }
    report = {
        **FROZEN_REQUIRED_CAPABILITIES,
        "job_id": verify_job_id,
        "job_type": "verify",
        "request": {
            "image_reference": input_reference,
            "strict": True,
            "return_overlay": False,
            "return_recovered_bits": True,
            "seed": EVALUATION_SEEDS[0],
        },
        "input_image": input_reference,
        "resolved_raw_vote_threshold": 510,
        "predicted_mask_area_ratio": 0.5,
        "response": response,
        "raw_localization_votes_artifact": artifact,
    }
    report_path = verify_dir / "verify_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    validated = validate_verify_localization_artifacts(
        response=response,
        artifact_run_root=run_dir / "benchmark",
        required_capabilities=FROZEN_REQUIRED_CAPABILITIES,
        expected_input_sha256=input_sha256,
        expected_seed=EVALUATION_SEEDS[0],
        expected_image_shape=(2, 2),
    )
    evidence = validated.evidence
    return (
        [
            {
                "row_key": "fixture-row",
                "verify_job_id": verify_job_id,
                "attacked_image_sha256": input_sha256,
                "seed": EVALUATION_SEEDS[0],
                "localization_artifact_evidence": evidence,
                "localization_artifact_evidence_sha256": evidence[
                    "canonical_evidence_sha256"
                ],
                "raw_localization_votes_sha256": evidence["raw_vote_sha256"],
                "predicted_mask_sha256": evidence["predicted_mask_sha256"],
                "localization_replay_identity_sha256": evidence[
                    "replay_identity_sha256"
                ],
            }
        ],
        report_path,
    )


def test_raw_vote_artifact_replay_checks_sha_shape_histogram_and_mask(
    tmp_path: Path,
) -> None:
    rows, _ = _write_raw_vote_case(tmp_path)

    evidence, evidence_sha256 = _validate_raw_vote_artifacts(
        rows,
        run_dir=tmp_path,
        required_image_shape=(2, 2),
    )

    assert list(evidence) == ["fixture-row"]
    assert len(evidence_sha256) == 64
    assert evidence["fixture-row"]["raw_vote_histogram"] == {
        "0": 1,
        "255": 1,
        "510": 1,
        "765": 1,
    }
    assert (
        evidence["fixture-row"]["schema_version"]
        == "cogniguard_localization_artifact_evidence_v1"
    )
    assert (
        evidence["fixture-row"]["canonical_evidence_sha256"]
        == rows[0]["localization_artifact_evidence_sha256"]
    )


def test_raw_vote_artifact_validation_delegates_each_row_to_shared_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _ = _write_raw_vote_case(tmp_path)
    observed: list[str] = []
    original = confirmation_analyzer.validate_verify_localization_artifacts

    def tracking_validator(**kwargs: Any) -> Any:
        observed.append(str(kwargs["response"]["job_id"]))
        return original(**kwargs)

    monkeypatch.setattr(
        confirmation_analyzer,
        "validate_verify_localization_artifacts",
        tracking_validator,
    )

    _validate_raw_vote_artifacts(
        rows,
        run_dir=tmp_path,
        required_image_shape=(2, 2),
    )

    assert observed == ["verify_raw_vote_fixture"]


def test_raw_vote_artifact_requires_frozen_512_attacked_input_shape(
    tmp_path: Path,
) -> None:
    rows, _ = _write_raw_vote_case(tmp_path)

    with pytest.raises(ChannelVoteConfirmationError, match="attacked input"):
        _validate_raw_vote_artifacts(rows, run_dir=tmp_path)


def test_raw_vote_artifact_rejects_reported_histogram_tamper(tmp_path: Path) -> None:
    rows, report_path = _write_raw_vote_case(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["response"]["raw_localization_votes_histogram"]["510"] = 0
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ChannelVoteConfirmationError, match="histogram"):
        _validate_raw_vote_artifacts(
            rows, run_dir=tmp_path, required_image_shape=(2, 2)
        )


def test_raw_vote_artifact_rejects_raw_results_evidence_tamper(tmp_path: Path) -> None:
    rows, _ = _write_raw_vote_case(tmp_path)
    rows[0]["localization_artifact_evidence"] = {
        **rows[0]["localization_artifact_evidence"],
        "raw_vote_sha256": "0" * 64,
    }

    with pytest.raises(ChannelVoteConfirmationError, match="shared replay"):
        _validate_raw_vote_artifacts(
            rows, run_dir=tmp_path, required_image_shape=(2, 2)
        )


def test_raw_vote_artifact_rejects_orphan_artifacts(tmp_path: Path) -> None:
    rows, _ = _write_raw_vote_case(tmp_path)
    orphan = (
        tmp_path
        / "benchmark"
        / "api_jobs"
        / "orphan"
        / "raw_localization_channel_votes.extra"
    )
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"orphan")

    with pytest.raises(ChannelVoteConfirmationError, match="artifact set"):
        _validate_raw_vote_artifacts(
            rows, run_dir=tmp_path, required_image_shape=(2, 2)
        )
