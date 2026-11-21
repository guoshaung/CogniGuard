#!/usr/bin/env bash
# Build and run the sole locked 600-image v3 spatial-filter confirmation.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
EXPLICIT_FORMAL_CONFIG="${FORMAL_BENCHMARK_CONFIG-}"
EXPLICIT_ASSIGNMENT="${REDEVELOPMENT_ASSIGNMENT-}"
EXPLICIT_ASSIGNMENT_LOCK="${REDEVELOPMENT_ASSIGNMENT_LOCK-}"
EXPLICIT_CALIBRATION_RUN_ROOT="${SPATIAL_FILTER_CALIBRATION_RUN_ROOT-}"

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
if [[ -z "${EXPLICIT_FORMAL_CONFIG}" || -z "${EXPLICIT_ASSIGNMENT}" || -z "${EXPLICIT_ASSIGNMENT_LOCK}" || -z "${EXPLICIT_CALIBRATION_RUN_ROOT}" ]]; then
  echo "FORMAL_BENCHMARK_CONFIG, REDEVELOPMENT_ASSIGNMENT, REDEVELOPMENT_ASSIGNMENT_LOCK, and SPATIAL_FILTER_CALIBRATION_RUN_ROOT are required." >&2
  exit 2
fi
if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "Spatial-filter confirmation forbids inherited or fabricated SLURM_JOB_ID." >&2
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
CALIBRATION_RUN_ROOT="${EXPLICIT_CALIBRATION_RUN_ROOT}"
OUTPUT_BASE="${SPATIAL_FILTER_CONFIRMATION_OUTPUT_BASE:-${PROJECT_ROOT}/var/outputs/image_watermark_spatial_filter_confirmation}"
RUN_TAG="${RUN_TAG:-spatial_filter_confirmation_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
BASE_URL="http://${API_HOST}:${API_PORT}"

