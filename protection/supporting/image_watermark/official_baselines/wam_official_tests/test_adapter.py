from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

import protection.supporting.image_watermark.official_baselines.wam_official_manifest_runner as runner_module
from protection.supporting.image_watermark.experiments.attacks import AttackSpec, expand_attack_specs
from protection.supporting.image_watermark.experiments.manifest import ImageSample, write_manifest
from protection.supporting.image_watermark.official_baselines.wam_official_adapter import (
    WamAdapterError,
    WamDetectionOutput,
    WamOfficialAdapter,
    WamOutputContractError,
)
from protection.supporting.image_watermark.official_baselines.wam_official_contract import (
    OFFICIAL_WAM_MIT,
    pinned_provenance,
)
from protection.supporting.image_watermark.official_baselines.wam_official_manifest_runner import (
    FORMAL_SEEDS,
    FORMAL_SOURCE_QUOTAS,
    FORMAL_TRADITIONAL_ATTACK_IDS,
    WamManifestError,
    WamManifestRunner,
    _artifact_slug,
    _native_message,
    _same_gt_mask,
)
from protection.supporting.image_watermark.official_baselines.wam_official_preflight import (
    DEPENDENCY_PINS,
    REQUIRED_REPOSITORY_FILES,
    WamPreflightError,
    require_ready,
    run_preflight,
)
from scripts.server.freeze_image_watermark_channel_vote_formal_config import (
    ChannelVoteFormalFreezeError,
)


MESSAGE = "01010101010101010101010101010101"


class MockWamBackend:
    def __init__(self, message: str = MESSAGE, *, no_detection: bool = False) -> None:
        self.message = np.fromiter((bit == "1" for bit in message), dtype=np.bool_)
        self.no_detection = no_detection
        self.tamper = (slice(4, 8), slice(5, 10))

    def embed(self, image_rgb: np.ndarray, message_bits: np.ndarray) -> np.ndarray:
        assert message_bits.shape == (32,)
        return np.minimum(image_rgb.astype(np.uint16) + 1, 255).astype(np.uint8)

    def detect(self, image_rgb: np.ndarray) -> WamDetectionOutput:
        height, width = image_rgb.shape[:2]
        probability = np.full((height, width), 0.9, dtype=np.float32)
        if self.no_detection:
            probability.fill(0.1)
        else:
            probability[self.tamper] = 0.1
        logits = np.broadcast_to(
            self.message.astype(np.float32)[:, None, None],
            (32, height, width),
        ).copy()
        return WamDetectionOutput(probability, logits)

    def runtime_provenance(self) -> dict[str, object]:
        return pinned_provenance()


class BadChannelBackend(MockWamBackend):
    def detect(self, image_rgb: np.ndarray) -> WamDetectionOutput:
        output = super().detect(image_rgb)
        return WamDetectionOutput(
            output.watermark_probability, output.message_logits[:31]
        )


class FailingThirdDetectionBackend(MockWamBackend):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def detect(self, image_rgb: np.ndarray) -> WamDetectionOutput:
        self.calls += 1
        if self.calls == 3:
            raise RuntimeError("fixture per-attack inference failure")
        return super().detect(image_rgb)


def _adapter(backend: MockWamBackend) -> WamOfficialAdapter:
    return WamOfficialAdapter(
        backend,
        ssim_evaluator=lambda _a, _b: 0.99,
        lpips_evaluator=lambda _a, _b: 0.01,
    )


def _image() -> np.ndarray:
    values = np.arange(16 * 16 * 3, dtype=np.uint16).reshape(16, 16, 3)
    return (values % 200).astype(np.uint8)


