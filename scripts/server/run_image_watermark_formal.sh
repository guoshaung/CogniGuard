#!/usr/bin/env bash
# Run one immutable formal benchmark directly on a single-GPU server.
# Usage:
#   BENCHMARK_CONFIG=/abs/path/paper_benchmark_selected_v1.yaml \
#   SERVER_ENV_FILE=/abs/path/watermark.env \
#   bash scripts/server/run_image_watermark_formal.sh

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

# Capture the caller's selected config before the secure environment is sourced.
# A machine-level default is never accepted as an implicit formal selection.
EXPLICIT_BENCHMARK_CONFIG="${BENCHMARK_CONFIG-}"
CALLER_SLURM_JOB_ID="${SLURM_JOB_ID:-}"
CALLER_PILOT_MODE="${PILOT_MODE:-0}"
CALLER_DEV_TUNING_MODE="${DEV_TUNING_MODE:-0}"
CALLER_THRESHOLD_CALIBRATION_MODE="${THRESHOLD_CALIBRATION_MODE:-0}"
CALLER_CHANNEL_VOTE_CONFIRMATION_MODE="${CHANNEL_VOTE_CONFIRMATION_MODE:-0}"
CALLER_SPATIAL_FILTER_MODE="${SPATIAL_FILTER_MODE:-0}"
CALLER_BENCHMARK_RESUME="${BENCHMARK_RESUME:-0}"

for MODE_VALUE in \
  "${CALLER_PILOT_MODE}" \
  "${CALLER_DEV_TUNING_MODE}" \
  "${CALLER_THRESHOLD_CALIBRATION_MODE}" \
  "${CALLER_CHANNEL_VOTE_CONFIRMATION_MODE}" \
  "${CALLER_SPATIAL_FILTER_MODE}"; do
  if [[ "${MODE_VALUE}" != "0" ]]; then
    echo "Direct formal execution requires all development modes to be 0." >&2
    exit 2
  fi
done
if [[ -n "${CALLER_SLURM_JOB_ID}" ]]; then
  echo "Direct formal execution forbids an inherited or fabricated SLURM_JOB_ID." >&2
  exit 2
fi
if [[ "${CALLER_BENCHMARK_RESUME}" != "0" ]]; then
  echo "Direct formal execution requires BENCHMARK_RESUME=0." >&2
  exit 2
fi

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

if [[ -z "${EXPLICIT_BENCHMARK_CONFIG}" ]]; then
  echo "BENCHMARK_CONFIG must explicitly name the frozen selected formal YAML." >&2
  exit 2
fi
if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "Direct formal execution forbids an inherited or fabricated SLURM_JOB_ID." >&2
  exit 2
fi
# Caller-selected development modes were rejected before sourcing the secure
# environment. Machine-level mode defaults are not experiment selections and
# are overwritten by the complete formal mode vector below.
if [[ "${BENCHMARK_RESUME:-0}" != "0" ]]; then
  echo "Direct formal execution requires BENCHMARK_RESUME=0." >&2
  exit 2
fi

# The explicit selected YAML is authoritative after secrets are loaded. Ignore
# stale machine-level benchmark, manifest, and dataset-root overrides.
unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
unset COGNIGUARD_DATASET_ROOTS_JSON
unset COGNIGUARD_PREREGISTRATION_CLAIM_PATH
unset COGNIGUARD_PREREGISTRATION_NONCE

PROJECT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
PROJECT_ROOT="$(cd -- "${PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${PROJECT_ROOT}/var/cache/python}"
export SCE_LOCGUARD_PROJECT_ROOT="${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/.venv-server/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python interpreter is not executable: ${PYTHON_BIN}" >&2
  exit 2
fi

