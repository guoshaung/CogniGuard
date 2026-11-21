#!/usr/bin/env bash
# Run the frozen development-only recovery-threshold candidate grid.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
EXPLICIT_FORMAL_CONFIG="${FORMAL_BENCHMARK_CONFIG-}"

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

if [[ -z "${EXPLICIT_FORMAL_CONFIG}" ]]; then
  echo "FORMAL_BENCHMARK_CONFIG must explicitly name the reviewed formal YAML." >&2
  exit 2
fi

# A calibration run is always bound to the manifest and dataset roots declared
# by its reviewed formal YAML.  Do not inherit generic machine-level overrides.
unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
unset COGNIGUARD_DATASET_ROOTS_JSON
unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
unset COGNIGUARD_PREREGISTRATION_CLAIM_PATH
unset COGNIGUARD_PREREGISTRATION_NONCE

PROJECT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
PROJECT_ROOT="$(cd -- "${PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${PROJECT_ROOT}/var/cache/python}"
export SCE_LOCGUARD_PROJECT_ROOT="${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/.venv-server/bin/python}"
FORMAL_CONFIG="${EXPLICIT_FORMAL_CONFIG}"
OUTPUT_BASE="${THRESHOLD_CALIBRATION_OUTPUT_BASE:-${PROJECT_ROOT}/var/outputs/image_watermark_threshold_calibration}"
RUN_TAG="${RUN_TAG:-threshold_calibration_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
CALIBRATION_BASE_URL="http://${API_HOST}:${API_PORT}"

