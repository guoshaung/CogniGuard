#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_ROOT="${COGNIGUARD_PROJECT_ROOT:-${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}}"
PROJECT_ROOT="$(cd -- "${PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${PROJECT_ROOT}/var/cache/python}"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/.venv-server/bin/python}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python executable is unavailable: ${PYTHON_BIN}" >&2
  exit 2
fi

DATASET_ROOT="${COGNIGUARD_MATH_DATASET_ROOT:-${PROJECT_ROOT}/experiments/datasets/cogniguard_math_suite}"
MIXED_ROOT="${DATASET_ROOT}/mixed_math_suite"
STUDENT_ROOT="${MIXED_ROOT}/student_profile/data"
TEACHER_ROOT="${MIXED_ROOT}/teacher_resource/data"
CONFIG="${COGNIGUARD_SYSTEM_CONFIG:-${PROJECT_ROOT}/protection/student_profile/configs/default.yaml}"
OUTPUT_ROOT="${SYSTEM_VALIDATION_OUTPUT_ROOT:-${PROJECT_ROOT}/var/outputs/system_validation}"
SAMPLES="${SYSTEM_VALIDATION_SAMPLES:-64}"
BOOTSTRAP_ITERATIONS="${SYSTEM_VALIDATION_BOOTSTRAP_ITERATIONS:-1000}"

