#!/usr/bin/env bash
# Build and run the locked 300-image v3 spatial-filter candidate grid.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
EXPLICIT_FORMAL_CONFIG="${FORMAL_BENCHMARK_CONFIG-}"
EXPLICIT_ASSIGNMENT="${REDEVELOPMENT_ASSIGNMENT-}"
EXPLICIT_ASSIGNMENT_LOCK="${REDEVELOPMENT_ASSIGNMENT_LOCK-}"

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
if [[ -z "${EXPLICIT_FORMAL_CONFIG}" || -z "${EXPLICIT_ASSIGNMENT}" || -z "${EXPLICIT_ASSIGNMENT_LOCK}" ]]; then
  echo "FORMAL_BENCHMARK_CONFIG, REDEVELOPMENT_ASSIGNMENT, and REDEVELOPMENT_ASSIGNMENT_LOCK are required." >&2
  exit 2
fi

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
FORMAL_CONFIG="${EXPLICIT_FORMAL_CONFIG}"
ASSIGNMENT="${EXPLICIT_ASSIGNMENT}"
ASSIGNMENT_LOCK="${EXPLICIT_ASSIGNMENT_LOCK}"
OUTPUT_BASE="${SPATIAL_FILTER_CALIBRATION_OUTPUT_BASE:-${PROJECT_ROOT}/var/outputs/image_watermark_spatial_filter_calibration}"
RUN_TAG="${RUN_TAG:-spatial_filter_calibration_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
BASE_URL="http://${API_HOST}:${API_PORT}"

