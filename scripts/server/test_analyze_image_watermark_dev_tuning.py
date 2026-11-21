from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.server.analyze_image_watermark_dev_tuning import (
    DevAnalysisError,
    analyze_run,
    canonical_condition,
    write_analysis,
)


WORD_A = "0" * 64
WORD_B = "111" + "0" * 61
FAR_WORD = "1" * 32 + "0" * 32


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _flip(bits: str, index: int) -> str:
    replacement = "0" if bits[index] == "1" else "1"
    return bits[:index] + replacement + bits[index + 1 :]


def _bit_accuracy(observed: str, expected: str) -> float:
    errors = (int(observed, 2) ^ int(expected, 2)).bit_count()
    return 1.0 - errors / 64.0


def _add_case(
    run_dir: Path,
    rows: list[dict],
    *,
    sample_id: str,
    domain: str,
    expected: str,
    raw_bits: str,
    attack_name: str,
    attack_params: dict,
    exact: bool,
    source: bool,
    corrected: bool,
    registry_distance: int | None,
    ordinal: int,
) -> None:
    job_id = f"verify_fixture_{ordinal:03d}"
    condition_suffix = "_".join(
        [attack_name]
        + [f"{key}-{attack_params[key]}" for key in sorted(attack_params)]
    )
    report_path = (
        run_dir / "api_jobs" / job_id / "verify" / "verify_report.json"
    ).resolve()
    response = {
        "status": "ok",
        "job_id": job_id,
        "exact_registry_match": exact,
        "source_registry_match": source,
        "correction_applied": corrected,
        "registry_hamming_distance": registry_distance,
        "recovered_capsule_bits": raw_bits,
        "predicted_mask_area_ratio": ordinal / 100.0,
    }
    _write_json(
        report_path,
        {
            "job_id": job_id,
            "job_type": "verify",
            "response": response,
            "recovered_bits": raw_bits,
        },
    )
    _write_json(
        run_dir / "api_jobs" / "_index" / f"{job_id}.json",
        {
            "job_id": job_id,
            "job_type": "verify",
            "report_json_path": str(report_path),
        },
    )
    accuracy = _bit_accuracy(raw_bits, expected)
    rows.append(
        {
            "row_key": f"editguard_wrapper|{sample_id}|20260802|{condition_suffix}",
            "status": "ok",
            "run_class": "dev_tuning",
            "paper_eligible": False,
            "split": "dev",
            "method_id": "editguard_wrapper",
            "seed": 20260802,
            "sample_id": sample_id,
            "domain": domain,
            "attack_id": attack_name,
            "attack_name": attack_name,
            "attack_params": attack_params,
            "verify_job_id": job_id,
            "exact_registry_match": float(exact),
            "source_registry_match": float(source),
            "correction_applied": float(corrected),
            "registry_corrected_match": float(source and not exact and corrected),
            "registry_hamming_distance": registry_distance,
            "bit_accuracy": accuracy,
            "bit_error_rate": 1.0 - accuracy,
            "predicted_tamper_area_ratio": ordinal / 100.0,
            "mask_iou": 0.10 + ordinal / 100.0,
            "mask_dice": 0.20 + ordinal / 100.0,
            "mask_precision": 0.30 + ordinal / 100.0,
            "mask_recall": 0.40 + ordinal / 100.0,
            "mask_fpr": ordinal / 1000.0,
            "image_tamper_detected": float(ordinal % 2 == 0),
            "watermark_psnr": 40.0 + ordinal,
            "watermark_ssim": 0.90,
            "watermark_lpips": None,
            "watermark_normalized_mae": 0.01,
            "verify_latency_seconds": 0.10 + ordinal / 100.0,
        }
    )


