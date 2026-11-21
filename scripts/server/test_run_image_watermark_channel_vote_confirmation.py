from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_confirmation_runner_and_shared_executor_are_bash_syntax_valid() -> None:
    root = _project_root()
    for script in (
        "scripts/server/run_image_watermark_channel_vote_confirmation.sh",
        "scripts/server/image_watermark_benchmark.sbatch",
    ):
        subprocess.run(["bash", "-n", script], cwd=root, check=True)


def test_confirmation_runner_requires_explicit_frozen_sources_despite_generic_overrides() -> None:
    root = _project_root()
    environment = os.environ.copy()
    environment.pop("FORMAL_BENCHMARK_CONFIG", None)
    environment.pop("THRESHOLD_CALIBRATION_RUN_ROOT", None)
    environment.pop("SERVER_ENV_FILE", None)
    environment.update(
        {
            "COGNIGUARD_WATERMARK_BENCHMARK_CONFIG": "poison.yaml",
            "COGNIGUARD_WATERMARK_DATASET_MANIFEST": "poison.jsonl",
            "COGNIGUARD_DATASET_ROOTS_JSON": '{"poison":"root"}',
        }
    )

    completed = subprocess.run(
        ["bash", "scripts/server/run_image_watermark_channel_vote_confirmation.sh"],
        cwd=root,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "must both be supplied explicitly" in completed.stderr


def test_confirmation_is_preregistered_before_the_only_candidate_and_fails_closed() -> None:
    root = _project_root()
    runner_text = (
        root / "scripts/server/run_image_watermark_channel_vote_confirmation.sh"
    ).read_text(encoding="utf-8")
    build_at = runner_text.index("build_image_watermark_channel_vote_confirmation.py")
    run_at = runner_text.index('bash "${PROJECT_ROOT}/scripts/server/image_watermark_benchmark.sbatch"')
    analyze_at = runner_text.index("analyze_image_watermark_channel_vote_confirmation.py")

    assert build_at < run_at < analyze_at
    assert "preregistration is incomplete or candidate artifacts predate it" in runner_text
    assert 'CANDIDATE_ID="recovery_threshold_0p34__channel_vote_2of3"' in runner_text
    assert 'CANDIDATE_DIR="${RUN_ROOT}/confirmation-run/${CANDIDATE_ID}"' in runner_text
    assert "SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34" in runner_text
    assert "SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=2" in runner_text
    assert "SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001" in runner_text
    assert "BENCHMARK_RESUME=0" in runner_text
    assert "COGNIGUARD_PREREGISTRATION_CLAIM_PATH" in runner_text
    assert "COGNIGUARD_PREREGISTRATION_NONCE" in runner_text
    assert 'mkdir -- "${RUN_ROOT}/confirmation-run"' in runner_text
    assert "CHANNEL_VOTE_CONFIRMATION_MIN_DATASET_SAMPLES=216" in runner_text
    assert "CHANNEL_VOTE_CONFIRMATION_MIN_SELECTED_SAMPLES=216" in runner_text
    assert "CHANNEL_VOTE_CONFIRMATION_MIN_SOURCE_DATASETS=4" in runner_text
    assert 'if (( MIN_CONTENT_DOMAINS < 9 )); then' in runner_text
    assert (
        'CHANNEL_VOTE_CONFIRMATION_MIN_CONTENT_DOMAINS="${MIN_CONTENT_DOMAINS}"'
        in runner_text
    )
    assert "unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG" in runner_text
    assert "unset COGNIGUARD_WATERMARK_DATASET_MANIFEST" in runner_text
    assert "unset COGNIGUARD_DATASET_ROOTS_JSON" in runner_text
    assert 'if [[ "${ANALYZER_STATUS}" == "2" ]]' in runner_text
    assert "exit 2" in runner_text[analyze_at:]


def test_shared_executor_has_isolated_confirmation_mode_and_strict_capability_gate() -> None:
    root = _project_root()
    sbatch_text = (
        root / "scripts/server/image_watermark_benchmark.sbatch"
    ).read_text(encoding="utf-8")

    assert 'CHANNEL_VOTE_CONFIRMATION_MODE="${CHANNEL_VOTE_CONFIRMATION_MODE:-0}"' in sbatch_text
    assert 'if [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then MODE_COUNT=' in sbatch_text
    assert 'RUN_CLASS="channel_vote_confirmation_development_only"' in sbatch_text
    assert (
        'MIN_CONTENT_DOMAINS_EFFECTIVE="${CHANNEL_VOTE_CONFIRMATION_MIN_CONTENT_DOMAINS:-9}"'
        in sbatch_text
    )
    assert "forbids inherited or fabricated SLURM_JOB_ID" in sbatch_text
    assert "forbids re-sourcing SERVER_ENV_FILE" in sbatch_text
    assert "channel-vote confirmation config gate: ready" in sbatch_text
    assert "channel-vote confirmation binding gate:" in sbatch_text
    assert "channel-vote confirmation capability gate:" in sbatch_text
    for declaration in (
        '"recovery_threshold": 0.34',
        '"tamper_area_threshold": 0.001',
        '"registry_hamming_radius": 1',
        '"localization_postprocessing": "none"',
        '"localization_mask_rule_version": "editguard_residual_channel_vote_v2"',
        '"localization_residual_channels": 3',
        '"localization_channel_aggregation": "k_of_3"',
        '"localization_channel_vote_min": 2',
        '"localization_residual_threshold_rule": "abs_gt_recovery_threshold_per_channel"',
        '"attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting"',
        '"deterministic_mode_enabled": True',
    ):
        assert declaration in sbatch_text
    assert "attack_model_revision" in sbatch_text
    assert "validate_required_capabilities" in sbatch_text
    assert "scripts.server.image_watermark_preregistration validate" in sbatch_text
    assert "scripts.server.image_watermark_preregistration copy" in sbatch_text
    assert 'if ! mkdir -- "${RUN_DIR}"; then' in sbatch_text
    assert 'export COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${RUN_DIR}/preregistration-claim.json"' in sbatch_text