for variable in FORMAL_CONFIG ASSIGNMENT ASSIGNMENT_LOCK OUTPUT_BASE; do
  value="${!variable}"
  if [[ "${value}" != /* ]]; then
    printf -v "${variable}" '%s' "${PROJECT_ROOT}/${value}"
  fi
done
if [[ ! "${RUN_TAG}" =~ ^spatial_filter_calibration_[A-Za-z0-9._-]+$ ]]; then
  echo "RUN_TAG must begin with spatial_filter_calibration_." >&2
  exit 2
fi
for required_file in "${FORMAL_CONFIG}" "${ASSIGNMENT}" "${ASSIGNMENT_LOCK}"; do
  if [[ ! -f "${required_file}" ]]; then
    echo "Required frozen input is missing: ${required_file}" >&2
    exit 2
  fi
done
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python interpreter is not executable: ${PYTHON_BIN}" >&2
  exit 2
fi

mkdir -p -- "${OUTPUT_BASE}"
RUN_ROOT="${OUTPUT_BASE}/${RUN_TAG}"
if [[ -e "${RUN_ROOT}" ]] || ! mkdir -- "${RUN_ROOT}"; then
  echo "Refusing to reuse spatial-filter calibration root: ${RUN_ROOT}" >&2
  exit 2
fi
CONFIG="${RUN_ROOT}/spatial_filter_calibration.yaml"
MANIFEST="${RUN_ROOT}/spatial_filter_calibration_300.jsonl"
REPORT="${RUN_ROOT}/spatial_filter_selection.json"

cd -- "${PROJECT_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/build_image_watermark_spatial_filter_calibration.py" \
  --source "${FORMAL_CONFIG}" \
  --assignment "${ASSIGNMENT}" \
  --assignment-lock "${ASSIGNMENT_LOCK}" \
  --output "${CONFIG}" \
  --manifest-output "${MANIFEST}" \
  --base-url "${BASE_URL}"

mapfile -t CLAIM_FIELDS < <(
  "${PYTHON_BIN}" - "${CONFIG}" <<'PY'
import sys
from pathlib import Path
import yaml
d = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
c = d["spatial_filter_calibration"]["preregistration_claim"]
print(c["claim_path"])
print(c["nonce"])
for row in d["spatial_filter_calibration"]["candidate_runs"]:
    print(f"{row['candidate_id']}|{row['localization_min_component_area_ratio']}")
PY
)
if [[ "${#CLAIM_FIELDS[@]}" -ne 5 ]]; then
  echo "Calibration preregistration did not emit one claim and three candidates." >&2
  exit 2
fi
CLAIM_PATH="${CLAIM_FIELDS[0]}"
CLAIM_NONCE="${CLAIM_FIELDS[1]}"
if [[ ! -f "${CLAIM_PATH}" || ! "${CLAIM_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Calibration preregistration claim is missing or malformed." >&2
  exit 2
fi
mkdir -- "${RUN_ROOT}/candidate-runs"
FORMAL_SHA="$(sha256sum "${FORMAL_CONFIG}" | awk '{print $1}')"
ASSIGNMENT_SHA="$(sha256sum "${ASSIGNMENT}" | awk '{print $1}')"
ASSIGNMENT_LOCK_SHA="$(sha256sum "${ASSIGNMENT_LOCK}" | awk '{print $1}')"

for candidate_line in "${CLAIM_FIELDS[@]:2}"; do
  IFS='|' read -r CANDIDATE_ID AREA_RATIO <<< "${candidate_line}"
  case "${AREA_RATIO}" in 0.005|0.01|0.02) ;; *) echo "Invalid candidate ${candidate_line}" >&2; exit 2 ;; esac
  CANDIDATE_DIR="${RUN_ROOT}/candidate-runs/${CANDIDATE_ID}"
  echo "Running v3 spatial-filter candidate ${CANDIDATE_ID} (${AREA_RATIO})"
  SERVER_ENV_FILE="" \
  PYTHON_BIN="${PYTHON_BIN}" \
  WATERMARK_API_HOST="${API_HOST}" \
  WATERMARK_API_PORT="${API_PORT}" \
  SCE_LOCGUARD_BASE_URL="${BASE_URL}" \
  PILOT_MODE=0 \
  DEV_TUNING_MODE=0 \
  THRESHOLD_CALIBRATION_MODE=0 \
  CHANNEL_VOTE_CONFIRMATION_MODE=0 \
  SPATIAL_FILTER_MODE=1 \
  FORMAL_DIRECT_MODE=0 \
  SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34 \
  SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001 \
  SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1 \
  SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO="${AREA_RATIO}" \
  BENCHMARK_RESUME=0 \
  COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${CLAIM_PATH}" \
  COGNIGUARD_PREREGISTRATION_NONCE="${CLAIM_NONCE}" \
  BENCHMARK_CONFIG="${CONFIG}" \
  BENCHMARK_OUTPUT_DIR="${CANDIDATE_DIR}" \
  RUN_TAG="${RUN_TAG}_${CANDIDATE_ID}" \
  SPATIAL_FILTER_MIN_DATASET_SAMPLES=300 \
  SPATIAL_FILTER_MIN_SELECTED_SAMPLES=300 \
  SPATIAL_FILTER_MIN_SOURCE_DATASETS=4 \
  SPATIAL_FILTER_MIN_CONTENT_DOMAINS=34 \
  bash "${PROJECT_ROOT}/scripts/server/image_watermark_benchmark.sbatch"

  [[ "$(sha256sum "${FORMAL_CONFIG}" | awk '{print $1}')" == "${FORMAL_SHA}" ]] || { echo "Formal config changed." >&2; exit 2; }
  [[ "$(sha256sum "${ASSIGNMENT}" | awk '{print $1}')" == "${ASSIGNMENT_SHA}" ]] || { echo "Assignment changed." >&2; exit 2; }
  [[ "$(sha256sum "${ASSIGNMENT_LOCK}" | awk '{print $1}')" == "${ASSIGNMENT_LOCK_SHA}" ]] || { echo "Assignment lock changed." >&2; exit 2; }
done

set +e
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/analyze_image_watermark_spatial_filter.py" \
  --config "${CONFIG}" \
  --run-root "${RUN_ROOT}" \
  --output "${REPORT}"
STATUS=$?
set -e
echo "Spatial-filter calibration report: ${REPORT}"
exit "${STATUS}"
