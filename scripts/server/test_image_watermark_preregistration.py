from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from protection.supporting.image_watermark.experiments.manifest import manifest_lock_path
from scripts.server.image_watermark_preregistration import (
    CLAIM_SCHEMA_VERSION,
    RUN_COPY_FILENAME,
    PreregistrationError,
    build_preregistration_contract,
    copy_preregistration_claim_to_run,
    generate_preregistration_nonce,
    validate_preregistration_claim,
    write_preregistration_claim,
)


RUN_CLASS = "threshold_calibration_development_only"
NONCE = "ab" * 32


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "bundle"
    root.mkdir()
    config_path = root / "threshold_calibration.yaml"
    manifest_path = root / "threshold_calibration_dev_117.jsonl"
    manifest_path.write_text('{"sample_id":"fixture"}\n', encoding="utf-8")
    lock_path = manifest_lock_path(manifest_path)
    lock_path.write_text('{"schema_version":"fixture"}\n', encoding="utf-8")
    config = {
        "experiment": {"run_class": RUN_CLASS},
        "manifest": {"path": str(manifest_path)},
        "threshold_calibration": {
            "preregistration_claim": build_preregistration_contract(
                config_path=config_path,
                nonce=NONCE,
                expected_candidate_run_relative_paths=["candidate-runs/candidate-a"],
            )
        },
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path, manifest_path


def test_claim_binds_bundle_and_is_copied_byte_identically(tmp_path: Path) -> None:
    config_path, _ = _bundle(tmp_path)

    committed = write_preregistration_claim(
        config_path,
        expected_run_class=RUN_CLASS,
    )
    run_dir = config_path.parent / "candidate-runs" / "candidate-a"
    run_dir.mkdir(parents=True)
    copied = copy_preregistration_claim_to_run(
        config_path,
        source_claim_path=Path(committed["source_claim_path"]),
        destination_run=run_dir,
        expected_run_class=RUN_CLASS,
        expected_nonce=NONCE,
    )

    assert committed["schema_version"] == CLAIM_SCHEMA_VERSION
    assert committed["nonce"] == NONCE
    assert copied["candidate_run_relative_path"] == "candidate-runs/candidate-a"
    assert copied["claim_sha256"] == committed["claim_sha256"]
    assert (run_dir / RUN_COPY_FILENAME).read_bytes() == Path(
        committed["source_claim_path"]
    ).read_bytes()


def test_claim_rejects_manifest_mutation_and_run_copy_mutation(tmp_path: Path) -> None:
    config_path, manifest_path = _bundle(tmp_path)
    committed = write_preregistration_claim(
        config_path,
        expected_run_class=RUN_CLASS,
    )
    manifest_path.write_text('{"sample_id":"changed"}\n', encoding="utf-8")
    with pytest.raises(PreregistrationError, match="current frozen bundle"):
        validate_preregistration_claim(
            config_path,
            expected_run_class=RUN_CLASS,
            expected_nonce=NONCE,
        )

    manifest_path.write_text('{"sample_id":"fixture"}\n', encoding="utf-8")
    run_dir = config_path.parent / "candidate-runs" / "candidate-a"
    run_dir.mkdir(parents=True)
    copied = copy_preregistration_claim_to_run(
        config_path,
        source_claim_path=Path(committed["source_claim_path"]),
        destination_run=run_dir,
        expected_run_class=RUN_CLASS,
        expected_nonce=NONCE,
    )
    run_copy = Path(copied["claim_path"])
    run_copy.chmod(0o644)
    payload = json.loads(run_copy.read_text(encoding="utf-8"))
    payload["nonce"] = "cd" * 32
    run_copy.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PreregistrationError, match="byte-identical"):
        validate_preregistration_claim(
            config_path,
            claim_path=run_copy,
            expected_run_class=RUN_CLASS,
            expected_nonce=NONCE,
            expected_candidate_run=run_dir,
        )


def test_claim_refuses_preexisting_candidate_root(tmp_path: Path) -> None:
    config_path, _ = _bundle(tmp_path)
    (config_path.parent / "candidate-runs").mkdir()

    with pytest.raises(PreregistrationError, match="candidate root already exists"):
        write_preregistration_claim(
            config_path,
            expected_run_class=RUN_CLASS,
        )


def test_nonce_generation_is_256_bit_lowercase_hex() -> None:
    first = generate_preregistration_nonce()
    second = generate_preregistration_nonce()

    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")
    assert first != second