def _build_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "dev_tuning_fixture"
    rows: list[dict] = []
    specifications = [
        ("sample-a", "geometry", WORD_A, WORD_A, "clean", {}, True, True, False, 0),
        (
            "sample-a",
            "geometry",
            WORD_A,
            _flip(WORD_A, 10),
            "jpeg",
            {"quality": 70},
            False,
            True,
            True,
            1,
        ),
        (
            "sample-a",
            "geometry",
            WORD_A,
            _flip(WORD_A, 0),
            "jpeg",
            {"quality": 90},
            False,
            True,
            True,
            1,
        ),
        (
            "sample-a",
            "geometry",
            WORD_A,
            FAR_WORD,
            "gaussian_noise",
            {"sigma": 5.0},
            False,
            False,
            False,
            None,
        ),
        ("sample-b", "physics", WORD_B, WORD_B, "clean", {}, True, True, False, 0),
        # This raw word is an exact match to the wrong sample.  It verifies that
        # reported exact acceptance and expected-source correctness stay separate.
        (
            "sample-b",
            "physics",
            WORD_B,
            WORD_A,
            "jpeg",
            {"quality": 70},
            True,
            True,
            False,
            0,
        ),
        (
            "sample-b",
            "physics",
            WORD_B,
            _flip(WORD_B, 10),
            "jpeg",
            {"quality": 90},
            False,
            True,
            True,
            1,
        ),
        (
            "sample-b",
            "physics",
            WORD_B,
            FAR_WORD,
            "gaussian_noise",
            {"sigma": 5.0},
            False,
            False,
            False,
            None,
        ),
    ]
    for ordinal, specification in enumerate(specifications, start=1):
        _add_case(
            run_dir,
            rows,
            sample_id=specification[0],
            domain=specification[1],
            expected=specification[2],
            raw_bits=specification[3],
            attack_name=specification[4],
            attack_params=specification[5],
            exact=specification[6],
            source=specification[7],
            corrected=specification[8],
            registry_distance=specification[9],
            ordinal=ordinal,
        )
    raw_path = run_dir / "benchmark" / "raw_results.jsonl"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return run_dir


def _add_registry_snapshot(run_dir: Path) -> None:
    for ordinal, (sample_id, bits) in enumerate(
        (("sample-a", WORD_A), ("sample-b", WORD_B)), start=1
    ):
        embed_job_id = f"embed_fixture_{ordinal:03d}"
        payload_id = f"payload-{ordinal}"
        auth_hash = f"auth-{ordinal}"
        _write_json(
            run_dir / "api_jobs" / embed_job_id / "embed" / "payload.json",
            {
                "capsule_schema": "hmac_source_capsule_v1",
                "auth_level": "hmac_registry",
                "capsule_bits": bits,
                "copyright_id": ordinal,
                "payload_id": payload_id,
                "auth_hash": auth_hash,
            },
        )
        _write_json(
            run_dir / "source-registry-snapshot" / f"{ordinal:05d}.json",
            {
                "schema_version": "cogniguard_source_registry_v2",
                "capsule_schema": "hmac_source_capsule_v1",
                "auth_level": "hmac_registry",
                "owner_id": f"paper:editguard_wrapper:{sample_id}",
                "embed_job_id": embed_job_id,
                "copyright_id": ordinal,
                "payload_id": payload_id,
                "auth_hash": auth_hash,
                "capsule_bits_sha256": hashlib.sha256(bits.encode()).hexdigest(),
            },
        )


def test_analyze_run_validates_and_groups_conditions(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)

    result = analyze_run(run_dir, expected_samples=2)

    assert result["result_class"] == "development_only_not_paper_result"
    assert result["paper_eligible"] is False
    assert result["scope"]["network_access_required"] is False
    assert result["scope"]["model_or_secret_access_required"] is False
    assert result["scope"]["canonical_condition_definitions"]["jpeg_quality_70"] == {
        "attack_name": "jpeg",
        "attack_params": {"quality": 70},
    }
    assert result["offline_simulation"]["radii"] == [0, 1, 2, 3, 4, 5]
    assert (
        result["offline_simulation"]["lookup_policy"]
        == "one_closed_set_codebook_lookup_per_row_per_radius"
    )
    assert result["bit_accuracy_validation"]["validated_rows"] == 8
    assert result["bit_accuracy_validation"]["mismatch_count"] == 0
    assert result["reference_selection"]["selected_from_clean"] == 2
    assert (
        result["reference_selection"]["samples_with_multiple_distinct_exact_words"]
        == 1
    )
    assert result["development_codebook"]["pairwise_distance"]["d_min"] == 3

    aggregates = result["aggregates"]
    assert aggregates["by_attack_name"]["jpeg"]["row_count"] == 4
    assert aggregates["by_attack_id"]["jpeg"]["row_count"] == 4
    assert aggregates["by_canonical_condition"]["jpeg_quality_70"]["row_count"] == 2
    assert aggregates["by_canonical_condition"]["jpeg_quality_90"]["row_count"] == 2
    assert (
        aggregates["by_domain_and_canonical_condition"]["geometry"]
        ["gaussian_noise_sigma_5"]
        ["row_count"]
        == 1
    )
    radius_zero = aggregates["overall"]["offline_codebook_lookup"]["0"]["counts"]
    assert radius_zero == {
        "correct_unique": 2,
        "wrong_unique": 1,
        "ambiguous": 0,
        "no_candidate": 5,
    }
    radius_two = aggregates["overall"]["offline_codebook_lookup"]["2"]["counts"]
    assert radius_two == {
        "correct_unique": 4,
        "wrong_unique": 1,
        "ambiguous": 1,
        "no_candidate": 2,
    }
    assert aggregates["overall"]["quality"]["watermark_psnr"]["count"] == 8
    assert aggregates["overall"]["quality"]["watermark_lpips"]["count"] == 0
    assert aggregates["overall"]["mask"]["predicted_mask_area_ratio"]["count"] == 8
    assert aggregates["overall"]["latency_seconds"]["verify"]["count"] == 8
    assert result["formal_3000_registry"]["recalculation_required"] is True
    assert result["formal_3000_registry"]["development_results_transferable"] is False