for variable in FORMAL_CONFIG ASSIGNMENT ASSIGNMENT_LOCK CALIBRATION_RUN_ROOT OUTPUT_BASE; do
  value="${!variable}"
  if [[ "${value}" != /* ]]; then
    printf -v "${variable}" '%s' "${PROJECT_ROOT}/${value}"
  fi
done
if [[ ! "${RUN_TAG}" =~ ^spatial_filter_confirmation_[A-Za-z0-9._-]+$ ]]; then
  echo "RUN_TAG must begin with spatial_filter_confirmation_." >&2
  exit 2
fi
for required_file in "${FORMAL_CONFIG}" "${ASSIGNMENT}" "${ASSIGNMENT_LOCK}"; do
  if [[ ! -f "${required_file}" ]]; then
    echo "Required frozen input is missing: ${required_file}" >&2
    exit 2
  fi
done
if [[ ! -d "${CALIBRATION_RUN_ROOT}" ]]; then
  echo "Calibration run root is missing: ${CALIBRATION_RUN_ROOT}" >&2
  exit 2
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python interpreter is not executable: ${PYTHON_BIN}" >&2
  exit 2
fi

mapfile -t CALIBRATION_INPUTS < <(
  "${PYTHON_BIN}" - "${CALIBRATION_RUN_ROOT}" "${FORMAL_CONFIG}" "${ASSIGNMENT}" "${ASSIGNMENT_LOCK}" <<'PY'
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]).resolve()
formal = Path(sys.argv[2]).resolve()
assignment = Path(sys.argv[3]).resolve()
assignment_lock = Path(sys.argv[4]).resolve()
config = root / "spatial_filter_calibration.yaml"
report = root / "spatial_filter_selection.json"
if not config.is_file() or not report.is_file():
    raise SystemExit(
        "Calibration root must contain spatial_filter_calibration.yaml and "
        "spatial_filter_selection.json."
    )
payload = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
if not isinstance(payload, dict):
    raise SystemExit("Spatial-filter calibration YAML root is not a mapping.")
contract = payload.get("spatial_filter_calibration") or {}
manifest = Path(str((payload.get("manifest") or {}).get("path") or "")).resolve()
if manifest.parent != root or not manifest.is_file():
    raise SystemExit("Calibration manifest is missing or escapes the supplied root.")
if (
    Path(str(contract.get("source_formal_config") or "")).resolve() != formal
    or Path(str(contract.get("redevelopment_assignment") or "")).resolve()
    != assignment
    or Path(str(contract.get("redevelopment_assignment_lock") or "")).resolve()
    != assignment_lock
):
    raise SystemExit("Calibration root is not bound to the explicit frozen inputs.")
selection = json.loads(report.read_text(encoding="utf-8"))
if (
    not isinstance(selection, dict)
    or selection.get("status") != "winner_selected"
    or selection.get("calibration_passed") is not True
    or not isinstance(selection.get("selected_candidate"), dict)
):
    raise SystemExit("Calibration did not produce an eligible sole winner.")
print(config)
print(manifest)
print(report)
PY
)
if [[ "${#CALIBRATION_INPUTS[@]}" -ne 3 ]]; then
  echo "Unable to resolve exactly three frozen calibration inputs." >&2
  exit 2
fi
CALIBRATION_CONFIG="${CALIBRATION_INPUTS[0]}"
CALIBRATION_MANIFEST="${CALIBRATION_INPUTS[1]}"
CALIBRATION_REPORT="${CALIBRATION_INPUTS[2]}"

mkdir -p -- "${OUTPUT_BASE}"
RUN_ROOT="${OUTPUT_BASE}/${RUN_TAG}"
if [[ -e "${RUN_ROOT}" ]] || ! mkdir -- "${RUN_ROOT}"; then
  echo "Refusing to reuse spatial-filter confirmation root: ${RUN_ROOT}" >&2
  exit 2
fi
CONFIG="${RUN_ROOT}/spatial_filter_confirmation.yaml"
MANIFEST="${RUN_ROOT}/spatial_filter_confirmation_600.jsonl"
REPORT="${RUN_ROOT}/spatial_filter_confirmation_report.json"

cd -- "${PROJECT_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/build_image_watermark_spatial_filter_confirmation.py" \
  --source "${FORMAL_CONFIG}" \
  --assignment "${ASSIGNMENT}" \
  --assignment-lock "${ASSIGNMENT_LOCK}" \
  --calibration-config "${CALIBRATION_CONFIG}" \
  --calibration-manifest "${CALIBRATION_MANIFEST}" \
  --calibration-run-root "${CALIBRATION_RUN_ROOT}" \
  --calibration-report "${CALIBRATION_REPORT}" \
  --output "${CONFIG}" \
  --manifest-output "${MANIFEST}" \
  --base-url "${BASE_URL}"

mapfile -t CLAIM_FIELDS < <(
  "${PYTHON_BIN}" - "${CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1]).resolve()
payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
contract = payload["spatial_filter_confirmation"]
claim = contract["preregistration_claim"]
candidate = contract["selected_candidate"]
print(claim["claim_path"])
print(claim["nonce"])
print(candidate["candidate_id"])
print(candidate["localization_min_component_area_ratio"])
print(payload["experiment"]["output_root"])
PY
)
if [[ "${#CLAIM_FIELDS[@]}" -ne 5 ]]; then
  echo "Confirmation preregistration did not emit one sole candidate." >&2
  exit 2
fi
CLAIM_PATH="${CLAIM_FIELDS[0]}"
CLAIM_NONCE="${CLAIM_FIELDS[1]}"
CANDIDATE_ID="${CLAIM_FIELDS[2]}"
AREA_RATIO="${CLAIM_FIELDS[3]}"
CANDIDATE_DIR="${CLAIM_FIELDS[4]}"
if [[ ! -f "${CLAIM_PATH}" || ! "${CLAIM_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Confirmation preregistration claim is missing or malformed." >&2
  exit 2
fi
case "${AREA_RATIO}" in
  0.005|0.01|0.02) ;;
  *) echo "Invalid sole confirmation candidate ratio: ${AREA_RATIO}" >&2; exit 2 ;;
esac
if [[ "${CANDIDATE_DIR}" != "${RUN_ROOT}/confirmation-run/${CANDIDATE_ID}" ]]; then
  echo "Confirmation candidate output is not the sole preregistered path." >&2
  exit 2
fi
if [[ -e "${CANDIDATE_DIR}" ]] || ! mkdir -- "${RUN_ROOT}/confirmation-run"; then
  echo "Confirmation candidate artifacts predate preregistration." >&2
  exit 2
fi

FORMAL_SHA="$(sha256sum "${FORMAL_CONFIG}" | awk '{print $1}')"
ASSIGNMENT_SHA="$(sha256sum "${ASSIGNMENT}" | awk '{print $1}')"
ASSIGNMENT_LOCK_SHA="$(sha256sum "${ASSIGNMENT_LOCK}" | awk '{print $1}')"
CALIBRATION_CONFIG_SHA="$(sha256sum "${CALIBRATION_CONFIG}" | awk '{print $1}')"
CALIBRATION_MANIFEST_SHA="$(sha256sum "${CALIBRATION_MANIFEST}" | awk '{print $1}')"
CALIBRATION_MANIFEST_LOCK="${CALIBRATION_MANIFEST}.lock.json"
if [[ ! -f "${CALIBRATION_MANIFEST_LOCK}" ]]; then
  echo "Calibration manifest lock is missing: ${CALIBRATION_MANIFEST_LOCK}" >&2
  exit 2
fi
CALIBRATION_MANIFEST_LOCK_SHA="$(sha256sum "${CALIBRATION_MANIFEST_LOCK}" | awk '{print $1}')"
CALIBRATION_REPORT_SHA="$(sha256sum "${CALIBRATION_REPORT}" | awk '{print $1}')"

echo "Running sole v3 spatial-filter confirmation ${CANDIDATE_ID} (${AREA_RATIO})"
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
SPATIAL_FILTER_MIN_DATASET_SAMPLES=600 \
SPATIAL_FILTER_MIN_SELECTED_SAMPLES=600 \
SPATIAL_FILTER_MIN_SOURCE_DATASETS=4 \
SPATIAL_FILTER_MIN_CONTENT_DOMAINS=34 \
bash "${PROJECT_ROOT}/scripts/server/image_watermark_benchmark.sbatch"

[[ "$(sha256sum "${FORMAL_CONFIG}" | awk '{print $1}')" == "${FORMAL_SHA}" ]] || { echo "Formal config changed." >&2; exit 2; }
[[ "$(sha256sum "${ASSIGNMENT}" | awk '{print $1}')" == "${ASSIGNMENT_SHA}" ]] || { echo "Assignment changed." >&2; exit 2; }
[[ "$(sha256sum "${ASSIGNMENT_LOCK}" | awk '{print $1}')" == "${ASSIGNMENT_LOCK_SHA}" ]] || { echo "Assignment lock changed." >&2; exit 2; }
[[ "$(sha256sum "${CALIBRATION_CONFIG}" | awk '{print $1}')" == "${CALIBRATION_CONFIG_SHA}" ]] || { echo "Calibration config changed." >&2; exit 2; }
[[ "$(sha256sum "${CALIBRATION_MANIFEST}" | awk '{print $1}')" == "${CALIBRATION_MANIFEST_SHA}" ]] || { echo "Calibration manifest changed." >&2; exit 2; }
[[ "$(sha256sum "${CALIBRATION_MANIFEST_LOCK}" | awk '{print $1}')" == "${CALIBRATION_MANIFEST_LOCK_SHA}" ]] || { echo "Calibration manifest lock changed." >&2; exit 2; }
[[ "$(sha256sum "${CALIBRATION_REPORT}" | awk '{print $1}')" == "${CALIBRATION_REPORT_SHA}" ]] || { echo "Calibration report changed." >&2; exit 2; }

set +e
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/analyze_image_watermark_spatial_filter.py" \
  --config "${CONFIG}" \
  --run-root "${RUN_ROOT}" \
  --output "${REPORT}"
STATUS=$?
set -e
if [[ "${STATUS}" == "0" ]]; then
  echo "Spatial-filter confirmation passed: ${REPORT}"
  exit 0
fi
if [[ "${STATUS}" == "2" ]]; then
  echo "Spatial-filter confirmation completed and failed its frozen gates: ${REPORT}" >&2
  exit 2
fi
echo "Spatial-filter confirmation analysis failed with status ${STATUS}." >&2
exit "${STATUS}"
