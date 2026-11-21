from __future__ import annotations

import re
import subprocess
import sys
import types
from pathlib import Path

import pytest
import yaml

from protection.supporting.image_watermark.experiments import paper_benchmark as paper_benchmark_module
from protection.supporting.image_watermark.experiments.paper_benchmark import (
    BenchmarkError,
    resolve_formal_service_thresholds,
)


def _install_freeze_validator(
    monkeypatch: pytest.MonkeyPatch,
    validator: object,
) -> type[RuntimeError]:
    class FakeFormalFreezeError(RuntimeError):
        pass

    fake_module = types.ModuleType(
        "scripts.server.freeze_image_watermark_formal_config"
    )
    fake_module.FormalFreezeError = FakeFormalFreezeError
    fake_module.validate_frozen_formal_config = validator
    monkeypatch.setitem(
        sys.modules,
        "scripts.server.freeze_image_watermark_formal_config",
        fake_module,
    )
    return FakeFormalFreezeError


def _threshold_required_capabilities(
    *, recovery_threshold: object = 0.28, tamper_area_threshold: object = 0.001
) -> dict[str, object]:
    return {
        "recovery_threshold": recovery_threshold,
        "tamper_area_threshold": tamper_area_threshold,
        "registry_hamming_radius": 1,
        "localization_postprocessing": "none",
        "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
        "localization_residual_channels": 3,
        "localization_channel_aggregation": "k_of_3",
        "localization_channel_vote_min": 1,
        "localization_residual_threshold_rule": (
            "abs_gt_recovery_threshold_per_channel"
        ),
        "attack_model_id": paper_benchmark_module.FORMAL_ATTACK_MODEL_ID,
        "attack_model_revision": "1" * 40,
        "deterministic_mode_enabled": True,
    }


def _write_selected_source_tree_binding(
    path: Path, *, required: dict[str, object] | None = None
) -> None:
    required = required or _threshold_required_capabilities()
    path.write_text(
        yaml.safe_dump(
            {
                "methods": [
                    {
                        "id": "editguard_wrapper",
                        "enabled": True,
                        "required_capabilities": required,
                    }
                ],
                "formal_selection": {
                    "schema_version": (
                        paper_benchmark_module.THRESHOLD_FORMAL_SELECTION_SCHEMA_VERSION
                    ),
                    "selection_source": (
                        paper_benchmark_module.THRESHOLD_FORMAL_SELECTION_SOURCE
                    ),
                    "method_id": "editguard_wrapper",
                    "selected_parameters": required,
                    "calibration_source_tree_identity_version": (
                        paper_benchmark_module.SOURCE_TREE_IDENTITY_VERSION
                    ),
                    "calibration_source_tree_scope": (
                        paper_benchmark_module._source_tree_identity_scope()
                    ),
                    "calibration_source_tree_sha256": "a" * 64,
                    "calibration_source_tree_file_count": 7,
                }
            }
        ),
        encoding="utf-8",
    )


def test_formal_thresholds_come_only_from_public_freeze_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_config = tmp_path / "paper_benchmark_selected_v1.yaml"
    required = _threshold_required_capabilities()
    _write_selected_source_tree_binding(selected_config, required=required)
    observed: dict[str, object] = {}

    def validate(
        config_path: Path,
        *,
        expected_formal_samples: int,
    ) -> dict[str, object]:
        observed["config_path"] = config_path
        observed["expected_formal_samples"] = expected_formal_samples
        return required

    _install_freeze_validator(monkeypatch, validate)
    monkeypatch.setattr(
        paper_benchmark_module,
        "_source_tree_identity",
        lambda _project_root: {
            "identity_version": paper_benchmark_module.SOURCE_TREE_IDENTITY_VERSION,
            "scope": paper_benchmark_module._source_tree_identity_scope(),
            "sha256": "a" * 64,
            "file_count": 7,
        },
    )
    monkeypatch.setattr(
        paper_benchmark_module,
        "_require_current_formal_runtime",
        lambda *_args, **_kwargs: None,
    )

    thresholds = resolve_formal_service_thresholds(
        selected_config,
        expected_formal_samples=3000,
    )

    assert thresholds == (0.28, 0.001)
    assert all(type(value) is float for value in thresholds)
    assert observed == {
        "config_path": selected_config,
        "expected_formal_samples": 3000,
    }


