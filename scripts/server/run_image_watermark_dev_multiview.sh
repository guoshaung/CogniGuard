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

PROJECT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
PROJECT_ROOT="$(cd -- "${PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${PROJECT_ROOT}/var/cache/python}"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/.venv-server/bin/python}"
DEV_RUN_DIR="${1:-${DEV_TUNING_RUN_DIR:-}}"
if [[ -z "${DEV_RUN_DIR}" ]]; then
  echo "Usage: $0 /absolute/path/to/completed/dev_tuning_run [extra tool args]" >&2
  exit 2
fi
shift || true
if [[ "${DEV_RUN_DIR}" != /* || ! -d "${DEV_RUN_DIR}" ]]; then
  echo "A completed absolute dev run directory is required: ${DEV_RUN_DIR}" >&2
  exit 2
fi

export SCE_LOCGUARD_DETERMINISTIC=true
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-20260802}"
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUNBUFFERED=1

cd -- "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" -m protection.supporting.image_watermark.experiments.dev_multiview_decode \
  --project-root "${PROJECT_ROOT}" \
  --run-dir "${DEV_RUN_DIR}" \
  "$@"
