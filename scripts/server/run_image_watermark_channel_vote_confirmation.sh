#!/usr/bin/env bash
# Preregister and execute the sole 0.34 / 2-of-3 development confirmation.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
EXPLICIT_FORMAL_CONFIG="${FORMAL_BENCHMARK_CONFIG-}"
EXPLICIT_CALIBRATION_RUN_ROOT="${THRESHOLD_CALIBRATION_RUN_ROOT-}"

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

if [[ -z "${EXPLICIT_FORMAL_CONFIG}" || -z "${EXPLICIT_CALIBRATION_RUN_ROOT}" ]]; then
  echo "FORMAL_BENCHMARK_CONFIG and THRESHOLD_CALIBRATION_RUN_ROOT must both be supplied explicitly." >&2
  exit 2
fi
if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "Channel-vote confirmation forbids inherited or fabricated SLURM_JOB_ID." >&2
  exit 2
fi

# The explicit formal/calibration roots are authoritative. Generic overrides
# from a machine or secure environment must never redirect this run.
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
CALIBRATION_RUN_ROOT="${EXPLICIT_CALIBRATION_RUN_ROOT}"
OUTPUT_BASE="${CHANNEL_VOTE_CONFIRMATION_OUTPUT_BASE:-${PROJECT_ROOT}/var/outputs/image_watermark_channel_vote_confirmation}"
RUN_TAG="${RUN_TAG:-channel_vote_confirmation_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
BASE_URL="http://${API_HOST}:${API_PORT}"
CANDIDATE_ID="recovery_threshold_0p34__channel_vote_2of3"