if [[ "${FORMAL_CONFIG}" != /* ]]; then
  FORMAL_CONFIG="${PROJECT_ROOT}/${FORMAL_CONFIG}"
fi
if [[ "${OUTPUT_BASE}" != /* ]]; then
  OUTPUT_BASE="${PROJECT_ROOT}/${OUTPUT_BASE}"
fi

if [[ ! "${RUN_TAG}" =~ ^threshold_calibration_[A-Za-z0-9._-]+$ ]]; then
  echo "RUN_TAG must start with threshold_calibration_ and contain only safe filename characters." >&2
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

RUN_ROOT="${OUTPUT_BASE}/${RUN_TAG}"
mkdir -p -- "${OUTPUT_BASE}"
if ! mkdir -- "${RUN_ROOT}"; then
  echo "Refusing to overwrite threshold-calibration output: ${RUN_ROOT}" >&2
  exit 2
fi

CALIBRATION_CONFIG="${RUN_ROOT}/threshold_calibration.yaml"
CALIBRATION_MANIFEST="${RUN_ROOT}/threshold_calibration_dev_117.jsonl"
SELECTION_REPORT="${RUN_ROOT}/threshold_selection.json"
FORMAL_CONFIG_SHA256="$("${PYTHON_BIN}" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "${FORMAL_CONFIG}")"

BUILD_ARGS=(
  --source "${FORMAL_CONFIG}"
  --output "${CALIBRATION_CONFIG}"
  --manifest-output "${CALIBRATION_MANIFEST}"
  --base-url "${CALIBRATION_BASE_URL}"
  --threshold 0.20
  --threshold 0.22
  --threshold 0.24
  --threshold 0.26
  --threshold 0.28
  --threshold 0.30
  --threshold 0.32
  --threshold 0.34
  --threshold 0.36
)

cd -- "${PROJECT_ROOT}"
"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/build_image_watermark_threshold_calibration.py" "${BUILD_ARGS[@]}"

mapfile -t PREREGISTRATION_FIELDS < <(
  "${PYTHON_BIN}" - "${CALIBRATION_CONFIG}" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1]).resolve()
payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
claim = payload["threshold_calibration"]["preregistration_claim"]
print(claim["claim_path"])
print(claim["nonce"])
PY
)
if [[ "${#PREREGISTRATION_FIELDS[@]}" -ne 2 ]]; then
  echo "Threshold preregistration did not emit exactly one claim path and nonce." >&2
  exit 2
fi
PREREGISTRATION_CLAIM_PATH="${PREREGISTRATION_FIELDS[0]}"
PREREGISTRATION_NONCE="${PREREGISTRATION_FIELDS[1]}"
if [[ ! -f "${PREREGISTRATION_CLAIM_PATH}" || ! "${PREREGISTRATION_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Threshold preregistration claim/nonce is missing or malformed." >&2
  exit 2
fi
if ! mkdir -- "${RUN_ROOT}/candidate-runs"; then
  echo "Unable to create the fresh preregistered threshold candidate root." >&2
  exit 2
fi

# The generated YAML contains absolute manifest and dataset-root bindings. Do
# not let a machine-level environment override redirect any candidate away
# from the frozen 117-row bundle.
unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
unset COGNIGUARD_DATASET_ROOTS_JSON

read -r MIN_SOURCE_DATASETS MIN_CONTENT_DOMAINS < <(
  "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")); r=d["data_requirements"]; print(r["minimum_datasets"], r["minimum_domains"])' "${CALIBRATION_CONFIG}"
)
mapfile -t CANDIDATE_LINES < <(
  "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")); [print("{}|{}".format(r["candidate_id"], r["recovery_threshold"])) for r in d["threshold_calibration"]["candidate_runs"]]' "${CALIBRATION_CONFIG}"
)
if [[ "${#CANDIDATE_LINES[@]}" -ne 9 ]]; then
  echo "Calibration bundle does not contain the exact frozen nine-candidate grid." >&2
  exit 2
fi

# Channel aggregation is not a calibration axis in this bundle. Override any
# machine/secure-environment default once and pass the same explicit value to
# every isolated candidate executor.
export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1

for candidate_line in "${CANDIDATE_LINES[@]}"; do
  IFS='|' read -r CANDIDATE_ID RECOVERY_THRESHOLD <<< "${candidate_line}"
  if [[ ! "${CANDIDATE_ID}" =~ ^recovery_threshold_[0-9]+p[0-9]+$ || ! "${RECOVERY_THRESHOLD}" =~ ^0\.[0-9]+$ ]]; then
    echo "Invalid candidate record in calibration YAML: ${candidate_line}" >&2
    exit 2
  fi
  CANDIDATE_DIR="${RUN_ROOT}/candidate-runs/${CANDIDATE_ID}"
  echo "Running development-only threshold candidate ${CANDIDATE_ID} (${RECOVERY_THRESHOLD})"
  SERVER_ENV_FILE="" \
  PYTHON_BIN="${PYTHON_BIN}" \
  WATERMARK_API_HOST="${API_HOST}" \
  WATERMARK_API_PORT="${API_PORT}" \
  SCE_LOCGUARD_BASE_URL="${CALIBRATION_BASE_URL}" \
  PILOT_MODE=0 \
  DEV_TUNING_MODE=0 \
  THRESHOLD_CALIBRATION_MODE=1 \
  CHANNEL_VOTE_CONFIRMATION_MODE=0 \
  FORMAL_DIRECT_MODE=0 \
  CALIBRATION_EXPECTED_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}" \
  SCE_LOCGUARD_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}" \
  SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1 \
  BENCHMARK_RESUME=0 \
  COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${PREREGISTRATION_CLAIM_PATH}" \
  COGNIGUARD_PREREGISTRATION_NONCE="${PREREGISTRATION_NONCE}" \
  BENCHMARK_CONFIG="${CALIBRATION_CONFIG}" \
  BENCHMARK_OUTPUT_DIR="${CANDIDATE_DIR}" \
  RUN_TAG="${RUN_TAG}_${CANDIDATE_ID}" \
  THRESHOLD_CALIBRATION_MIN_DATASET_SAMPLES=117 \
  THRESHOLD_CALIBRATION_MIN_SELECTED_SAMPLES=117 \
  THRESHOLD_CALIBRATION_MIN_SOURCE_DATASETS="${MIN_SOURCE_DATASETS}" \
  THRESHOLD_CALIBRATION_MIN_CONTENT_DOMAINS="${MIN_CONTENT_DOMAINS}" \
  bash "${PROJECT_ROOT}/scripts/server/image_watermark_benchmark.sbatch"

  CURRENT_FORMAL_SHA256="$("${PYTHON_BIN}" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "${FORMAL_CONFIG}")"
  if [[ "${CURRENT_FORMAL_SHA256}" != "${FORMAL_CONFIG_SHA256}" ]]; then
    echo "Frozen formal config changed during threshold calibration." >&2
    exit 2
  fi
done

"${PYTHON_BIN}" "${PROJECT_ROOT}/scripts/server/analyze_image_watermark_threshold_calibration.py" \
  --config "${CALIBRATION_CONFIG}" \
  --run-root "${RUN_ROOT}" \
  --output "${SELECTION_REPORT}"

echo "Development-only threshold selection report: ${SELECTION_REPORT}"
echo "The formal test config was not modified; freeze the winner only in a separate reviewed step."