BENCHMARK_CONFIG="${EXPLICIT_BENCHMARK_CONFIG}"
if [[ "${BENCHMARK_CONFIG}" != /* ]]; then
  BENCHMARK_CONFIG="${PROJECT_ROOT}/${BENCHMARK_CONFIG}"
fi
if [[ ! -f "${BENCHMARK_CONFIG}" ]]; then
  echo "Selected formal benchmark config is missing: ${BENCHMARK_CONFIG}" >&2
  exit 2
fi

FORMAL_OUTPUT_ROOT="${FORMAL_OUTPUT_ROOT:-${PROJECT_ROOT}/var/outputs/image_watermark_paper}"
if [[ "${FORMAL_OUTPUT_ROOT}" != /* ]]; then
  FORMAL_OUTPUT_ROOT="${PROJECT_ROOT}/${FORMAL_OUTPUT_ROOT}"
fi
mkdir -p -- "${FORMAL_OUTPUT_ROOT}"
FORMAL_OUTPUT_ROOT="$(cd -- "${FORMAL_OUTPUT_ROOT}" && pwd)"

# Do not accept caller- or secure-env-provided run names/output directories.
# Every formal direct run gets a new identity and an as-yet nonexistent target.
RUN_TAG="formal_direct_$(date -u +%Y%m%dT%H%M%SZ)_$$"
BENCHMARK_OUTPUT_DIR="${FORMAL_OUTPUT_ROOT}/${RUN_TAG}"
if [[ -e "${BENCHMARK_OUTPUT_DIR}" ]]; then
  echo "Refusing to reuse a formal output directory: ${BENCHMARK_OUTPUT_DIR}" >&2
  exit 2
fi

FORMAL_SERVICE_PARAMETERS="$(
  "${PYTHON_BIN}" -c \
    'import sys; from protection.supporting.image_watermark.experiments.paper_benchmark import resolve_formal_service_parameters; p=resolve_formal_service_parameters(sys.argv[1]); print(f"{p['"'"'recovery_threshold'"'"']!r}\t{p['"'"'tamper_area_threshold'"'"']!r}\t{p['"'"'localization_channel_vote_min'"'"']}\t{p.get('"'"'localization_min_component_area_ratio'"'"', 0.0)!r}")' \
    "${BENCHMARK_CONFIG}"
)"
IFS=$'\t' read -r RECOVERY_THRESHOLD TAMPER_AREA_THRESHOLD LOCALIZATION_CHANNEL_VOTE_MIN LOCALIZATION_MIN_COMPONENT_AREA_RATIO EXTRA_FIELD <<< "${FORMAL_SERVICE_PARAMETERS}"
if [[ -z "${RECOVERY_THRESHOLD}" || -z "${TAMPER_AREA_THRESHOLD}" || ! "${LOCALIZATION_CHANNEL_VOTE_MIN}" =~ ^[1-3]$ || -z "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" || -n "${EXTRA_FIELD:-}" ]]; then
  echo "Selected formal config did not resolve exactly four service parameters." >&2
  exit 2
fi
case "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" in
  0|0.0|0.005|0.01|0.02) ;;
  *) echo "Selected formal component-area ratio is invalid." >&2; exit 2 ;;
esac

export PILOT_MODE=0
export DEV_TUNING_MODE=0
export THRESHOLD_CALIBRATION_MODE=0
export CHANNEL_VOTE_CONFIRMATION_MODE=0
export SPATIAL_FILTER_MODE=0
export FORMAL_DIRECT_MODE=1
export BENCHMARK_RESUME=0
export BENCHMARK_CONFIG
export BENCHMARK_OUTPUT_DIR
export RUN_TAG
export SCE_LOCGUARD_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}"
export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD="${TAMPER_AREA_THRESHOLD}"
export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN="${LOCALIZATION_CHANNEL_VOTE_MIN}"
if [[ "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" == "0" || "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" == "0.0" ]]; then
  # Explicitly clear an inherited v3 value while preserving the v2 default-zero
  # service contract; the service rejects an explicit numeric zero.
  export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO=""
else
  export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO="${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}"
fi
# The secure environment has already been sourced. Prevent the shared runner or
# API launcher from sourcing it again and undoing the selected-config bindings.
export SERVER_ENV_FILE=""

echo "Starting ${RUN_TAG} with scheduler=direct_single_gpu and frozen config ${BENCHMARK_CONFIG}."
echo "RUN_DIR=${BENCHMARK_OUTPUT_DIR}"
exec bash "${SCRIPT_DIR}/image_watermark_benchmark.sbatch"