def _write_runner_fixture(tmp_path: Path) -> Path:
    dataset = tmp_path / "fixture-dataset"
    dataset.mkdir()
    image_path = dataset / "sample.png"
    Image.fromarray(_image(), mode="RGB").save(image_path)
    manifest = tmp_path / "fixture-manifest.jsonl"
    config = tmp_path / "fixture-benchmark.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "experiment": {"split": "test", "seeds": [7]},
                "manifest": {
                    "path": manifest.name,
                    "verify_hashes": True,
                    "require_lock": True,
                },
                "metrics": {"lpips": {"enabled": False}},
                "datasets": [
                    {"name": "fixture", "enabled": True, "root": dataset.name}
                ],
                "attacks": {
                    "traditional": [
                        {"name": "clean", "family": "clean"},
                        {
                            "name": "erasing",
                            "family": "removal",
                            "grid": [{"area_ratio": 0.05}],
                        },
                    ]
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_manifest(
        [
            ImageSample(
                sample_id="fixture:sample",
                relative_path="sample.png",
                split="test",
                source_dataset="fixture",
                domain="diagram",
                license_id="CC0-1.0",
                license_url="https://example.invalid/license",
                provenance="unit-test",
                sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                width=16,
                height=16,
                image_path=str(image_path),
            )
        ],
        manifest,
        config_path=config,
    )
    return config


def test_pinned_machine_readable_contract_is_native_wam() -> None:
    assert OFFICIAL_WAM_MIT.repository_commit == (
        "2c08af04d037d5667c02f6ddebbda9ff04581c3e"
    )
    assert OFFICIAL_WAM_MIT.checkpoint_bytes == 377_825_938
    assert OFFICIAL_WAM_MIT.checkpoint_sha256 == (
        "90ef232384e023bd63245eb0c131abd69d2afc7b8f17a71ccedceb542bf009e2"
    )
    assert OFFICIAL_WAM_MIT.checkpoint_license == "MIT"
    assert OFFICIAL_WAM_MIT.scaling_w == 2.0
    assert OFFICIAL_WAM_MIT.message_bits == 32
    assert OFFICIAL_WAM_MIT.detector_channels == 33
    assert OFFICIAL_WAM_MIT.watermark_detection_channels == 1
    assert OFFICIAL_WAM_MIT.message_logit_channels == 32
    provenance = pinned_provenance()
    semantics = provenance["native_semantics"]
    assert semantics["source_registry_mapping"] == "none"
    assert semantics["cogniguard_64bit_hmac_capsule_equivalent"] is False
    assert OFFICIAL_WAM_MIT.params_sha256 == (
        "d133a504d126b56b3e980add9fc014d718e3635a0f5740d8d6dc3190007fb476"
    )
    pins = {pin.distribution: pin.version for pin in DEPENDENCY_PINS}
    assert pins["numpy"] == "1.26.4"
    assert pins["Pillow"] == "10.4.0"


def test_install_contract_requires_dedicated_python_and_official_cu121_index() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "wam_official_install.sh").read_text(encoding="utf-8")
    requirements = (root / "wam_official_requirements.txt").read_text(encoding="utf-8")
    assert "${VENV:?" in script and "${PYTHON:?" in script
    assert ".venv-server" in script
    assert "https://download.pytorch.org/whl/cu121" in script
    assert '"${PYTHON}" -m pip install' in script
    assert "numpy==1.26.4" in requirements
    assert "Pillow==10.4.0" in requirements
    assert "torch==2.5.1" not in requirements


def test_full_frame_embed_uses_explicit_all_ones_mask_and_shared_quality() -> None:
    image = _image()
    result = _adapter(MockWamBackend()).embed(image, MESSAGE)
    assert result.embedding_mask.dtype == np.bool_
    assert result.embedding_mask.all()
    assert result.record["embedding"]["mask_mode"] == "full_image_all_ones"
    assert result.record["embedding"]["mask_area_fraction"] == 1.0
    assert result.record["native_message"]["bit_length"] == 32
    assert result.record["common_metrics"]["ssim"] == 0.99
    assert result.record["common_metrics"]["lpips"] == 0.01
    assert result.record["common_metrics"]["psnr_db"] is not None
    assert result.record["common_metrics"]["embed_latency_ms"] >= 0.0
    assert result.record["registry_mapping"] == "none"
    assert result.record["cogniguard_64bit_hmac_capsule_equivalent"] is False


def test_partial_embed_changes_only_explicit_mask() -> None:
    image = _image()
    mask = np.zeros((16, 16), dtype=np.bool_)
    mask[2:9, 3:11] = True
    result = _adapter(MockWamBackend()).embed(image, MESSAGE, embedding_mask=mask)
    assert np.array_equal(result.watermarked_image[~mask], image[~mask])
    assert np.all(result.watermarked_image[mask] == image[mask] + 1)
    assert result.record["embedding"]["mask_mode"] == "caller_supplied_binary_mask"


