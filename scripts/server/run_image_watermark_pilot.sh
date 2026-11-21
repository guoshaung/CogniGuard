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
FORMAL_CONFIG="${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG:-${SCE_LOCGUARD_PROJECT_ROOT}/protection/supporting/image_watermark/configs/paper_benchmark.yaml}"
if [[ "${FORMAL_CONFIG}" != /* ]]; then
  FORMAL_CONFIG="${SCE_LOCGUARD_PROJECT_ROOT}/${FORMAL_CONFIG}"
fi

PILOT_MAX_SAMPLES="${PILOT_MAX_SAMPLES:-8}"
if [[ ! "${PILOT_MAX_SAMPLES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "PILOT_MAX_SAMPLES must be a positive integer." >&2
  exit 2
fi

PILOT_OUTPUT_ROOT="${PILOT_OUTPUT_ROOT:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/image_watermark_pilot}"
if [[ "${PILOT_OUTPUT_ROOT}" != /* ]]; then
  PILOT_OUTPUT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT}/${PILOT_OUTPUT_ROOT}"
fi
mkdir -p -- "${PILOT_OUTPUT_ROOT}"
PILOT_OUTPUT_ROOT="$(cd -- "${PILOT_OUTPUT_ROOT}" && pwd)"

RUN_TAG="pilot_$(date -u +%Y%m%dT%H%M%SZ)_$$"
RUN_DIR="${PILOT_OUTPUT_ROOT}/${RUN_TAG}"
if [[ -e "${RUN_DIR}" ]]; then
  echo "Refusing to reuse an existing pilot run directory: ${RUN_DIR}" >&2
  exit 2
fi
mkdir -p -- "${RUN_DIR}"

PILOT_CONFIG="${RUN_DIR}/pilot_benchmark.yaml"
PILOT_CONFIG_ARGS=(
  --source "${FORMAL_CONFIG}"
  --output "${PILOT_CONFIG}"
  --max-samples "${PILOT_MAX_SAMPLES}"
)
if [[ -n "${PILOT_SEED:-}" ]]; then
  PILOT_CONFIG_ARGS+=(--seed "${PILOT_SEED}")
fi
"${PYTHON_BIN}" "${SCRIPT_DIR}/build_image_watermark_pilot_config.py" "${PILOT_CONFIG_ARGS[@]}"

export PILOT_MODE=1
export DEV_TUNING_MODE=0
export THRESHOLD_CALIBRATION_MODE=0
export CHANNEL_VOTE_CONFIRMATION_MODE=0
export FORMAL_DIRECT_MODE=0
export RUN_TAG
export BENCHMARK_OUTPUT_DIR="${RUN_DIR}"
export BENCHMARK_CONFIG="${PILOT_CONFIG}"

echo "Starting direct pilot ${RUN_TAG}; results are explicitly not paper-eligible."
exec bash "${SCRIPT_DIR}/image_watermark_benchmark.sbatch"
