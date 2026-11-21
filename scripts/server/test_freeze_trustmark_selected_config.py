from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from PIL import Image

import scripts.server.freeze_trustmark_selected_config as freeze_module
from protection.supporting.image_watermark.experiments.manifest import ImageSample, write_manifest
from scripts.server.freeze_image_watermark_channel_vote_formal_config import (
    ChannelVoteFormalFreezeError,
)
from scripts.server.freeze_trustmark_selected_config import (
    EVIDENCE_SCHEMA_VERSION,
    TrustMarkSelectedFreezeError,
    freeze_trustmark_selected_config,
)


CANONICAL_BASELINE = (
    Path(__file__).resolve().parents[2]
    / 'protection' / 'image_watermark'
    / "configs"
    / "trustmark_official_baseline.yaml"
)
SELECTED_CAPABILITIES = {
    "recovery_threshold": 0.34,
    "tamper_area_threshold": 0.001,
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 2,
    "localization_residual_threshold_rule": ("abs_gt_recovery_threshold_per_channel"),
    "localization_postprocessing": "none",
}


@pytest.fixture(autouse=True)
def _validated_channel_vote_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        freeze_module,
        "validate_frozen_channel_vote_formal_config",
        lambda _path: dict(SELECTED_CAPABILITIES),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_reference(config: Path, value: str) -> Path:
    candidate = Path(value)
    return (
        candidate.resolve()
        if candidate.is_absolute()
        else (config.parent / candidate).resolve()
    )


def _selected_benchmark_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "selected" / "dataset"
    root.mkdir(parents=True)
    image_path = root / "sample.png"
    Image.new("RGB", (8, 7), (50, 100, 150)).save(image_path)

    selected_config = tmp_path / "selected" / "paper_benchmark_selected.yaml"
    manifest_path = tmp_path / "selected" / "paper_selected.jsonl"
    selected_payload = {
        "experiment": {
            "strict_paper_mode": True,
            "fail_fast": True,
            "split": "test",
            "max_samples": 0,
            "paper_eligible": True,
            "development_only": False,
        },
        "manifest": {
            "path": manifest_path.name,
            "verify_hashes": True,
            "require_lock": True,
        },
        "datasets": [
            {
                "name": "fixture",
                "enabled": True,
                "root": "dataset",
            }
        ],
        "formal_selection": {
            "schema_version": "cogniguard_image_channel_vote_formal_selection_v1",
            "status": "frozen",
            "selection_source": "development_only_channel_vote_confirmation",
            "selection_split": "dev",
            "excluded_splits": ["train", "test"],
            "formal_test_rows_consumed": 0,
        },
    }
    selected_config.write_text(
        yaml.safe_dump(selected_payload, sort_keys=False), encoding="utf-8"
    )
    write_manifest(
        [
            ImageSample(
                sample_id="fixture:sample",
                relative_path="sample.png",
                split="test",
                source_dataset="fixture",
                source_family="fixture-family",
                domain="fixture-domain",
                license_id="CC0-1.0",
                license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                provenance="programmatic:test",
                sha256=_sha256(image_path),
                width=8,
                height=7,
                image_path=str(image_path),
            )
        ],
        manifest_path,
        config_path=selected_config,
    )
    return selected_config, manifest_path, manifest_path.with_suffix(".jsonl.lock.json")