for value in "${SAMPLES}" "${BOOTSTRAP_ITERATIONS}"; do
  if [[ ! "${value}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Sampling controls must be positive integers: ${value}" >&2
    exit 2
  fi
done

for required in \
  "${DATASET_ROOT}/manifest.json" \
  "${STUDENT_ROOT}/profiles.jsonl" \
  "${STUDENT_ROOT}/student_questions.jsonl" \
  "${TEACHER_ROOT}/teacher_resources.jsonl" \
  "${CONFIG}"; do
  if [[ ! -f "${required}" ]]; then
    echo "Required validation input is missing: ${required}" >&2
    exit 2
  fi
done

mkdir -p -- "${OUTPUT_ROOT}"
OUTPUT_ROOT="$(cd -- "${OUTPUT_ROOT}" && pwd)"
RUN_TAG="system_validation_$(date -u +%Y%m%dT%H%M%SZ)_$$"
RUN_DIR="${OUTPUT_ROOT}/${RUN_TAG}"
if [[ -e "${RUN_DIR}" ]]; then
  echo "Refusing to reuse validation directory: ${RUN_DIR}" >&2
  exit 2
fi
mkdir -p -- "${RUN_DIR}/stages"

export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [[ ! "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export OMP_NUM_THREADS=8
fi
if [[ ! "${MKL_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export MKL_NUM_THREADS=8
fi
export TOKENIZERS_PARALLELISM="false"
# The integrated demo is a deterministic system-wiring check.  It must not
# silently download a large encoder or call an external LLM during validation.
export COGNIGUARD_RUNTIME_MODE="${COGNIGUARD_RUNTIME_MODE:-mock}"
export COGNIGUARD_PROFILE_ENCODER_BACKEND="${COGNIGUARD_PROFILE_ENCODER_BACKEND:-fallback}"

printf '%s\n' "development_validation_not_for_automatic_paper_claims" > "${RUN_DIR}/run_class.txt"
cp -- "${DATASET_ROOT}/manifest.json" "${RUN_DIR}/dataset_manifest.json"
cp -- "${CONFIG}" "${RUN_DIR}/system_config.yaml"
(
  cd -- "${PROJECT_ROOT}"
  git rev-parse HEAD 2>/dev/null || printf '%s\n' unavailable
) > "${RUN_DIR}/git_head.txt"
(
  cd -- "${PROJECT_ROOT}"
  git status --porcelain=v1 2>/dev/null || true
) > "${RUN_DIR}/git_status.txt"
"${PYTHON_BIN}" -m pip freeze > "${RUN_DIR}/pip_freeze.txt" 2>&1 || true
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader \
  > "${RUN_DIR}/gpu.txt" 2>&1 || true

STAGE_TABLE="${RUN_DIR}/stages.tsv"
printf 'stage\tstarted_utc\tended_utc\tduration_seconds\texit_code\tlog\n' > "${STAGE_TABLE}"
overall_rc=0

run_stage() {
  local stage="$1"
  shift
  local log="${RUN_DIR}/stages/${stage}.log"
  local started ended start_epoch end_epoch rc
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  start_epoch="$(date +%s)"
  printf '[%s] START %s\n' "${started}" "${stage}"
  (
    cd -- "${PROJECT_ROOT}"
    "$@"
  ) > "${log}" 2>&1
  rc=$?
  ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  end_epoch="$(date +%s)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "${stage}" "${started}" "${ended}" "$((end_epoch - start_epoch))" "${rc}" "${log}" \
    >> "${STAGE_TABLE}"
  printf '[%s] END %s rc=%s duration=%ss\n' \
    "${ended}" "${stage}" "${rc}" "$((end_epoch - start_epoch))"
  tail -n 20 -- "${log}" || true
  if (( rc != 0 )); then
    overall_rc=1
  fi
}

run_stage dataset_integrity \
  "${PYTHON_BIN}" -m experiments.dataset_builders.validate_math_dataset "${DATASET_ROOT}"

run_stage pytest_full \
  "${PYTHON_BIN}" -m pytest -q

run_stage end_to_end_demo \
  "${PYTHON_BIN}" -m cogniguard.demo.run_demo --case-index 0

run_stage baseline_comparisons \
  "${PYTHON_BIN}" -m experiments.baselines.run_baseline_comparisons \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/baseline_comparisons" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}"

run_stage protection_ablations \
  "${PYTHON_BIN}" -m experiments.ablation.run_protection_ablations \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/protection_ablations" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}"

run_stage joint_synergy \
  "${PYTHON_BIN}" -m experiments.evaluation.eval_joint_synergy \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/joint_synergy" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}"

run_stage feedback_loops \
  "${PYTHON_BIN}" -m experiments.evaluation.eval_feedback_loops \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/feedback_loops" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}"

run_stage cross_layer_synergy \
  "${PYTHON_BIN}" -m experiments.evaluation.eval_cross_layer_synergy \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/cross_layer_synergy" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}"

run_stage episode_attacks \
  "${PYTHON_BIN}" -m experiments.attacks.episode_attack_runner \
  --dataset-root "${MIXED_ROOT}" \
  --output "${RUN_DIR}/episode_attacks.json" \
  --seed 2026

run_stage joint_synergy_sampling \
  "${PYTHON_BIN}" -m experiments.evaluation.eval_joint_synergy_sampling \
  --config "${CONFIG}" \
  --results-root "${RUN_DIR}/joint_synergy_sampling" \
  --student-data-root "${STUDENT_ROOT}" \
  --teacher-data-root "${TEACHER_ROOT}" \
  --samples "${SAMPLES}" \
  --bootstrap-iterations "${BOOTSTRAP_ITERATIONS}" \
  --seed 2026

"${PYTHON_BIN}" - "${RUN_DIR}" "${overall_rc}" <<'PY'
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

run_dir = Path(sys.argv[1])
overall_rc = int(sys.argv[2])
with (run_dir / "stages.tsv").open(encoding="utf-8", newline="") as handle:
    stages = list(csv.DictReader(handle, delimiter="\t"))
for row in stages:
    row["duration_seconds"] = int(row["duration_seconds"])
    row["exit_code"] = int(row["exit_code"])
summary = {
    "schema_version": "cogniguard.system-validation.v1",
    "run_class": "development_validation_not_for_automatic_paper_claims",
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "success": overall_rc == 0,
    "stage_count": len(stages),
    "failed_stages": [row["stage"] for row in stages if row["exit_code"] != 0],
    "stages": stages,
}
temporary = run_dir / "summary.json.tmp"
temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
temporary.replace(run_dir / "summary.json")
PY

printf '%s\n' "${overall_rc}" > "${RUN_DIR}/exit_code"
printf 'Validation artifacts: %s\n' "${RUN_DIR}"
exit "${overall_rc}"