def test_formal_thresholds_fail_closed_when_freeze_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_config = tmp_path / "selected.yaml"
    _write_selected_source_tree_binding(selected_config)
    error_type: type[RuntimeError]

    def reject(
        _config_path: Path,
        *,
        expected_formal_samples: int,
    ) -> dict[str, object]:
        assert expected_formal_samples == 3000
        raise error_type("candidate evidence mismatch")

    error_type = _install_freeze_validator(monkeypatch, reject)

    with pytest.raises(BenchmarkError, match="candidate evidence mismatch"):
        resolve_formal_service_thresholds(selected_config)


@pytest.mark.parametrize(
    ("required", "message"),
    (
        (
            {"recovery_threshold": 1, "tamper_area_threshold": 0.001},
            "finite float",
        ),
        (
            {"recovery_threshold": 0.28, "tamper_area_threshold": 1.0},
            "mismatch",
        ),
    ),
)
def test_formal_thresholds_reject_invalid_validated_scalars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    required: dict[str, object],
    message: str,
) -> None:
    selected_config = tmp_path / "selected.yaml"
    full_required = _threshold_required_capabilities(
        recovery_threshold=required["recovery_threshold"],
        tamper_area_threshold=required["tamper_area_threshold"],
    )
    _write_selected_source_tree_binding(selected_config, required=full_required)

    def validate(
        _config_path: Path,
        *,
        expected_formal_samples: int,
    ) -> dict[str, object]:
        assert expected_formal_samples == 3000
        return full_required

    _install_freeze_validator(monkeypatch, validate)
    monkeypatch.setattr(
        paper_benchmark_module,
        "_source_tree_identity",
        lambda _project_root: {
            "identity_version": paper_benchmark_module.SOURCE_TREE_IDENTITY_VERSION,
            "scope": paper_benchmark_module._source_tree_identity_scope(),
            "sha256": "a" * 64,
            "file_count": 7,
        },
    )
    monkeypatch.setattr(
        paper_benchmark_module,
        "_require_current_formal_runtime",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(BenchmarkError, match=message):
        resolve_formal_service_thresholds(selected_config)


def test_formal_direct_shell_entrypoint_is_syntax_valid_and_fail_closed() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runner_path = project_root / "scripts" / "server" / "run_image_watermark_formal.sh"
    sbatch_path = (
        project_root / "scripts" / "server" / "image_watermark_benchmark.sbatch"
    )

    subprocess.run(
        ["bash", "-n", "scripts/server/run_image_watermark_formal.sh"],
        check=True,
        cwd=project_root,
    )
    subprocess.run(
        ["bash", "-n", "scripts/server/image_watermark_benchmark.sbatch"],
        check=True,
        cwd=project_root,
    )
    runner = runner_path.read_text(encoding="utf-8")
    sbatch = sbatch_path.read_text(encoding="utf-8")
    pilot = (project_root / "scripts/server/run_image_watermark_pilot.sh").read_text(
        encoding="utf-8"
    )
    dev_tuning = (
        project_root / "scripts/server/run_image_watermark_dev_tuning.sh"
    ).read_text(encoding="utf-8")
    calibration = (
        project_root / "scripts/server/run_image_watermark_threshold_calibration.sh"
    ).read_text(encoding="utf-8")
    confirmation = (
        project_root
        / "scripts/server/run_image_watermark_channel_vote_confirmation.sh"
    ).read_text(encoding="utf-8")

    assert runner.index(
        'EXPLICIT_BENCHMARK_CONFIG="${BENCHMARK_CONFIG-}"'
    ) < runner.index('source "${SERVER_ENV_FILE}"')
    assert re.search(r"(?m)^\s*(?:export\s+)?SLURM_JOB_ID=", runner) is None
    assert "forbids an inherited or fabricated SLURM_JOB_ID" in runner
    assert "unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG" in runner
    assert "unset COGNIGUARD_WATERMARK_DATASET_MANIFEST" in runner
    assert "unset COGNIGUARD_DATASET_ROOTS_JSON" in runner
    assert "unset COGNIGUARD_PREREGISTRATION_CLAIM_PATH" in runner
    assert "unset COGNIGUARD_PREREGISTRATION_NONCE" in runner
    assert 'RUN_TAG="formal_direct_$(date -u +%Y%m%dT%H%M%SZ)_$$"' in runner
    assert 'BENCHMARK_OUTPUT_DIR="${FORMAL_OUTPUT_ROOT}/${RUN_TAG}"' in runner
    assert "export FORMAL_DIRECT_MODE=1" in runner
    assert "export CHANNEL_VOTE_CONFIRMATION_MODE=0" in runner
    assert "export SPATIAL_FILTER_MODE=0" in runner
    assert "export BENCHMARK_RESUME=0" in runner
    assert 'export SERVER_ENV_FILE=""' in runner
    assert 'export SCE_LOCGUARD_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}"' in runner
    assert (
        'export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD="${TAMPER_AREA_THRESHOLD}"' in runner
    )
    assert (
        'export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN="${LOCALIZATION_CHANNEL_VOTE_MIN}"'
        in runner
    )
    assert "LOCALIZATION_MIN_COMPONENT_AREA_RATIO" in runner
    assert 'export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO=""' in runner
    assert 'exec bash "${SCRIPT_DIR}/image_watermark_benchmark.sbatch"' in runner

    assert 'FORMAL_DIRECT_MODE="${FORMAL_DIRECT_MODE:-0}"' in sbatch
    assert 'EXPLICIT_BENCHMARK_CONFIG="${BENCHMARK_CONFIG-}"' in sbatch
    assert '"${MODE_COUNT}" == "0" && -z "${EXPLICIT_BENCHMARK_CONFIG}"' in sbatch
    assert 'BENCHMARK_CONFIG="${EXPLICIT_BENCHMARK_CONFIG}"' in sbatch
    assert '"${FORMAL_DIRECT_MODE}" == "1" && "${MODE_COUNT}" != "0"' in sbatch
    assert '"${FORMAL_DIRECT_MODE}" == "1" && -n "${SLURM_JOB_ID:-}"' in sbatch
    assert '"${FORMAL_DIRECT_MODE}" == "1" && "${BENCHMARK_RESUME:-0}" != "0"' in sbatch
    assert 'scontrol --oneliner show job "${SLURM_JOB_ID}"' in sbatch
    assert 'EVIDENCE_NUMERIC_UID="${BASH_REMATCH[1]}"' in sbatch
    assert 'EVIDENCE_BATCH_FLAG="${TOKEN#BatchFlag=}"' in sbatch
    assert 'EVIDENCE_BATCH_HOST="${TOKEN#BatchHost=}"' in sbatch
    assert "Slurm batch host does not match the current execution host" in sbatch
    assert 'scontrol pidinfo "$$"' in sbatch
    assert "Current process Slurm allocation differs from SLURM_JOB_ID" in sbatch
    assert "resolve_formal_service_parameters" in sbatch
    assert 'export SCE_LOCGUARD_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}"' in sbatch
    assert (
        'export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD="${TAMPER_AREA_THRESHOLD}"' in sbatch
    )
    assert (
        'export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN="${LOCALIZATION_CHANNEL_VOTE_MIN}"'
        in sbatch
    )
    assert (
        'export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO="${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}"'
        in sbatch
    )
    assert 'export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO=""' in sbatch
    assert "exactly four service parameters" in sbatch
    assert "Refusing to reuse a formal direct run directory" in sbatch
    assert 'mkdir -- "${RUN_DIR}"' in sbatch
    assert "Unable to atomically create a fresh formal direct run directory" in sbatch
    assert 'RUN_SCHEDULER="direct_single_gpu"' in sbatch
    assert '"scheduler=${RUN_SCHEDULER}" > "${RUN_DIR}/scheduler.txt"' in sbatch
    assert "scheduler-slurm-evidence.txt" in sbatch
    assert "scheduler-slurm-pid-evidence.txt" in sbatch
    assert "--validate-required-capabilities" in sbatch
    assert "SCE_LOCGUARD_RUN_INSTANCE_NONCE" in sbatch
    assert "Refusing to start: API port is already occupied" in sbatch
    assert "scripts.server.validate_image_watermark_api_instance" in sbatch
    assert "health-after-capabilities.json" in sbatch
    for script, selected in (
        (pilot, "PILOT_MODE=1"),
        (dev_tuning, "DEV_TUNING_MODE=1"),
        (calibration, "THRESHOLD_CALIBRATION_MODE=1"),
        (confirmation, "CHANNEL_VOTE_CONFIRMATION_MODE=1"),
    ):
        assert selected in script
        for mode in (
            "PILOT_MODE",
            "DEV_TUNING_MODE",
            "THRESHOLD_CALIBRATION_MODE",
            "CHANNEL_VOTE_CONFIRMATION_MODE",
            "FORMAL_DIRECT_MODE",
        ):
            assert mode in script


def test_sbatch_rejects_fabricated_slurm_identifier_before_formal_setup() -> None:
    project_root = Path(__file__).resolve().parents[2]
    command = " ".join(
        (
            "SERVER_ENV_FILE=",
            "SLURM_JOB_ID=fabricated",
            "FORMAL_DIRECT_MODE=0",
            "PILOT_MODE=0",
            "DEV_TUNING_MODE=0",
            "THRESHOLD_CALIBRATION_MODE=0",
            "BENCHMARK_CONFIG=missing-selected.yaml",
            "bash scripts/server/image_watermark_benchmark.sbatch",
        )
    )

    completed = subprocess.run(
        ["bash", "-c", command],
        check=False,
        cwd=project_root,
        capture_output=True,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 2
    assert b"numeric scheduler-issued SLURM_JOB_ID" in output


def test_formal_wrapper_rejects_caller_mode_but_ignores_secure_env_mode() -> None:
    project_root = Path(__file__).resolve().parents[2]
    caller = subprocess.run(
        [
            "bash",
            "-c",
            "BENCHMARK_CONFIG=missing-selected.yaml "
            "CHANNEL_VOTE_CONFIRMATION_MODE=1 SERVER_ENV_FILE= "
            "bash scripts/server/run_image_watermark_formal.sh",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
    )
    assert caller.returncode == 2
    assert b"all development modes to be 0" in caller.stderr

    inherited = subprocess.run(
        [
            "bash",
            "-c",
            "secure_env=$(mktemp); "
            "trap 'rm -f -- \"$secure_env\"' EXIT; "
            "printf '%s\\n' CHANNEL_VOTE_CONFIRMATION_MODE=1 > \"$secure_env\"; "
            "BENCHMARK_CONFIG=missing-selected.yaml SERVER_ENV_FILE=\"$secure_env\" "
            "bash scripts/server/run_image_watermark_formal.sh",
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
    )
    assert inherited.returncode == 2
    assert b"all development modes to be 0" not in inherited.stderr
    assert any(
        marker in inherited.stderr
        for marker in (
            b"Python interpreter is not executable",
            b"Selected formal benchmark config is missing",
        )
    )