def test_freeze_binds_selected_yaml_relocates_output_and_preserves_official_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_config, manifest_path, lock_path = _selected_benchmark_fixture(tmp_path)
    redirected_manifest = tmp_path / "redirected.jsonl"
    redirected_manifest.write_text("{}\n", encoding="utf-8")
    redirected_root = tmp_path / "redirected-root"
    redirected_root.mkdir()
    monkeypatch.setenv(
        "COGNIGUARD_WATERMARK_DATASET_MANIFEST", str(redirected_manifest)
    )
    monkeypatch.setenv(
        "COGNIGUARD_DATASET_ROOTS_JSON",
        json.dumps({"fixture": str(redirected_root)}),
    )
    output_config = tmp_path / "published" / "configs" / "trustmark_selected.yaml"

    result = freeze_trustmark_selected_config(
        CANONICAL_BASELINE,
        selected_benchmark_config=selected_config,
        output_config=output_config,
    )

    source = yaml.safe_load(CANONICAL_BASELINE.read_text(encoding="utf-8"))
    frozen = yaml.safe_load(output_config.read_text(encoding="utf-8"))
    assert result["status"] == "created"
    assert result["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert result["generic_dataset_environment_overrides_ignored"] is True
    assert frozen["method"] == source["method"]
    assert frozen["experiment"]["attack_scope"] == "traditional_only"
    assert (
        _resolve_reference(
            output_config, frozen["experiment"]["source_benchmark_config"]
        )
        == selected_config.resolve()
    )
    assert _resolve_reference(
        output_config, frozen["experiment"]["output_root"]
    ) == _resolve_reference(CANONICAL_BASELINE, source["experiment"]["output_root"])
    evidence = frozen["selected_benchmark_evidence"]
    assert evidence["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert evidence["selected_benchmark_config_sha256"] == _sha256(selected_config)
    assert evidence["selected_manifest_sha256"] == _sha256(manifest_path)
    assert evidence["selected_manifest_lock_sha256"] == _sha256(lock_path)
    assert evidence["selected_manifest_total_samples"] == 1
    assert evidence["selected_manifest_test_samples"] == 1
    assert evidence["selected_required_capabilities"] == SELECTED_CAPABILITIES
    assert evidence["generic_dataset_environment_overrides_ignored"] is True


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("missing", "Required manifest lock is missing"),
        ("tampered", "Manifest lock evidence mismatch"),
    ],
)
def test_freeze_fails_closed_for_missing_or_tampered_selected_lock(
    tmp_path: Path, failure: str, message: str
) -> None:
    selected_config, _manifest_path, lock_path = _selected_benchmark_fixture(tmp_path)
    if failure == "missing":
        lock_path.unlink()
    else:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["assignment_sha256"] = "0" * 64
        lock_path.write_text(
            json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    output_config = tmp_path / "trustmark-selected.yaml"

    with pytest.raises(TrustMarkSelectedFreezeError, match=message):
        freeze_trustmark_selected_config(
            CANONICAL_BASELINE,
            selected_benchmark_config=selected_config,
            output_config=output_config,
        )

    assert not output_config.exists()


def test_freeze_refuses_overwrite_without_touching_existing_output(
    tmp_path: Path,
) -> None:
    selected_config, _manifest_path, _lock_path = _selected_benchmark_fixture(tmp_path)
    output_config = tmp_path / "already-there.yaml"
    original = b"user-owned-content\n"
    output_config.write_bytes(original)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        freeze_trustmark_selected_config(
            CANONICAL_BASELINE,
            selected_benchmark_config=selected_config,
            output_config=output_config,
        )

    assert output_config.read_bytes() == original


def test_freeze_rejects_nonselected_benchmark_before_publication(
    tmp_path: Path,
) -> None:
    selected_config, _manifest_path, _lock_path = _selected_benchmark_fixture(tmp_path)
    selected = yaml.safe_load(selected_config.read_text(encoding="utf-8"))
    selected.pop("formal_selection")
    selected_config.write_text(yaml.safe_dump(selected), encoding="utf-8")
    output_config = tmp_path / "not-created.yaml"

    with pytest.raises(
        TrustMarkSelectedFreezeError,
        match="lacks frozen development-only selection evidence",
    ):
        freeze_trustmark_selected_config(
            CANONICAL_BASELINE,
            selected_benchmark_config=selected_config,
            output_config=output_config,
        )

    assert not output_config.exists()


def test_freeze_fails_closed_when_channel_vote_chain_replay_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_config, _manifest_path, _lock_path = _selected_benchmark_fixture(tmp_path)
    output_config = tmp_path / "not-created-invalid-chain.yaml"

    def reject(_path: Path) -> dict[str, object]:
        raise ChannelVoteFormalFreezeError("confirmation evidence mismatch")

    monkeypatch.setattr(
        freeze_module,
        "validate_frozen_channel_vote_formal_config",
        reject,
    )
    with pytest.raises(
        TrustMarkSelectedFreezeError,
        match="channel-vote freeze validation failed",
    ):
        freeze_trustmark_selected_config(
            CANONICAL_BASELINE,
            selected_benchmark_config=selected_config,
            output_config=output_config,
        )

    assert not output_config.exists()