def test_output_is_byte_reproducible(tmp_path: Path) -> None:
    payload = analyze_run(_build_run(tmp_path), expected_samples=2)

    first = write_analysis(payload, tmp_path / "first.json")
    second = write_analysis(payload, tmp_path / "second.json")

    assert first.read_bytes() == second.read_bytes()


def test_registry_snapshot_supplies_truth_when_a_sample_has_no_exact_row(
    tmp_path: Path,
) -> None:
    run_dir = _build_run(tmp_path)
    _add_registry_snapshot(run_dir)

    raw_path = run_dir / "benchmark" / "raw_results.jsonl"
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    clean_a = next(
        row
        for row in rows
        if row["sample_id"] == "sample-a" and row["attack_name"] == "clean"
    )
    clean_a["exact_registry_match"] = 0.0
    clean_a["source_registry_match"] = 0.0
    raw_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    report_path = (
        run_dir / "api_jobs" / clean_a["verify_job_id"] / "verify" / "verify_report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["response"]["exact_registry_match"] = False
    report["response"]["source_registry_match"] = False
    _write_json(report_path, report)

    result = analyze_run(run_dir, expected_samples=2)

    assert result["reference_selection"]["policy"] == (
        "authenticated_run_local_registry_snapshot_and_embed_payload"
    )
    assert result["reference_selection"]["selected_from_registry_payload"] == 2
    assert result["bit_accuracy_validation"]["mismatch_count"] == 0


def test_bit_accuracy_mismatch_fails_closed(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    raw_path = run_dir / "benchmark" / "raw_results.jsonl"
    rows = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    rows[1]["bit_accuracy"] = 0.123
    raw_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(DevAnalysisError, match="bit_accuracy mismatch"):
        analyze_run(run_dir, expected_samples=2)


def test_verify_report_pointer_must_remain_inside_run(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path)
    outside_report = tmp_path / "outside" / "verify_report.json"
    _write_json(outside_report, {"job_id": "not-used"})
    index_path = run_dir / "api_jobs" / "_index" / "verify_fixture_001.json"
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    index_payload["report_json_path"] = str(outside_report.resolve())
    _write_json(index_path, index_payload)

    with pytest.raises(DevAnalysisError, match="escapes the RUN directory"):
        analyze_run(run_dir, expected_samples=2)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {"attack_id": "jpeg", "attack_name": "jpeg", "attack_params": {"quality": 70}},
            "jpeg_quality_70",
        ),
        (
            {
                "attack_id": "gaussian_noise",
                "attack_name": "gaussian_noise",
                "attack_params": {"sigma": 5.0},
            },
            "gaussian_noise_sigma_5",
        ),
        (
            {
                "attack_id": "resize",
                "attack_name": "resize",
                "attack_params": {"scale": 0.75},
            },
            "resize_scale_0.75",
        ),
    ],
)
def test_canonical_condition_uses_attack_parameter_values(
    row: dict, expected: str
) -> None:
    assert canonical_condition(row) == expected
