from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from protection.supporting.image_watermark.experiments.manifest import ImageSample, write_manifest
from scripts.server import audit_image_watermark_redevelopment_history as audit


def _row(
    *,
    sample_id: str,
    relative_path: str,
    split: str,
    source_family: str,
    content: bytes,
) -> ImageSample:
    return ImageSample(
        sample_id=sample_id,
        relative_path=relative_path,
        split=split,
        source_dataset="fixture_dataset",
        domain="fixture_domain",
        license_id="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        provenance="fixture",
        source_family=source_family,
        sha256=hashlib.sha256(content).hexdigest(),
        width=8,
        height=8,
    )


def _bundle(tmp_path: Path) -> tuple[Path, Path, list[ImageSample]]:
    manifest = tmp_path / "formal.jsonl"
    config = tmp_path / "formal.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "manifest": {"path": str(manifest), "require_lock": True},
                "datasets": [
                    {
                        "name": "fixture_dataset",
                        "enabled": True,
                        "root": str(tmp_path / "missing-source-data"),
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    rows = [
        _row(
            sample_id="fixture_dataset:images/train.png",
            relative_path="images/train.png",
            split="train",
            source_family="fixture:family:train",
            content=b"train-source-bytes",
        ),
        _row(
            sample_id="fixture_dataset:images/test.png",
            relative_path="images/test.png",
            split="test",
            source_family="fixture:family:test",
            content=b"test-source-bytes",
        ),
    ]
    write_manifest(rows, manifest, config_path=config)
    return config, manifest, rows


def test_history_audit_combines_text_identity_and_exact_output_image_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, manifest, rows = _bundle(tmp_path)
    monkeypatch.setattr(audit, "EXPECTED_FORMAL_SAMPLES", 2)
    monkeypatch.setattr(audit, "EXPECTED_FORMAL_SPLITS", {"train": 1, "test": 1})
    evidence_root = tmp_path / "prior-outputs"
    evidence_root.mkdir()
    full_source_path = (
        tmp_path / "missing-source-data" / rows[0].relative_path
    ).resolve()
    (evidence_root / "row.json").write_text(
        json.dumps(
            {
                "sample_id": rows[0].sample_id,
                "source_family": rows[0].source_family,
                "input_path": str(full_source_path),
            }
        ),
        encoding="utf-8",
    )
    (evidence_root / "copied-source.png").write_bytes(b"test-source-bytes")
    shutil.copyfile(manifest, evidence_root / "formal-copy.jsonl")

    payload = audit.audit_history(
        config,
        scan_roots=[evidence_root],
        output_path=tmp_path / "ledger.json",
        hash_output_images=True,
        allow_missing_source_files=True,
        cutoff_utc=datetime(2100, 1, 1, tzinfo=timezone.utc),
    )

    assert payload["source_validation_mode"] == "portable_inventory_identity_only"
    assert payload["touched_total"] == 2
    assert payload["touched_by_formal_split"] == {"test": 1, "train": 1}
    assert payload["hashed_image_files"] == 1
    assert payload["exact_output_image_sha_hits"] == 1
    assert payload["canonical_manifest_copy_exclusion_count"] == 1
    touched = {row["sample_id"]: row for row in payload["touched_rows"]}
    train_matches = {item["match"] for item in touched[rows[0].sample_id]["evidence"]}
    assert train_matches == {
        "sample_id+source_family+full_source_path",
    }
    assert touched[rows[1].sample_id]["evidence"][0]["match"] == (
        "output_image_sha256"
    )


def test_history_audit_rejects_tampered_portable_manifest_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, manifest, _rows = _bundle(tmp_path)
    monkeypatch.setattr(audit, "EXPECTED_FORMAL_SAMPLES", 2)
    monkeypatch.setattr(audit, "EXPECTED_FORMAL_SPLITS", {"train": 1, "test": 1})
    lock_path = manifest.with_suffix(manifest.suffix + ".lock.json")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["manifest_sha256"] = "0" * 64
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    evidence_root = tmp_path / "prior-outputs"
    evidence_root.mkdir()

    with pytest.raises(ValueError, match="Portable manifest lock identity mismatch"):
        audit.audit_history(
            config,
            scan_roots=[evidence_root],
            output_path=tmp_path / "ledger.json",
            allow_missing_source_files=True,
        )


def test_cutoff_parser_requires_timezone() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        audit._parse_cutoff("2026-08-03T11:55:30")
    assert audit._parse_cutoff("2026-08-03T11:55:30Z") == datetime(
        2026, 8, 3, 11, 55, 30, tzinfo=timezone.utc
    )