def test_verify_reports_native_recovery_detection_and_same_gt_localization() -> None:
    backend = MockWamBackend()
    attack = AttackSpec(name="erasing", family="removal")
    gt = _same_gt_mask(
        attack,
        {"truth_bbox": [5, 4, 10, 8]},
        (16, 16),
    )
    assert gt is not None
    assert int(gt.sum()) == (10 - 5) * (8 - 4) == 20
    assert gt[4:8, 5:10].all()
    assert not gt[8, 5:10].any()  # bottom is excluded
    assert not gt[4:8, 10].any()  # right is excluded
    result = _adapter(backend).verify(
        _image(), MESSAGE, attack_gt_tamper_mask=gt, attack_id="splice"
    )
    recovery = result.record["native_32bit_message_recovery"]
    assert recovery["bit_length"] == 32
    assert recovery["raw_bit_accuracy"] == 1.0
    assert recovery["raw_exact"] is True
    detection = result.record["native_watermark_detection"]
    assert detection["output_channels"] == {
        "watermark_presence": 1,
        "message_logits": 32,
        "total": 33,
    }
    assert detection["image_level_watermark_present"] is None
    assert detection["image_level_decision_status"] == (
        "not_computed_no_pinned_official_image_level_threshold"
    )
    assert detection["pixel_logit_threshold"] == 0.0
    assert detection["pixel_probability_threshold"] == 0.5
    assert 0.0 < detection["detected_area_fraction"] < 1.0
    assert detection["presence_score_summary"]["mean_probability"] > 0.5
    localization = result.record["localization_same_attack_gt"]
    assert localization["table_scope"] == "separate_same_attack_gt_only"
    assert localization["attack_id"] == "splice"
    assert localization["native_watermark_presence"]["iou"] == 1.0
    assert (
        localization["derived_tamper_from_watermark_absence_within_support"]["iou"]
        == 1.0
    )
    assert np.array_equal(result.predicted_tamper_mask, gt)
    rendered = json.dumps(result.record, sort_keys=True)
    assert "source_registry_match" not in rendered
    assert result.record["registry_lookup_performed"] is False
    assert result.record["cogniguard_64bit_hmac_capsule_equivalent"] is False


def test_no_detected_pixels_is_recorded_as_decode_failure_not_fake_bits() -> None:
    result = _adapter(MockWamBackend(no_detection=True)).verify(_image(), MESSAGE)
    recovery = result.record["native_32bit_message_recovery"]
    assert recovery["recovered_bits"] is None
    assert recovery["raw_bit_accuracy"] is None
    assert recovery["raw_exact"] is False
    assert recovery["decode_status"] == "no_watermarked_pixels_detected"
    detection = result.record["native_watermark_detection"]
    assert detection["detected_area_fraction"] == 0.0
    assert detection["image_level_watermark_present"] is None


