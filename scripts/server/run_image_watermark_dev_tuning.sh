#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

if [[ -n "${SERVER_ENV_FILE:-}" ]]; then
  if [[ ! -r "${SERVER_ENV_FILE}" ]]; then
    echo "SERVER_ENV_FILE is not readable: ${SERVER_ENV_FILE}" >&2
    exit 2
  fi
  set -a
  # shellcheck disable=SC1090
  source "${SERVER_ENV_FILE}"
  set +a
fi

export SCE_LOCGUARD_PROJECT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
export SCE_LOCGUARD_PROJECT_ROOT="$(cd -- "${SCE_LOCGUARD_PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${SCE_LOCGUARD_PROJECT_ROOT}/var/cache/python}"
PYTHON_BIN="${PYTHON_BIN:-${SCE_LOCGUARD_PROJECT_ROOT}/.venv-server/bin/python}"
FORMAL_CONFIG="${DEV_TUNING_SOURCE_CONFIG:-${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG:-${SCE_LOCGUARD_PROJECT_ROOT}/protection/supporting/image_watermark/configs/paper_benchmark.yaml}}"
if [[ "${FORMAL_CONFIG}" != /* ]]; then
  FORMAL_CONFIG="${SCE_LOCGUARD_PROJECT_ROOT}/${FORMAL_CONFIG}"
fi

DEV_TUNING_OUTPUT_ROOT="${DEV_TUNING_OUTPUT_ROOT:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/image_watermark_dev_tuning}"
if [[ "${DEV_TUNING_OUTPUT_ROOT}" != /* ]]; then
  DEV_TUNING_OUTPUT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT}/${DEV_TUNING_OUTPUT_ROOT}"
fi
mkdir -p -- "${DEV_TUNING_OUTPUT_ROOT}"
DEV_TUNING_OUTPUT_ROOT="$(cd -- "${DEV_TUNING_OUTPUT_ROOT}" && pwd)"

DEV_TUNING_ATTACK_PROFILE="${DEV_TUNING_ATTACK_PROFILE:-baseline}"
case "${DEV_TUNING_ATTACK_PROFILE}" in
  baseline)
    DEV_TUNING_CONDITION_COUNT=4
    DEV_TUNING_EXPECTED_ROWS=468
    ;;
  selection-grid)
    DEV_TUNING_CONDITION_COUNT=7
    DEV_TUNING_EXPECTED_ROWS=819
    ;;
  *)
    echo "DEV_TUNING_ATTACK_PROFILE must be baseline or selection-grid." >&2
    exit 2
    ;;
esac

RUN_TAG="${RUN_TAG:-dev_tuning_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
if [[ ! "${RUN_TAG}" =~ ^dev_tuning_[A-Za-z0-9_.-]+$ ]]; then
  echo "RUN_TAG must begin with dev_tuning_ and contain only safe characters." >&2
  exit 2
fi
RUN_DIR="${DEV_TUNING_OUTPUT_ROOT}/${RUN_TAG}"
if [[ -e "${RUN_DIR}" ]]; then
  echo "Refusing to reuse an existing dev-tuning run directory: ${RUN_DIR}" >&2
  exit 2
fi
mkdir -p -- "${RUN_DIR}"

DEV_CONFIG="${RUN_DIR}/dev_tuning_benchmark.yaml"
DEV_MANIFEST="${RUN_DIR}/synthetic_dev_117.jsonl"
BUILD_ARGS=(
  --source "${FORMAL_CONFIG}"
  --output "${DEV_CONFIG}"
  --manifest-output "${DEV_MANIFEST}"
  --expected-samples 117
  --seed 20260802
  --attack-profile "${DEV_TUNING_ATTACK_PROFILE}"
)
SOURCE_MANIFEST_OVERRIDE="${COGNIGUARD_WATERMARK_DATASET_MANIFEST:-}"
if [[ -n "${SOURCE_MANIFEST_OVERRIDE}" ]]; then
  BUILD_ARGS+=(--source-manifest "${SOURCE_MANIFEST_OVERRIDE}")
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/build_image_watermark_dev_tuning_config.py" "${BUILD_ARGS[@]}"

# The source-manifest override is only an input to the bundle builder. Leaving
# it exported would override the run-local dev-only manifest in both preflight
# and the benchmark runner.
unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
export SERVER_ENV_FILE=""

export DEV_TUNING_MODE=1
export PILOT_MODE=0
export THRESHOLD_CALIBRATION_MODE=0
export CHANNEL_VOTE_CONFIRMATION_MODE=0
export FORMAL_DIRECT_MODE=0
export RUN_TAG
export BENCHMARK_OUTPUT_DIR="${RUN_DIR}"
export BENCHMARK_CONFIG="${DEV_CONFIG}"
export DEV_TUNING_MIN_DATASET_SAMPLES=117
export DEV_TUNING_MIN_SELECTED_SAMPLES=117
export DEV_TUNING_MIN_SOURCE_DATASETS=1
export DEV_TUNING_MIN_CONTENT_DOMAINS=9

printf '%s\n' "dev_tuning" > "${RUN_DIR}/requested-run-class.txt"
printf '%s\n' "${DEV_TUNING_ATTACK_PROFILE}" > "${RUN_DIR}/requested-attack-profile.txt"
printf '%s\n' "${RUN_DIR}" > "${DEV_TUNING_OUTPUT_ROOT}/latest-requested-run.txt"
echo "Starting ${RUN_TAG}: synthetic dev only, 117 samples, 1 seed, ${DEV_TUNING_CONDITION_COUNT} non-AIGC conditions (${DEV_TUNING_ATTACK_PROFILE}, ${DEV_TUNING_EXPECTED_ROWS} rows)."
echo "RUN_DIR=${RUN_DIR}"
exec bash "${SCRIPT_DIR}/image_watermark_benchmark.sbatch"
