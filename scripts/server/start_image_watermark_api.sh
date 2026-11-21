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
export SCE_LOCGUARD_OUTPUT_DIR="${SCE_LOCGUARD_OUTPUT_DIR:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/sce_locguard_jobs}"
export SCE_LOCGUARD_API_JOB_ROOT="${SCE_LOCGUARD_API_JOB_ROOT:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/sce_locguard_api_jobs}"
export SCE_LOCGUARD_REGISTRY_DIR="${SCE_LOCGUARD_REGISTRY_DIR:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/sce_locguard_registry}"
export HF_HOME="${HF_HOME:-${SCE_LOCGUARD_PROJECT_ROOT}/assets/models/hf_cache}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export HF_HUB_DISABLE_TELEMETRY="${HF_HUB_DISABLE_TELEMETRY:-1}"
export SCE_LOCGUARD_DETERMINISTIC="${SCE_LOCGUARD_DETERMINISTIC:-true}"
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-20260802}"
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export PYTHONPATH="${SCE_LOCGUARD_PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [[ ! "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export OMP_NUM_THREADS=8
fi
if [[ ! "${MKL_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export MKL_NUM_THREADS="${OMP_NUM_THREADS}"
fi

if [[ -z "${SCE_LOCGUARD_REGISTRY_SECRET:-}" && -n "${SCE_LOCGUARD_REGISTRY_SECRET_FILE:-}" ]]; then
  if [[ ! -r "${SCE_LOCGUARD_REGISTRY_SECRET_FILE}" ]]; then
    echo "Registry secret file is not readable: ${SCE_LOCGUARD_REGISTRY_SECRET_FILE}" >&2
    exit 2
  fi
  SECRET_MODE="$(stat -c '%a' "${SCE_LOCGUARD_REGISTRY_SECRET_FILE}")"
  if [[ "${SECRET_MODE: -2}" != "00" ]]; then
    echo "Registry secret file must not grant group/other permissions (use chmod 600)." >&2
    exit 2
  fi
  export SCE_LOCGUARD_REGISTRY_SECRET="$(<"${SCE_LOCGUARD_REGISTRY_SECRET_FILE}")"
fi

REGISTRY_SECRET="${SCE_LOCGUARD_REGISTRY_SECRET:-}"
if (( ${#REGISTRY_SECRET} < 32 )); then
  echo "SCE_LOCGUARD_REGISTRY_SECRET must contain at least 32 characters." >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
export SCE_LOCGUARD_BASE_URL="http://${API_HOST}:${API_PORT}"
ASSET_MANIFEST="${COGNIGUARD_WATERMARK_ASSET_MANIFEST:-${SCE_LOCGUARD_PROJECT_ROOT}/deploy/image_watermark/assets.manifest.example.json}"

mkdir -p -- "${SCE_LOCGUARD_OUTPUT_DIR}" "${SCE_LOCGUARD_API_JOB_ROOT}" "${SCE_LOCGUARD_REGISTRY_DIR}"

if [[ "${RUN_PREFLIGHT:-1}" == "1" ]]; then
  PREFLIGHT_ARGS=(
    --project-root "${SCE_LOCGUARD_PROJECT_ROOT}"
    --output-root "${SCE_LOCGUARD_API_JOB_ROOT}"
    --asset-manifest "${ASSET_MANIFEST}"
    --hf-cache "${HF_HOME}"
    --require-linux
    --require-cuda
    --require-secret
    --require-asset-hashes
    --require-deterministic
  )
  if [[ "${REQUIRE_AIGC_CACHE:-1}" == "1" ]]; then
    PREFLIGHT_ARGS+=(--require-hf-cache)
  fi
  if [[ -n "${COGNIGUARD_SHARED_ROOT:-}" ]]; then
    PREFLIGHT_ARGS+=(--shared-root "${COGNIGUARD_SHARED_ROOT}")
  elif [[ "${REQUIRE_SHARED_ROOT:-0}" == "1" ]]; then
    PREFLIGHT_ARGS+=(--require-shared-root)
  fi
  if [[ "${REQUIRE_DATASET_MANIFEST:-0}" == "1" && -n "${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG:-}" ]]; then
    PREFLIGHT_ARGS+=(--benchmark-config "${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG}")
    PREFLIGHT_ARGS+=(--require-dataset-files --require-license-metadata)
  fi
  "${PYTHON_BIN}" "${SCE_LOCGUARD_PROJECT_ROOT}/scripts/server/preflight_image_watermark.py" "${PREFLIGHT_ARGS[@]}"
fi

cd -- "${SCE_LOCGUARD_PROJECT_ROOT}"
echo "Starting SCE-LocGuard API on ${API_HOST}:${API_PORT} with exactly one worker."
exec "${PYTHON_BIN}" -m uvicorn protection.supporting.image_watermark.api.server:app \
  --host "${API_HOST}" \
  --port "${API_PORT}" \
  --workers 1 \
  --log-level "${WATERMARK_API_LOG_LEVEL:-info}" \
  --timeout-keep-alive 5