def test_native_adapter_rejects_64_bit_capsule_and_wrong_channels() -> None:
    adapter = _adapter(MockWamBackend())
    with pytest.raises(WamAdapterError, match="native 32-bit"):
        adapter.embed(_image(), np.zeros(64, dtype=np.uint8))
    with pytest.raises(WamOutputContractError, match="32xHxW"):
        _adapter(BadChannelBackend()).verify(_image(), MESSAGE)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fixture_installation(tmp_path: Path):
    repo = tmp_path / "wam"
    repo.mkdir()
    for relative in REQUIRED_REPOSITORY_FILES:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "LICENSE":
            path.write_text("MIT License\nfixture only\n", encoding="utf-8")
        elif path.suffix in {".yaml", ".py"}:
            path.write_text("# fixture\n", encoding="utf-8")
    params = {
        "embedder_config": "configs/embedder.yaml",
        "augmentation_config": "configs/all_augs_multi_wm.yaml",
        "extractor_config": "configs/extractor.yaml",
        "attenuation_config": "configs/attenuation.yaml",
        "nbits": 32,
        "scaling_w": 2.0,
        "scaling_i": 1.0,
        "img_size_extractor": 256,
    }
    params_path = repo / "checkpoints" / "params.json"
    params_path.parent.mkdir(parents=True, exist_ok=True)
    params_path.write_text(json.dumps(params, sort_keys=True), encoding="utf-8")
    checkpoint = tmp_path / "wam_mit.pth"
    checkpoint.write_bytes(b"tiny-test-checkpoint")
    _git(repo, "init")
    _git(repo, "config", "user.email", "wam-test@example.invalid")
    _git(repo, "config", "user.name", "WAM Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    commit = _git(repo, "rev-parse", "HEAD")
    contract = replace(
        OFFICIAL_WAM_MIT,
        repository_commit=commit,
        checkpoint_bytes=checkpoint.stat().st_size,
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        params_sha256=hashlib.sha256(params_path.read_bytes()).hexdigest(),
    )
    return repo, checkpoint, params_path, contract


def test_preflight_accepts_only_complete_matching_installation(tmp_path: Path) -> None:
    repo, checkpoint, _params, contract = _fixture_installation(tmp_path)
    report = run_preflight(
        repo,
        checkpoint,
        device="cpu",
        check_dependencies=False,
        contract=contract,
    )
    assert report["ready"] is True
    require_ready(report)
    assert report["artifacts"]["repository_commit"] == contract.repository_commit
    assert report["artifacts"]["checkpoint_bytes"] == contract.checkpoint_bytes
    assert report["artifacts"]["checkpoint_sha256"] == contract.checkpoint_sha256
    semantics_check = next(
        item for item in report["checks"] if item["name"] == "params:native_semantics"
    )
    assert semantics_check["evidence"]["detector_channels"] == 33
    assert semantics_check["evidence"]["detection_channels"] == 1
    assert semantics_check["evidence"]["message_channels"] == 32


def test_preflight_fails_closed_on_weight_or_params_change(tmp_path: Path) -> None:
    repo, checkpoint, params, contract = _fixture_installation(tmp_path)
    checkpoint.write_bytes(b"changed")
    report = run_preflight(
        repo,
        checkpoint,
        device="cpu",
        check_dependencies=False,
        contract=contract,
    )
    assert report["ready"] is False
    with pytest.raises(WamPreflightError, match="checkpoint:bytes"):
        require_ready(report)

    checkpoint.write_bytes(b"tiny-test-checkpoint")
    payload = json.loads(params.read_text(encoding="utf-8"))
    payload["nbits"] = 64
    params.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    report = run_preflight(
        repo,
        checkpoint,
        device="cpu",
        check_dependencies=False,
        contract=contract,
    )
    assert report["ready"] is False
    failures = {item["name"] for item in report["checks"] if not item["passed"]}
    assert "params:sha256" in failures
    assert "params:native_semantics" in failures
    assert "repository:tracked_files_clean" in failures


def test_preflight_rejects_untracked_shadow_module_and_invalid_device(
    tmp_path: Path,
) -> None:
    repo, checkpoint, _params, contract = _fixture_installation(tmp_path)
    shadow = repo / "watermark_anything" / "shadow.py"
    shadow.write_text("raise RuntimeError('shadow')\n", encoding="utf-8")
    report = run_preflight(
        repo,
        checkpoint,
        device="cuda:-1",
        check_dependencies=False,
        contract=contract,
    )
    failures = {item["name"] for item in report["checks"] if not item["passed"]}
    assert "runtime:device_syntax" in failures
    assert "repository:tracked_and_untracked_files_clean" in failures
    assert report["ready"] is False


def test_default_preflight_fails_closed_when_artifacts_are_missing(
    tmp_path: Path,
) -> None:
    report = run_preflight(
        tmp_path / "missing-repo",
        tmp_path / "missing-weight.pth",
        device="cpu",
        check_dependencies=False,
    )
    assert report["ready"] is False
    with pytest.raises(WamPreflightError):
        require_ready(report)


def test_same_manifest_runner_is_independent_and_emits_auditable_rows(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    image_path = dataset / "sample.png"
    Image.fromarray(_image(), mode="RGB").save(image_path)
    source_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "sample_id": "fixture:sample",
                "relative_path": "sample.png",
                "split": "test",
                "source_dataset": "fixture",
                "domain": "diagram",
                "license_id": "CC0-1.0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "provenance": "unit-test",
                "sha256": source_sha,
                "width": 16,
                "height": 16,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    config = tmp_path / "benchmark.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "experiment": {"split": "test", "seeds": [7]},
                "manifest": {"path": "manifest.jsonl", "verify_hashes": True},
                "metrics": {"lpips": {"enabled": False}},
                "datasets": [
                    {
                        "name": "fixture",
                        "enabled": True,
                        "root": "dataset",
                    }
                ],
                "attacks": {
                    "traditional": [
                        {"name": "clean", "family": "clean"},
                        {
                            "name": "erasing",
                            "family": "removal",
                            "grid": [{"area_ratio": 0.05}],
                        },
                    ]
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "out"
    runner = WamManifestRunner(
        config,
        output,
        _adapter(MockWamBackend()),
        mode="smoke",
        limit=1,
        lpips_enabled=False,
        allow_test_backend=True,
    )
    summary = runner.run()
    assert summary["rows"] == 2
    assert summary["unique_samples"] == 1
    assert summary["registry_metrics"] == "not_applicable"
    assert summary["cogniguard_64bit_hmac_capsule_equivalent"] is False
    assert summary["aigc_included"] is False
    assert summary["mode"] == "smoke"
    assert summary["paper_eligible"] is False
    assert summary["paper_eligibility_status"] == "invalid_smoke_run"
    assert (output / "raw_results.jsonl").is_file()
    assert (output / "original_negative_controls.jsonl").is_file()
    assert (output / "selected_test_samples.jsonl").is_file()
    assert (output / "environment.json").is_file()
    assert (output / "summary.json").is_file()
    rows = [
        json.loads(line)
        for line in (output / "raw_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {row["attack_id"] for row in rows} == {
        "clean",
        "erasing",
    }
    assert all(row["registry_lookup_performed"] is False for row in rows)
    assert all(row["native_message_bits"] == 32 for row in rows)
    assert all(row["paper_eligible"] is False for row in rows)
    assert all(len(row["attacked_image_sha256"]) == 64 for row in rows)
    assert all(len(row["attacks_source_sha256"]) == 64 for row in rows)
    assert all(row["attack_numpy_version"] for row in rows)
    assert all(row["attack_pillow_version"] for row in rows)
    assert all(row["image_level_watermark_present"] is None for row in rows)
    negatives = [
        json.loads(line)
        for line in (output / "original_negative_controls.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(negatives) == 1
    assert negatives[0]["image_level_watermark_present"] is None
    assert (
        summary["original_image_negative_controls"]["image_level_false_positive_rate"]
        is None
    )
    assert _native_message("fixture:sample", 7) == _native_message("fixture:sample", 7)
    assert len(_native_message("fixture:sample", 7)) == 32
    assert _native_message("fixture:sample", 7) != _native_message("fixture:sample", 8)


def test_manifest_runner_rejects_mock_backend_by_default(tmp_path: Path) -> None:
    with pytest.raises(WamManifestError, match="injected/mock"):
        WamManifestRunner(
            tmp_path / "config.yaml",
            tmp_path / "out",
            _adapter(MockWamBackend()),
            mode="smoke",
            limit=1,
            lpips_enabled=False,
        )


def test_safe_artifact_slug_cannot_traverse_and_is_collision_resistant() -> None:
    first = _artifact_slug("../../attack name")
    second = _artifact_slug("..\\..\\attack name")
    assert "/" not in first and "\\" not in first and ".." not in first
    assert "/" not in second and "\\" not in second and ".." not in second
    assert first != second


def test_formal_contract_checks_global_3000_quotas_test_set_and_full_grid(
    tmp_path: Path,
) -> None:
    canonical_path = (
        Path(__file__).resolve().parents[2] / "configs" / "paper_benchmark.yaml"
    )
    config = yaml.safe_load(canonical_path.read_text(encoding="utf-8"))
    all_rows: list[ImageSample] = []
    selected: list[ImageSample] = []
    for source, quota in FORMAL_SOURCE_QUOTAS.items():
        test_count = quota // 5
        for index in range(quota):
            row = ImageSample(
                sample_id=f"{source}:{index:04d}",
                relative_path=f"{index:04d}.png",
                split="test" if index < test_count else "train",
                source_dataset=source,
                domain=f"domain-{index % 4}",
                license_id="fixture",
                license_url="https://example.invalid/license",
                provenance="fixture",
                sha256=hashlib.sha256(
                    f"{source}:{index:04d}".encode("utf-8")
                ).hexdigest(),
            )
            all_rows.append(row)
            if row.split == "test":
                selected.append(row)
    specs = expand_attack_specs(config["attacks"]["traditional"])
    assert tuple(spec.params.get("expanded_name") or spec.name for spec in specs) == (
        FORMAL_TRADITIONAL_ATTACK_IDS
    )
    runner = WamManifestRunner(
        canonical_path,
        tmp_path / "formal-out",
        _adapter(MockWamBackend()),
        mode="formal",
        allow_test_backend=True,
    )
    runner._validate_formal_inputs(
        config=config,
        all_rows=all_rows,
        selected=selected,
        specs=specs,
        seeds=list(FORMAL_SEEDS),
        split="test",
    )
    assert len(all_rows) == 3000
    assert len(selected) == 600

    corrupted = list(all_rows)
    corrupted[0] = replace(
        corrupted[0], source_dataset="open_images_v7_license_audited"
    )
    with pytest.raises(WamManifestError, match="source quotas mismatch"):
        runner._validate_formal_inputs(
            config=config,
            all_rows=corrupted,
            selected=selected,
            specs=specs,
            seeds=list(FORMAL_SEEDS),
            split="test",
        )


def test_formal_mode_rejects_any_partial_selector(tmp_path: Path) -> None:
    with pytest.raises(WamManifestError, match="formal mode forbids"):
        WamManifestRunner(
            tmp_path / "config.yaml",
            tmp_path / "out",
            _adapter(MockWamBackend()),
            mode="formal",
            seeds=[20260802],
            allow_test_backend=True,
        )


def test_formal_hash_only_retention_and_atomic_no_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write_runner_fixture(tmp_path)
    redirected_manifest = tmp_path / "secure-env-redirect.jsonl"
    redirected_manifest.write_text("{}\n", encoding="utf-8")
    redirected_root = tmp_path / "secure-env-root"
    redirected_root.mkdir()
    monkeypatch.setenv(
        "COGNIGUARD_WATERMARK_DATASET_MANIFEST", str(redirected_manifest)
    )
    monkeypatch.setenv(
        "COGNIGUARD_DATASET_ROOTS_JSON",
        json.dumps({"fixture": str(redirected_root)}),
    )
    output = tmp_path / "formal-hash-only"
    runner = WamManifestRunner(
        config,
        output,
        _adapter(MockWamBackend()),
        mode="formal",
        allow_test_backend=True,
    )
    monkeypatch.setattr(runner, "_validate_formal_inputs", lambda **_kwargs: None)
    summary = runner.run()
    assert summary["paper_eligible"] is False
    assert summary["observed_rows"] == 2
    rows = [
        json.loads(line)
        for line in (output / "raw_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    clean = next(row for row in rows if row["attack_id"] == "clean")
    erased = next(row for row in rows if row["attack_id"] == "erasing")
    assert clean["attacked_image_path"] is None
    assert clean["attacked_artifact_retention"] == (
        "hash_only_shared_watermarked_deleted_after_grid"
    )
    assert erased["attacked_image_path"] is None
    assert erased["attacked_artifact_retention"] == (
        "hash_only_deleted_after_successful_verify"
    )
    assert not list(output.rglob("attack-*.png"))
    assert not list(output.rglob("watermarked.png"))
    assert all(row["watermarked_image_path"] is None for row in rows)
    assert all(len(row["watermarked_image_sha256"]) == 64 for row in rows)
    assert all(row["watermarked_image_bytes"] > 0 for row in rows)
    assert all(
        row["watermarked_artifact_retention"]
        == "hash_only_deleted_after_complete_attack_grid"
        for row in rows
    )
    environment = json.loads((output / "environment.json").read_text(encoding="utf-8"))
    assert environment["artifact_retention"]["watermarked_clean_images"] == (
        "hash_only_deleted_after_complete_attack_grid"
    )
    assert environment["artifact_retention"]["nonclean_attacked_images"] == (
        "hash_only_deleted_after_success"
    )
    locked_manifest = tmp_path / "fixture-manifest.jsonl"
    lock_path = locked_manifest.with_suffix(".jsonl.lock.json")
    assert environment["manifest_path"] == str(locked_manifest.resolve())
    assert environment["manifest_lock"]["lock_path"] == str(lock_path.resolve())
    assert (
        environment["manifest_lock"]["lock_sha256"]
        == hashlib.sha256(lock_path.read_bytes()).hexdigest()
    )
    selected_ids = [
        json.loads(line)["sample_id"]
        for line in (output / "selected_test_samples.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert (
        environment["selected_sample_ids_sha256"]
        == hashlib.sha256("\n".join(selected_ids).encode("utf-8")).hexdigest()
    )
    assert environment["input_resolution"]["benchmark_config_authoritative"] is True
    assert environment["input_resolution"]["environment_overrides_allowed"] is False
    assert all(
        environment["input_resolution"][
            "ignored_environment_override_presence"
        ].values()
    )
    with pytest.raises(WamManifestError, match="overwrite"):
        runner.run()


@pytest.mark.parametrize(
    ("lock_failure", "message"),
    [
        ("missing", "Required manifest lock is missing"),
        ("tampered", "Manifest lock evidence mismatch"),
    ],
)
def test_formal_manifest_lock_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lock_failure: str,
    message: str,
) -> None:
    config = _write_runner_fixture(tmp_path)
    lock_path = (tmp_path / "fixture-manifest.jsonl").with_suffix(".jsonl.lock.json")
    if lock_failure == "missing":
        lock_path.unlink()
    else:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        payload["assignment_sha256"] = "0" * 64
        lock_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    runner = WamManifestRunner(
        config,
        tmp_path / "formal-lock-failure",
        _adapter(MockWamBackend()),
        mode="formal",
        allow_test_backend=True,
    )
    monkeypatch.setattr(runner, "_validate_formal_inputs", lambda **_kwargs: None)

    with pytest.raises(WamManifestError, match=message):
        runner._inputs()


def test_formal_channel_vote_chain_failure_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _write_runner_fixture(tmp_path)
    runner = WamManifestRunner(
        config,
        tmp_path / "formal-invalid-selection",
        _adapter(MockWamBackend()),
        mode="formal",
        allow_test_backend=True,
    )

    def reject(_path: Path) -> dict[str, object]:
        raise ChannelVoteFormalFreezeError("confirmation evidence mismatch")

    monkeypatch.setattr(
        runner_module,
        "validate_frozen_channel_vote_formal_config",
        reject,
    )
    with pytest.raises(WamManifestError, match="not an authentic channel-vote"):
        runner._validate_formal_selected_config()


def test_single_attack_inference_failure_keeps_complete_cartesian_rows(
    tmp_path: Path,
) -> None:
    config = _write_runner_fixture(tmp_path)
    output = tmp_path / "failure-row-run"
    runner = WamManifestRunner(
        config,
        output,
        _adapter(FailingThirdDetectionBackend()),
        mode="smoke",
        limit=1,
        lpips_enabled=False,
        allow_test_backend=True,
    )
    summary = runner.run()
    rows = [
        json.loads(line)
        for line in (output / "raw_results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) == 2
    assert len({row["row_key"] for row in rows}) == 2
    failure = next(row for row in rows if row["pipeline_success"] is False)
    assert failure["status"] == "inference_error"
    assert failure["native_32bit_raw_bit_accuracy_strict"] == 0.0
    assert failure["native_32bit_raw_exact"] is False
    assert failure["error_stage"] == "verify_inference"
    assert failure["error_type"] == "RuntimeError"
    assert failure["attacked_artifact_retention"] == (
        "retained_failed_inference_diagnostic"
    )
    assert summary["failed_rows"] == 1
    assert summary["pipeline_failure_rate"] == 0.5
    assert summary["paper_claim_status"] == "invalid_smoke_run"