for path_variable in FORMAL_CONFIG CALIBRATION_RUN_ROOT OUTPUT_BASE; do
  declare value="${!path_variable}"
  if [[ "${value}" != /* ]]; then
    printf -v "${path_variable}" '%s' "${PROJECT_ROOT}/${value}"
  fi
done
FORMAL_CONFIG="$(cd -- "$(dirname -- "${FORMAL_CONFIG}")" && pwd)/$(basename -- "${FORMAL_CONFIG}")"
CALIBRATION_RUN_ROOT="$(cd -- "${CALIBRATION_RUN_ROOT}" && pwd)"
if [[ ! "${RUN_TAG}" =~ ^channel_vote_confirmation_[A-Za-z0-9._-]+$ ]]; then
  echo "RUN_TAG must begin with channel_vote_confirmation_ and use safe filename characters." >&2
  exit 2
fi
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python interpreter is not executable: ${PYTHON_BIN}" >&2
  exit 2
fi
if [[ ! -f "${FORMAL_CONFIG}" ]]; then
  echo "Frozen formal benchmark config is missing: ${FORMAL_CONFIG}" >&2
  exit 2
fi

mapfile -t CALIBRATION_INPUTS < <(
  "${PYTHON_BIN}" - "${CALIBRATION_RUN_ROOT}" "${FORMAL_CONFIG}" <<'PY'
import json
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1]).resolve()
formal = Path(sys.argv[2]).resolve()
config = root / "threshold_calibration.yaml"
report = root / "threshold_selection.json"
if not config.is_file() or not report.is_file():
    raise SystemExit("Calibration root must contain threshold_calibration.yaml and threshold_selection.json.")
payload = yaml.safe_load(config.read_text(encoding="utf-8"))
if not isinstance(payload, dict):
    raise SystemExit("Threshold calibration YAML root is not a mapping.")
manifest = Path(str((payload.get("manifest") or {}).get("path") or "")).resolve()
contract = payload.get("threshold_calibration") or {}
if manifest.parent != root or not manifest.is_file():
    raise SystemExit("Calibration manifest is missing or escapes the supplied calibration root.")
if Path(str(contract.get("source_formal_config") or "")).resolve() != formal:
    raise SystemExit("Calibration root is not bound to the explicitly supplied formal config.")
selection = json.loads(report.read_text(encoding="utf-8"))
if not isinstance(selection, dict) or selection.get("status") not in {
    "winner_selected",
    "no_candidate_satisfies_constraints",
}:
    raise SystemExit("Threshold selection report has no valid completed status.")
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
  echo "Refusing to reuse channel-vote confirmation bundle root: ${RUN_ROOT}" >&2
  exit 2
fi

CONFIRMATION_CONFIG="${RUN_ROOT}/channel_vote_confirmation.yaml"
CONFIRMATION_MANIFEST="${RUN_ROOT}/channel_vote_confirmation_dev_216.jsonl"
CONFIRMATION_REPORT="${RUN_ROOT}/channel_vote_confirmation_report.json"
CANDIDATE_DIR="${RUN_ROOT}/confirmation-run/${CANDIDATE_ID}"

cd -- "${PROJECT_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/build_image_watermark_channel_vote_confirmation.py" \
  --source "${FORMAL_CONFIG}" \
  --calibration-config "${CALIBRATION_CONFIG}" \
  --calibration-manifest "${CALIBRATION_MANIFEST}" \
  --calibration-run-root "${CALIBRATION_RUN_ROOT}" \
  --calibration-report "${CALIBRATION_REPORT}" \
  --output "${CONFIRMATION_CONFIG}" \
  --manifest-output "${CONFIRMATION_MANIFEST}" \
  --base-url "${BASE_URL}"

mapfile -t PREREGISTRATION_FIELDS < <(
  "${PYTHON_BIN}" - "${CONFIRMATION_CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1]).resolve()
payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
claim = payload["channel_vote_confirmation"]["preregistration_claim"]
print(claim["claim_path"])
print(claim["nonce"])
PY
)
if [[ "${#PREREGISTRATION_FIELDS[@]}" -ne 2 ]]; then
  echo "Confirmation preregistration did not emit exactly one claim path and nonce." >&2
  exit 2
fi
PREREGISTRATION_CLAIM_PATH="${PREREGISTRATION_FIELDS[0]}"
PREREGISTRATION_NONCE="${PREREGISTRATION_FIELDS[1]}"
if [[ ! -f "${PREREGISTRATION_CLAIM_PATH}" || ! "${PREREGISTRATION_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Confirmation preregistration claim/nonce is missing or malformed." >&2
  exit 2
fi
if ! mkdir -- "${RUN_ROOT}/confirmation-run"; then
  echo "Unable to create the fresh preregistered confirmation candidate root." >&2
  exit 2
fi

# Pre-registration must finish while the sole candidate path is still absent.
if [[ ! -f "${CONFIRMATION_CONFIG}" || ! -f "${CONFIRMATION_MANIFEST}" || -e "${CANDIDATE_DIR}" ]]; then
  echo "Confirmation preregistration is incomplete or candidate artifacts predate it." >&2
  exit 2
fi
read -r MIN_SOURCE_DATASETS MIN_CONTENT_DOMAINS < <(
  "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")); r=d["data_requirements"]; print(r["minimum_datasets"], r["minimum_domains"])' "${CONFIRMATION_CONFIG}"
)
if [[ "${MIN_SOURCE_DATASETS}" != "4" || ! "${MIN_CONTENT_DOMAINS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Confirmation preregistration did not preserve four datasets and at least nine domains." >&2
  exit 2
fi
if (( MIN_CONTENT_DOMAINS < 9 )); then
  echo "Confirmation preregistration did not preserve four datasets and at least nine domains." >&2
  exit 2
fi

SERVER_ENV_FILE="" \
PYTHON_BIN="${PYTHON_BIN}" \
WATERMARK_API_HOST="${API_HOST}" \
WATERMARK_API_PORT="${API_PORT}" \
PILOT_MODE=0 \
DEV_TUNING_MODE=0 \
THRESHOLD_CALIBRATION_MODE=0 \
CHANNEL_VOTE_CONFIRMATION_MODE=1 \
FORMAL_DIRECT_MODE=0 \
SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34 \
SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001 \
SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=2 \
BENCHMARK_RESUME=0 \
COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${PREREGISTRATION_CLAIM_PATH}" \
COGNIGUARD_PREREGISTRATION_NONCE="${PREREGISTRATION_NONCE}" \
BENCHMARK_CONFIG="${CONFIRMATION_CONFIG}" \
BENCHMARK_OUTPUT_DIR="${CANDIDATE_DIR}" \
RUN_TAG="${RUN_TAG}_${CANDIDATE_ID}" \
CHANNEL_VOTE_CONFIRMATION_MIN_DATASET_SAMPLES=216 \
CHANNEL_VOTE_CONFIRMATION_MIN_SELECTED_SAMPLES=216 \
CHANNEL_VOTE_CONFIRMATION_MIN_SOURCE_DATASETS=4 \
CHANNEL_VOTE_CONFIRMATION_MIN_CONTENT_DOMAINS="${MIN_CONTENT_DOMAINS}" \
bash "${PROJECT_ROOT}/scripts/server/image_watermark_benchmark.sbatch"

set +e
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/analyze_image_watermark_channel_vote_confirmation.py" \
  --config "${CONFIRMATION_CONFIG}" \
  --run-root "${RUN_ROOT}" \
  --output "${CONFIRMATION_REPORT}"
ANALYZER_STATUS=$?
set -e

if [[ "${ANALYZER_STATUS}" == "0" ]]; then
  echo "Channel-vote confirmation passed: ${CONFIRMATION_REPORT}"
  exit 0
fi
if [[ "${ANALYZER_STATUS}" == "2" ]]; then
  echo "Channel-vote confirmation completed and failed its preregistered gates: ${CONFIRMATION_REPORT}" >&2
  exit 2
fi
echo "Channel-vote confirmation analysis failed with status ${ANALYZER_STATUS}." >&2
exit "${ANALYZER_STATUS}"
