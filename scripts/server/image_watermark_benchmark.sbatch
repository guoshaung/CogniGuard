#!/usr/bin/env bash
# Slurm entrypoint and shared executor for the audited direct-formal wrapper.
# Direct formal users must call run_image_watermark_formal.sh rather than forge
# scheduler variables. Adjust partition/account/time/memory for a real cluster.
#SBATCH --job-name=cg-watermark
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=var/logs/slurm-%x-%j.out

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
EXPLICIT_BENCHMARK_CONFIG="${BENCHMARK_CONFIG-}"
REQUESTED_SERVER_ENV_FILE="${SERVER_ENV_FILE-}"
EXPLICIT_THRESHOLD_CALIBRATION_MODE="${THRESHOLD_CALIBRATION_MODE-}"
EXPLICIT_CHANNEL_VOTE_CONFIRMATION_MODE="${CHANNEL_VOTE_CONFIRMATION_MODE-}"
EXPLICIT_SPATIAL_FILTER_MODE="${SPATIAL_FILTER_MODE-}"
EXPLICIT_PREREGISTRATION_CLAIM_PATH="${COGNIGUARD_PREREGISTRATION_CLAIM_PATH-}"
EXPLICIT_PREREGISTRATION_NONCE="${COGNIGUARD_PREREGISTRATION_NONCE-}"

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

if [[ -n "${REQUESTED_SERVER_ENV_FILE}" ]] && {
  [[ "${EXPLICIT_THRESHOLD_CALIBRATION_MODE}" == "1" ]] ||
  [[ "${THRESHOLD_CALIBRATION_MODE:-0}" == "1" ]] ||
  [[ "${EXPLICIT_CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]] ||
  [[ "${CHANNEL_VOTE_CONFIRMATION_MODE:-0}" == "1" ]] ||
  [[ "${EXPLICIT_SPATIAL_FILTER_MODE}" == "1" ]] ||
  [[ "${SPATIAL_FILTER_MODE:-0}" == "1" ]]
}; then
  echo "Threshold/confirmation execution forbids re-sourcing SERVER_ENV_FILE; pre-source it in the audited runner." >&2
  exit 2
fi

PILOT_MODE="${PILOT_MODE:-0}"
DEV_TUNING_MODE="${DEV_TUNING_MODE:-0}"
THRESHOLD_CALIBRATION_MODE="${THRESHOLD_CALIBRATION_MODE:-0}"
CHANNEL_VOTE_CONFIRMATION_MODE="${CHANNEL_VOTE_CONFIRMATION_MODE:-0}"
SPATIAL_FILTER_MODE="${SPATIAL_FILTER_MODE:-0}"
FORMAL_DIRECT_MODE="${FORMAL_DIRECT_MODE:-0}"
for MODE_VALUE in \
  "${PILOT_MODE}" \
  "${DEV_TUNING_MODE}" \
  "${THRESHOLD_CALIBRATION_MODE}" \
  "${CHANNEL_VOTE_CONFIRMATION_MODE}" \
  "${SPATIAL_FILTER_MODE}" \
  "${FORMAL_DIRECT_MODE}"; do
  if [[ "${MODE_VALUE}" != "0" && "${MODE_VALUE}" != "1" ]]; then
    echo "Benchmark mode flags must be exactly 0 or 1." >&2
    exit 2
  fi
done
MODE_COUNT=0
if [[ "${PILOT_MODE}" == "1" ]]; then MODE_COUNT=$((MODE_COUNT + 1)); fi
if [[ "${DEV_TUNING_MODE}" == "1" ]]; then MODE_COUNT=$((MODE_COUNT + 1)); fi
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then MODE_COUNT=$((MODE_COUNT + 1)); fi
if [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then MODE_COUNT=$((MODE_COUNT + 1)); fi
if [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then MODE_COUNT=$((MODE_COUNT + 1)); fi
if (( MODE_COUNT > 1 )); then
  echo "All benchmark development mode flags are mutually exclusive." >&2
  exit 2
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" && "${MODE_COUNT}" != "0" ]]; then
  echo "FORMAL_DIRECT_MODE=1 requires all development modes to be 0." >&2
  exit 2
fi
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" || "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" || "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  if [[ -z "${EXPLICIT_PREREGISTRATION_CLAIM_PATH}" || ! "${EXPLICIT_PREREGISTRATION_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "Frozen development execution requires an explicit preregistration claim and 256-bit nonce." >&2
    exit 2
  fi
  export COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${EXPLICIT_PREREGISTRATION_CLAIM_PATH}"
  export COGNIGUARD_PREREGISTRATION_NONCE="${EXPLICIT_PREREGISTRATION_NONCE}"
elif [[ -n "${EXPLICIT_PREREGISTRATION_CLAIM_PATH}" || -n "${EXPLICIT_PREREGISTRATION_NONCE}" ]]; then
  echo "Preregistration evidence is valid only for frozen development runs." >&2
  exit 2
else
  unset COGNIGUARD_PREREGISTRATION_CLAIM_PATH
  unset COGNIGUARD_PREREGISTRATION_NONCE
fi
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then
  if [[ "${SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN:-}" != "1" ]]; then
    echo "Threshold calibration requires SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1; refusing secure-environment drift." >&2
    exit 2
  fi
  export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1
fi
if [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then
  if [[ -z "${EXPLICIT_BENCHMARK_CONFIG}" ]]; then
    echo "Channel-vote confirmation requires an explicit preregistered BENCHMARK_CONFIG." >&2
    exit 2
  fi
  BENCHMARK_CONFIG="${EXPLICIT_BENCHMARK_CONFIG}"
  unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
  if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    echo "Channel-vote confirmation is a direct audited run and forbids inherited or fabricated SLURM_JOB_ID." >&2
    exit 2
  fi
  if [[ "${SCE_LOCGUARD_RECOVERY_THRESHOLD:-}" != "0.34" ]]; then
    echo "Channel-vote confirmation requires SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34." >&2
    exit 2
  fi
  if [[ "${SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN:-}" != "2" ]]; then
    echo "Channel-vote confirmation requires SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=2." >&2
    exit 2
  fi
  if [[ "${SCE_LOCGUARD_TAMPER_AREA_THRESHOLD:-}" != "0.001" ]]; then
    echo "Channel-vote confirmation requires SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001." >&2
    exit 2
  fi
  export SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34
  export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=2
  export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001
fi
if [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  if [[ -z "${EXPLICIT_BENCHMARK_CONFIG}" ]]; then
    echo "Spatial-filter execution requires an explicit preregistered BENCHMARK_CONFIG." >&2
    exit 2
  fi
  BENCHMARK_CONFIG="${EXPLICIT_BENCHMARK_CONFIG}"
  unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
  if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    echo "Spatial-filter development is a direct audited run and forbids inherited SLURM_JOB_ID." >&2
    exit 2
  fi
  if [[ "${SCE_LOCGUARD_RECOVERY_THRESHOLD:-}" != "0.34" || "${SCE_LOCGUARD_TAMPER_AREA_THRESHOLD:-}" != "0.001" || "${SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN:-}" != "1" ]]; then
    echo "Spatial-filter development requires recovery=0.34, tamper=0.001, and channel vote k=1." >&2
    exit 2
  fi
  case "${SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO:-}" in
    0.005|0.01|0.02) ;;
    *)
      echo "Spatial-filter area ratio must be one frozen candidate: 0.005, 0.01, or 0.02." >&2
      exit 2
      ;;
  esac
  export SCE_LOCGUARD_RECOVERY_THRESHOLD=0.34
  export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD=0.001
  export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN=1
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" && -n "${SLURM_JOB_ID:-}" ]]; then
  echo "Direct formal execution forbids an inherited or fabricated SLURM_JOB_ID." >&2
  exit 2
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" && "${BENCHMARK_RESUME:-0}" != "0" ]]; then
  echo "Direct formal execution requires BENCHMARK_RESUME=0." >&2
  exit 2
fi
if [[ "${MODE_COUNT}" == "0" && -z "${EXPLICIT_BENCHMARK_CONFIG}" ]]; then
  echo "Formal execution requires an explicit selected BENCHMARK_CONFIG." >&2
  exit 2
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" && ( -z "${RUN_TAG:-}" || -z "${BENCHMARK_OUTPUT_DIR:-}" ) ]]; then
  echo "Direct formal execution requires explicit fresh RUN_TAG and BENCHMARK_OUTPUT_DIR values." >&2
  exit 2
fi
if [[ "${MODE_COUNT}" == "0" ]]; then
  # The caller-selected formal YAML is authoritative for both Slurm and direct
  # execution. Never let a secure-env default redirect formal config or data.
  BENCHMARK_CONFIG="${EXPLICIT_BENCHMARK_CONFIG}"
  unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
fi
if [[ -z "${SLURM_JOB_ID:-}" && "${MODE_COUNT}" == "0" && "${FORMAL_DIRECT_MODE}" == "0" ]]; then
  echo "Formal direct runs require FORMAL_DIRECT_MODE=1 via run_image_watermark_formal.sh." >&2
  exit 2
fi
SLURM_JOB_EVIDENCE=""
SLURM_PID_EVIDENCE=""
if [[ "${MODE_COUNT}" == "0" && "${FORMAL_DIRECT_MODE}" == "0" ]]; then
  if [[ ! "${SLURM_JOB_ID}" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
    echo "Formal Slurm execution requires a numeric scheduler-issued SLURM_JOB_ID." >&2
    exit 2
  fi
  if ! command -v scontrol >/dev/null 2>&1; then
    echo "Formal Slurm execution requires scontrol for live allocation verification." >&2
    exit 2
  fi
  if ! SLURM_JOB_EVIDENCE="$(scontrol --oneliner show job "${SLURM_JOB_ID}")"; then
    echo "SLURM_JOB_ID is not backed by a live scheduler allocation." >&2
    exit 2
  fi
  EVIDENCE_JOB_ID=""
  EVIDENCE_JOB_STATE=""
  EVIDENCE_USER_ID=""
  EVIDENCE_BATCH_FLAG=""
  EVIDENCE_BATCH_HOST=""
  read -r -a SLURM_EVIDENCE_TOKENS <<< "${SLURM_JOB_EVIDENCE}"
  for TOKEN in "${SLURM_EVIDENCE_TOKENS[@]}"; do
    case "${TOKEN}" in
      JobId=*) EVIDENCE_JOB_ID="${TOKEN#JobId=}" ;;
      JobState=*) EVIDENCE_JOB_STATE="${TOKEN#JobState=}" ;;
      UserId=*) EVIDENCE_USER_ID="${TOKEN#UserId=}" ;;
      BatchFlag=*) EVIDENCE_BATCH_FLAG="${TOKEN#BatchFlag=}" ;;
      BatchHost=*) EVIDENCE_BATCH_HOST="${TOKEN#BatchHost=}" ;;
    esac
  done
  if [[ "${EVIDENCE_JOB_ID}" != "${SLURM_JOB_ID}" ]]; then
    echo "Live Slurm evidence does not match SLURM_JOB_ID." >&2
    exit 2
  fi
  case "${EVIDENCE_JOB_STATE}" in
    CONFIGURING | RUNNING | COMPLETING) ;;
    *)
      echo "Slurm allocation is not in an executing state: ${EVIDENCE_JOB_STATE:-missing}." >&2
      exit 2
      ;;
  esac
  if [[ "${EVIDENCE_USER_ID}" =~ \(([0-9]+)\)$ ]]; then
    EVIDENCE_NUMERIC_UID="${BASH_REMATCH[1]}"
  else
    echo "Live Slurm evidence does not contain a numeric allocation user." >&2
    exit 2
  fi
  if [[ "${EVIDENCE_NUMERIC_UID}" != "$(id -u)" ]]; then
    echo "Slurm allocation user does not match the current process user." >&2
    exit 2
  fi
  if [[ ! "${EVIDENCE_BATCH_FLAG}" =~ ^[1-9][0-9]*$ ]]; then
    echo "Slurm allocation is not an sbatch batch job." >&2
    exit 2
  fi
  LOCAL_HOST_SHORT="$(hostname -s)"
  LOCAL_HOST_FULL="$(hostname -f 2>/dev/null || hostname)"
  EVIDENCE_HOST_LOWER="${EVIDENCE_BATCH_HOST,,}"
  EVIDENCE_HOST_SHORT="${EVIDENCE_HOST_LOWER%%.*}"
  LOCAL_HOST_SHORT_LOWER="${LOCAL_HOST_SHORT,,}"
  LOCAL_HOST_FULL_LOWER="${LOCAL_HOST_FULL,,}"
  if [[ -z "${EVIDENCE_BATCH_HOST}" ]] || {
    [[ "${EVIDENCE_HOST_LOWER}" != "${LOCAL_HOST_SHORT_LOWER}" ]] &&
    [[ "${EVIDENCE_HOST_LOWER}" != "${LOCAL_HOST_FULL_LOWER}" ]] &&
    [[ "${EVIDENCE_HOST_SHORT}" != "${LOCAL_HOST_SHORT_LOWER}" ]]
  }; then
    echo "Slurm batch host does not match the current execution host." >&2
    exit 2
  fi
  if ! SLURM_PID_EVIDENCE="$(scontrol pidinfo "$$")"; then
    echo "Current process is not attached to a live Slurm allocation." >&2
    exit 2
  fi
  if [[ ! "${SLURM_PID_EVIDENCE}" =~ (^|[^0-9_])${SLURM_JOB_ID}([^0-9_]|$) ]]; then
    echo "Current process Slurm allocation differs from SLURM_JOB_ID." >&2
    exit 2
  fi
fi

export SCE_LOCGUARD_PROJECT_ROOT="${SCE_LOCGUARD_PROJECT_ROOT:-${DEFAULT_PROJECT_ROOT}}"
export SCE_LOCGUARD_PROJECT_ROOT="$(cd -- "${SCE_LOCGUARD_PROJECT_ROOT}" && pwd)"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${SCE_LOCGUARD_PROJECT_ROOT}/var/cache/python}"
export SCE_LOCGUARD_OUTPUT_DIR="${SCE_LOCGUARD_OUTPUT_DIR:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/sce_locguard_jobs}"
export HF_HOME="${HF_HOME:-${SCE_LOCGUARD_PROJECT_ROOT}/assets/models/hf_cache}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
export SCE_LOCGUARD_DETERMINISTIC=true
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-20260802}"
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
export PYTHONPATH="${SCE_LOCGUARD_PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [[ ! "${OMP_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  CPU_THREADS="${SLURM_CPUS_PER_TASK:-8}"
  if [[ ! "${CPU_THREADS}" =~ ^[1-9][0-9]*$ ]]; then
    CPU_THREADS=8
  fi
  export OMP_NUM_THREADS="${CPU_THREADS}"
fi
if [[ ! "${MKL_NUM_THREADS:-}" =~ ^[1-9][0-9]*$ ]]; then
  export MKL_NUM_THREADS="${OMP_NUM_THREADS}"
fi

PYTHON_BIN="${PYTHON_BIN:-${SCE_LOCGUARD_PROJECT_ROOT}/.venv-server/bin/python}"
BENCHMARK_CONFIG="${BENCHMARK_CONFIG:-${COGNIGUARD_WATERMARK_BENCHMARK_CONFIG:-${SCE_LOCGUARD_PROJECT_ROOT}/protection/image_watermark/configs/paper_benchmark.yaml}}"
ASSET_MANIFEST="${COGNIGUARD_WATERMARK_ASSET_MANIFEST:-${SCE_LOCGUARD_PROJECT_ROOT}/deploy/image_watermark/assets.manifest.example.json}"
API_HOST="${WATERMARK_API_HOST:-127.0.0.1}"
API_PORT="${WATERMARK_API_PORT:-8010}"
export SCE_LOCGUARD_BASE_URL="http://${API_HOST}:${API_PORT}"

if [[ "${MODE_COUNT}" == "0" ]]; then
  # Re-resolve the frozen values in the shared executor. This prevents callers
  # from bypassing the wrapper and supplying arbitrary service thresholds.
  FORMAL_SERVICE_PARAMETERS="$(
    "${PYTHON_BIN}" -c \
      'import sys; from protection.image_watermark.experiments.paper_benchmark import resolve_formal_service_parameters; p=resolve_formal_service_parameters(sys.argv[1]); print(f"{p['"'"'recovery_threshold'"'"']!r}\t{p['"'"'tamper_area_threshold'"'"']!r}\t{p['"'"'localization_channel_vote_min'"'"']}\t{p.get('"'"'localization_min_component_area_ratio'"'"', 0.0)!r}")' \
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
  export SCE_LOCGUARD_RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD}"
  export SCE_LOCGUARD_TAMPER_AREA_THRESHOLD="${TAMPER_AREA_THRESHOLD}"
  export SCE_LOCGUARD_LOCALIZATION_CHANNEL_VOTE_MIN="${LOCALIZATION_CHANNEL_VOTE_MIN}"
  if [[ "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" == "0" || "${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}" == "0.0" ]]; then
    # The legacy v2 service contract represents no post-processing with the
    # variable absent/blank; an explicit numeric zero is rejected by the parser.
    export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO=""
  else
    export SCE_LOCGUARD_LOCALIZATION_MIN_COMPONENT_AREA_RATIO="${LOCALIZATION_MIN_COMPONENT_AREA_RATIO}"
  fi
fi

RUN_TAG="${RUN_TAG:-slurm_${SLURM_JOB_ID:-manual}}"
RUN_DIR="${BENCHMARK_OUTPUT_DIR:-${SCE_LOCGUARD_PROJECT_ROOT}/var/outputs/image_watermark_paper/${RUN_TAG}}"
PREREGISTRATION_RUN_CLASS=""
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then
  PREREGISTRATION_RUN_CLASS="threshold_calibration_development_only"
elif [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then
  PREREGISTRATION_RUN_CLASS="channel_vote_confirmation_development_only"
elif [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  PREREGISTRATION_RUN_CLASS="$(
    "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}; print((d.get("experiment") or {}).get("run_class") or "")' "${BENCHMARK_CONFIG}"
  )"
  if [[ "${PREREGISTRATION_RUN_CLASS}" != "spatial_filter_calibration_development_only" && "${PREREGISTRATION_RUN_CLASS}" != "spatial_filter_confirmation_development_only" ]]; then
    echo "Spatial-filter config has an unsupported development run class." >&2
    exit 2
  fi
fi
if [[ -n "${PREREGISTRATION_RUN_CLASS}" ]]; then
  "${PYTHON_BIN}" -m scripts.server.image_watermark_preregistration validate \
    --config "${BENCHMARK_CONFIG}" \
    --claim "${COGNIGUARD_PREREGISTRATION_CLAIM_PATH}" \
    --run-class "${PREREGISTRATION_RUN_CLASS}" \
    --nonce "${COGNIGUARD_PREREGISTRATION_NONCE}" \
    --candidate-run "${RUN_DIR}"
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" ]]; then
  if [[ ! "${RUN_TAG}" =~ ^formal_direct_[A-Za-z0-9._-]+$ ]]; then
    echo "Direct formal RUN_TAG must begin with formal_direct_ and use safe characters." >&2
    exit 2
  fi
  NORMALIZED_RUN_DIR="${RUN_DIR%/}"
  if [[ "${NORMALIZED_RUN_DIR##*/}" != "${RUN_TAG}" ]]; then
    echo "Direct formal output directory basename must equal RUN_TAG." >&2
    exit 2
  fi
  if [[ -e "${RUN_DIR}" ]]; then
    echo "Refusing to reuse a formal direct run directory: ${RUN_DIR}" >&2
    exit 2
  fi
  if ! mkdir -- "${RUN_DIR}"; then
    echo "Unable to atomically create a fresh formal direct run directory: ${RUN_DIR}" >&2
    exit 2
  fi
elif [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" || "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" || "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  if ! mkdir -- "${RUN_DIR}"; then
    echo "Refusing to overwrite threshold/confirmation run directory: ${RUN_DIR}" >&2
    exit 2
  fi
else
  mkdir -p -- "${RUN_DIR}"
fi
if [[ -n "${PREREGISTRATION_RUN_CLASS}" ]]; then
  SOURCE_PREREGISTRATION_CLAIM_PATH="${COGNIGUARD_PREREGISTRATION_CLAIM_PATH}"
  "${PYTHON_BIN}" -m scripts.server.image_watermark_preregistration copy \
    --config "${BENCHMARK_CONFIG}" \
    --claim "${SOURCE_PREREGISTRATION_CLAIM_PATH}" \
    --run-class "${PREREGISTRATION_RUN_CLASS}" \
    --nonce "${COGNIGUARD_PREREGISTRATION_NONCE}" \
    --candidate-run "${RUN_DIR}"
  export COGNIGUARD_PREREGISTRATION_CLAIM_PATH="${RUN_DIR}/preregistration-claim.json"
fi
if [[ "${FORMAL_DIRECT_MODE}" == "1" ]]; then
  RUN_SCHEDULER="direct_single_gpu"
elif [[ -n "${SLURM_JOB_ID:-}" ]]; then
  RUN_SCHEDULER="slurm"
else
  RUN_SCHEDULER="direct_nonformal"
fi
printf '%s\n' "scheduler=${RUN_SCHEDULER}" > "${RUN_DIR}/scheduler.txt"
if [[ -n "${SLURM_JOB_EVIDENCE}" ]]; then
  printf '%s\n' "${SLURM_JOB_EVIDENCE}" > "${RUN_DIR}/scheduler-slurm-evidence.txt"
  printf '%s\n' "${SLURM_PID_EVIDENCE}" > "${RUN_DIR}/scheduler-slurm-pid-evidence.txt"
fi
# Never inherit the standalone/global locations from SERVER_ENV_FILE. Each run
# owns its API jobs and source registry, including resumed runs using RUN_DIR.
export SCE_LOCGUARD_API_JOB_ROOT="${RUN_DIR}/api_jobs"
export SCE_LOCGUARD_REGISTRY_DIR="${RUN_DIR}/source-registry-live"
mkdir -p -- "${SCE_LOCGUARD_API_JOB_ROOT}" "${SCE_LOCGUARD_REGISTRY_DIR}"
SCE_LOCGUARD_RUN_INSTANCE_NONCE="$("${PYTHON_BIN}" -c 'import secrets; print(secrets.token_hex(32))')"
if [[ ! "${SCE_LOCGUARD_RUN_INSTANCE_NONCE}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "Unable to generate a fresh 256-bit API run-instance nonce." >&2
  exit 2
fi
export SCE_LOCGUARD_RUN_INSTANCE_NONCE

if [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  RUN_CLASS="$(
    "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}; print((d.get("experiment") or {}).get("run_class") or "")' "${BENCHMARK_CONFIG}"
  )"
  if [[ "${RUN_CLASS}" == "spatial_filter_calibration_development_only" ]]; then
    MIN_DATASET_SAMPLES_EFFECTIVE="${SPATIAL_FILTER_MIN_DATASET_SAMPLES:-300}"
    MIN_TEST_SAMPLES_EFFECTIVE="${SPATIAL_FILTER_MIN_SELECTED_SAMPLES:-300}"
  elif [[ "${RUN_CLASS}" == "spatial_filter_confirmation_development_only" ]]; then
    MIN_DATASET_SAMPLES_EFFECTIVE="${SPATIAL_FILTER_MIN_DATASET_SAMPLES:-600}"
    MIN_TEST_SAMPLES_EFFECTIVE="${SPATIAL_FILTER_MIN_SELECTED_SAMPLES:-600}"
  else
    echo "Spatial-filter config run class is invalid: ${RUN_CLASS}" >&2
    exit 2
  fi
  MIN_SOURCE_DATASETS_EFFECTIVE="${SPATIAL_FILTER_MIN_SOURCE_DATASETS:-4}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${SPATIAL_FILTER_MIN_CONTENT_DOMAINS:-34}"
elif [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then
  RUN_CLASS="channel_vote_confirmation_development_only"
  MIN_DATASET_SAMPLES_EFFECTIVE="${CHANNEL_VOTE_CONFIRMATION_MIN_DATASET_SAMPLES:-216}"
  MIN_TEST_SAMPLES_EFFECTIVE="${CHANNEL_VOTE_CONFIRMATION_MIN_SELECTED_SAMPLES:-216}"
  MIN_SOURCE_DATASETS_EFFECTIVE="${CHANNEL_VOTE_CONFIRMATION_MIN_SOURCE_DATASETS:-4}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${CHANNEL_VOTE_CONFIRMATION_MIN_CONTENT_DOMAINS:-9}"
elif [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then
  RUN_CLASS="threshold_calibration_development_only"
  MIN_DATASET_SAMPLES_EFFECTIVE="${THRESHOLD_CALIBRATION_MIN_DATASET_SAMPLES:-117}"
  MIN_TEST_SAMPLES_EFFECTIVE="${THRESHOLD_CALIBRATION_MIN_SELECTED_SAMPLES:-117}"
  MIN_SOURCE_DATASETS_EFFECTIVE="${THRESHOLD_CALIBRATION_MIN_SOURCE_DATASETS:-4}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${THRESHOLD_CALIBRATION_MIN_CONTENT_DOMAINS:-4}"
elif [[ "${DEV_TUNING_MODE}" == "1" ]]; then
  RUN_CLASS="dev_tuning"
  MIN_DATASET_SAMPLES_EFFECTIVE="${DEV_TUNING_MIN_DATASET_SAMPLES:-117}"
  MIN_TEST_SAMPLES_EFFECTIVE="${DEV_TUNING_MIN_SELECTED_SAMPLES:-117}"
  MIN_SOURCE_DATASETS_EFFECTIVE="${DEV_TUNING_MIN_SOURCE_DATASETS:-1}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${DEV_TUNING_MIN_CONTENT_DOMAINS:-9}"
elif [[ "${PILOT_MODE}" == "1" ]]; then
  RUN_CLASS="pilot_not_for_paper"
  MIN_DATASET_SAMPLES_EFFECTIVE="${PILOT_MIN_DATASET_SAMPLES:-1}"
  MIN_TEST_SAMPLES_EFFECTIVE="${PILOT_MIN_TEST_SAMPLES:-1}"
  MIN_SOURCE_DATASETS_EFFECTIVE="${PILOT_MIN_SOURCE_DATASETS:-1}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${PILOT_MIN_CONTENT_DOMAINS:-1}"
else
  RUN_CLASS="formal_paper_candidate"
  MIN_DATASET_SAMPLES_EFFECTIVE="${MIN_DATASET_SAMPLES:-500}"
  MIN_TEST_SAMPLES_EFFECTIVE="${MIN_TEST_SAMPLES:-500}"
  MIN_SOURCE_DATASETS_EFFECTIVE="${MIN_SOURCE_DATASETS:-4}"
  MIN_CONTENT_DOMAINS_EFFECTIVE="${MIN_CONTENT_DOMAINS:-4}"
fi
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then
  # The generated calibration YAML contains absolute, reviewed bindings.  A
  # direct invocation must not re-enable generic manifest/root overrides.
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
  "${PYTHON_BIN}" -c 'import sys; from pathlib import Path; from scripts.server.analyze_image_watermark_threshold_calibration import _validate_calibration_config; _validate_calibration_config(Path(sys.argv[1]).resolve()); print("threshold-calibration config gate: ready")' "${BENCHMARK_CONFIG}"
  "${PYTHON_BIN}" -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1], encoding="utf-8")); methods=[row for row in d.get("methods", []) if isinstance(row, dict) and row.get("id")=="editguard_wrapper" and row.get("enabled", True)]; actual=methods[0].get("base_url") if len(methods)==1 else None; expected=sys.argv[2]; print("threshold-calibration API URL gate:", "ready" if actual==expected else f"mismatch=config:{actual!r},runtime:{expected!r}"); raise SystemExit(actual!=expected)' "${BENCHMARK_CONFIG}" "${SCE_LOCGUARD_BASE_URL}"
fi
if [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
  unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
  "${PYTHON_BIN}" -c 'import sys; from pathlib import Path; from scripts.server.analyze_image_watermark_channel_vote_confirmation import _validate_confirmation_config; _validate_confirmation_config(Path(sys.argv[1]).resolve()); print("channel-vote confirmation config gate: ready")' "${BENCHMARK_CONFIG}"
  "${PYTHON_BIN}" - "${BENCHMARK_CONFIG}" "${SCE_LOCGUARD_BASE_URL}" "${RUN_DIR}" <<'PY'
import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1]).resolve()
base_url = sys.argv[2]
run_dir = Path(sys.argv[3]).resolve()
config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
methods = [
    row
    for row in config.get("methods", [])
    if isinstance(row, dict)
    and row.get("id") == "editguard_wrapper"
    and row.get("enabled", True)
]
configured_url = methods[0].get("base_url") if len(methods) == 1 else None
expected_output = Path(config["experiment"]["output_root"]).resolve()
candidate = config["channel_vote_confirmation"]["candidate"]
valid = (
    configured_url == base_url
    and expected_output == run_dir
    and candidate.get("candidate_id")
    == "recovery_threshold_0p34__channel_vote_2of3"
    and candidate.get("run_relative_path")
    == "confirmation-run/recovery_threshold_0p34__channel_vote_2of3"
)
print(
    "channel-vote confirmation binding gate:",
    "ready" if valid else "mismatch",
)
raise SystemExit(not valid)
PY
fi
if [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  unset COGNIGUARD_WATERMARK_DATASET_MANIFEST
  unset COGNIGUARD_DATASET_ROOTS_JSON
  unset COGNIGUARD_WATERMARK_BENCHMARK_CONFIG
  "${PYTHON_BIN}" - "${BENCHMARK_CONFIG}" "${RUN_DIR}/benchmark" "${RUN_CLASS}" "${SCE_LOCGUARD_BASE_URL}" <<'PY'
import sys
from pathlib import Path

import yaml

from scripts.server.image_watermark_redevelopment_protocol import (
    resolve_development_required_capabilities,
)

config_path = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
run_class = sys.argv[3]
base_url = sys.argv[4]
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
methods = [
    row
    for row in config.get("methods") or []
    if isinstance(row, dict)
    and row.get("enabled", True)
    and row.get("id") == "editguard_wrapper"
]
if len(methods) != 1 or methods[0].get("base_url") != base_url:
    raise SystemExit("Spatial-filter API URL binding differs from the config.")
required = resolve_development_required_capabilities(
    config_path,
    output,
    run_class=run_class,
)
print(
    "spatial-filter config gate: ready",
    required["localization_min_component_area_ratio"],
)
PY
fi
printf '%s\n' "${RUN_CLASS}" > "${RUN_DIR}/run-class.txt"

API_PID=""
archive_registry() {
  local snapshot_dir="${RUN_DIR}/source-registry-snapshot"
  mkdir -p -- "${snapshot_dir}"
  if [[ -d "${SCE_LOCGUARD_REGISTRY_DIR}" ]]; then
    if ! cp -a -- "${SCE_LOCGUARD_REGISTRY_DIR}/." "${snapshot_dir}/"; then
      echo "Warning: failed to archive source registry to ${snapshot_dir}." >&2
    fi
  fi
}
cleanup() {
  local status="${1:-$?}"
  trap - EXIT INT TERM
  set +e
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" 2>/dev/null
    wait "${API_PID}" 2>/dev/null
  fi
  archive_registry
  exit "${status}"
}
trap 'cleanup $?' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

PREFLIGHT_ARGS=(
  --project-root "${SCE_LOCGUARD_PROJECT_ROOT}"
  --output-root "${SCE_LOCGUARD_API_JOB_ROOT}"
  --asset-manifest "${ASSET_MANIFEST}"
  --benchmark-config "${BENCHMARK_CONFIG}"
  --expected-api-url "${SCE_LOCGUARD_BASE_URL}"
  --hf-cache "${HF_HOME}"
  --model-id "${SCE_LOCGUARD_INPAINT_MODEL_ID:-stable-diffusion-v1-5/stable-diffusion-inpainting}"
  --model-revision "${SCE_LOCGUARD_INPAINT_MODEL_REVISION:-}"
  --min-dataset-samples "${MIN_DATASET_SAMPLES_EFFECTIVE}"
  --min-test-samples "${MIN_TEST_SAMPLES_EFFECTIVE}"
  --min-source-datasets "${MIN_SOURCE_DATASETS_EFFECTIVE}"
  --min-content-domains "${MIN_CONTENT_DOMAINS_EFFECTIVE}"
  --require-linux
  --require-cuda
  --require-secret
  --require-shared-root
  --require-asset-hashes
  --require-hf-cache
  --require-dataset-files
  --require-license-metadata
  --require-deterministic
  --output-json "${RUN_DIR}/preflight.json"
)
if [[ -n "${COGNIGUARD_SHARED_ROOT:-}" ]]; then
  PREFLIGHT_ARGS+=(--shared-root "${COGNIGUARD_SHARED_ROOT}")
fi
if [[ -n "${COGNIGUARD_WATERMARK_DATASET_MANIFEST:-}" ]]; then
  PREFLIGHT_ARGS+=(--dataset-manifest "${COGNIGUARD_WATERMARK_DATASET_MANIFEST}")
fi

"${PYTHON_BIN}" "${SCE_LOCGUARD_PROJECT_ROOT}/scripts/server/preflight_image_watermark.py" "${PREFLIGHT_ARGS[@]}"
"${PYTHON_BIN}" -m pip freeze > "${RUN_DIR}/pip-freeze.txt"
nvidia-smi -q > "${RUN_DIR}/nvidia-smi.txt"
uname -a > "${RUN_DIR}/uname.txt"
DECLARED_INPUT_FILES=("${BENCHMARK_CONFIG}" "${ASSET_MANIFEST}")
if [[ -n "${PREREGISTRATION_RUN_CLASS}" ]]; then
  DECLARED_INPUT_FILES+=("${COGNIGUARD_PREREGISTRATION_CLAIM_PATH}")
fi
sha256sum "${DECLARED_INPUT_FILES[@]}" > "${RUN_DIR}/declared-input-files.sha256"
if command -v git >/dev/null 2>&1 && git -C "${SCE_LOCGUARD_PROJECT_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "${SCE_LOCGUARD_PROJECT_ROOT}" rev-parse HEAD > "${RUN_DIR}/git-revision.txt"
  git -C "${SCE_LOCGUARD_PROJECT_ROOT}" status --short > "${RUN_DIR}/git-status.txt"
fi

export RUN_PREFLIGHT=0
# The benchmark environment has already been sourced above.  Clear the file
# variable for the child launcher so it cannot source the same file again and
# overwrite the run-local paths or RUN_PREFLIGHT=0.
"${PYTHON_BIN}" - "${SCE_LOCGUARD_BASE_URL}" <<'PY'
import socket
import sys
from urllib.parse import urlsplit

parsed = urlsplit(sys.argv[1])
if parsed.scheme != "http" or not parsed.hostname or parsed.port is None:
    raise SystemExit(f"Invalid local API URL for port-ownership check: {sys.argv[1]!r}")
try:
    with socket.create_connection((parsed.hostname, parsed.port), timeout=0.5):
        pass
except OSError:
    raise SystemExit(0)
raise SystemExit(
    f"Refusing to start: API port is already occupied at {parsed.hostname}:{parsed.port}."
)
PY
SERVER_ENV_FILE="" bash "${SCE_LOCGUARD_PROJECT_ROOT}/scripts/server/start_image_watermark_api.sh" > "${RUN_DIR}/api.log" 2>&1 &
API_PID=$!

validate_api_instance() {
  local health_path="$1"
  "${PYTHON_BIN}" -m scripts.server.validate_image_watermark_api_instance \
    --health-json "${health_path}" \
    --expected-nonce "${SCE_LOCGUARD_RUN_INSTANCE_NONCE}" \
    --expected-job-root "${SCE_LOCGUARD_API_JOB_ROOT}"
}

ready=0
for _ in $(seq 1 90); do
  if ! kill -0 "${API_PID}" 2>/dev/null; then
    echo "Image-watermark API exited before becoming healthy; see ${RUN_DIR}/api.log" >&2
    tail -n 80 "${RUN_DIR}/api.log" >&2 || true
    exit 1
  fi
  if curl --fail --silent --show-error "${SCE_LOCGUARD_BASE_URL}/health" > "${RUN_DIR}/health.json"; then
    if ! validate_api_instance "${RUN_DIR}/health.json"; then
      echo "A process answered on the API port but did not match this run." >&2
      exit 1
    fi
    ready=1
    break
  fi
  sleep 2
done
if [[ "${ready}" != "1" ]]; then
  echo "Image-watermark API did not become healthy; see ${RUN_DIR}/api.log" >&2
  exit 1
fi
if ! kill -0 "${API_PID}" 2>/dev/null; then
  echo "Image-watermark API exited after its readiness attestation." >&2
  exit 1
fi
curl --fail --silent --show-error "${SCE_LOCGUARD_BASE_URL}/api/v1/capabilities" > "${RUN_DIR}/capabilities.json"
"${PYTHON_BIN}" -c 'import json,sys; p=sys.argv[1]; d=json.load(open(p, encoding="utf-8")); keys=("embed_real_pipeline_available","attack_real_pipeline_available","verify_real_pipeline_available","registry_secret_configured","paper_mode_ready","deterministic_mode_enabled","service_singleton"); missing=[k for k in keys if not d.get(k)]; print("capability gate:", "ready" if not missing else "missing="+",".join(missing)); raise SystemExit(bool(missing))' "${RUN_DIR}/capabilities.json"
if ! kill -0 "${API_PID}" 2>/dev/null; then
  echo "Image-watermark API exited during its capability gate." >&2
  exit 1
fi
curl --fail --silent --show-error "${SCE_LOCGUARD_BASE_URL}/health" > "${RUN_DIR}/health-after-capabilities.json"
validate_api_instance "${RUN_DIR}/health-after-capabilities.json"
if ! kill -0 "${API_PID}" 2>/dev/null; then
  echo "Image-watermark API exited after its capability attestation." >&2
  exit 1
fi
if (( MODE_COUNT == 0 )); then
  "${PYTHON_BIN}" -m protection.image_watermark.experiments.paper_benchmark \
    --config "${BENCHMARK_CONFIG}" \
    --validate-required-capabilities "${RUN_DIR}/capabilities.json" \
    --capabilities-method-id editguard_wrapper
  echo "formal required-capabilities gate: ready"
fi
if [[ "${DEV_TUNING_MODE}" == "1" ]]; then
  "${PYTHON_BIN}" -c 'import json,math,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); expected={"recovery_threshold":0.28,"tamper_area_threshold":0.001,"registry_hamming_radius":1}; bad=[f"{key}={d.get(key)!r}" for key,value in expected.items() if not (d.get(key)==value if isinstance(value,int) else isinstance(d.get(key),(int,float)) and math.isclose(float(d[key]),value,rel_tol=0.0,abs_tol=1e-12))]; print("frozen dev-tuning gate:", "ready" if not bad else "mismatch="+",".join(bad)); raise SystemExit(bool(bad))' "${RUN_DIR}/capabilities.json"
fi
if [[ "${THRESHOLD_CALIBRATION_MODE}" == "1" ]]; then
  if [[ -z "${CALIBRATION_EXPECTED_RECOVERY_THRESHOLD:-}" ]]; then
    echo "CALIBRATION_EXPECTED_RECOVERY_THRESHOLD is required in threshold-calibration mode." >&2
    exit 2
  fi
  "${PYTHON_BIN}" - "${RUN_DIR}/capabilities.json" "${CALIBRATION_EXPECTED_RECOVERY_THRESHOLD}" <<'PY'
import json
import math
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    capabilities = json.load(handle)
expected_exact = {
    "registry_hamming_radius": 1,
    "localization_postprocessing": "none",
    "deterministic_mode_enabled": True,
    "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 1,
    "localization_residual_threshold_rule": "abs_gt_recovery_threshold_per_channel",
}
mismatches = [
    f"{field}={capabilities.get(field)!r}"
    for field, expected in expected_exact.items()
    if type(capabilities.get(field)) is not type(expected)
    or capabilities.get(field) != expected
]
revision = capabilities.get("attack_model_revision")
if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
    mismatches.append(f"attack_model_revision={revision!r}")
for field, expected in {
    "recovery_threshold": float(sys.argv[2]),
    "tamper_area_threshold": 0.001,
}.items():
    observed = capabilities.get(field)
    if (
        type(observed) is not float
        or not math.isfinite(observed)
        or not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12)
    ):
        mismatches.append(f"{field}={observed!r}")
legacy = sorted(
    {
        "localization_rule_version",
        "localization_channel_count",
        "localization_channel_vote_rule",
        "localization_threshold_rule",
        "localization_channel_vote",
    }.intersection(capabilities)
)
if legacy:
    mismatches.append("legacy=" + ",".join(legacy))
print(
    "threshold-calibration gate:",
    "ready" if not mismatches else "mismatch=" + ",".join(mismatches),
)
raise SystemExit(bool(mismatches))
PY
fi
if [[ "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" ]]; then
  "${PYTHON_BIN}" - "${RUN_DIR}/capabilities.json" "${BENCHMARK_CONFIG}" <<'PY'
import json
import math
import re
import sys

import yaml

from protection.image_watermark.experiments.paper_benchmark import (
    BenchmarkError,
    validate_required_capabilities,
)

with open(sys.argv[1], encoding="utf-8") as handle:
    capabilities = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}
methods = [
    method
    for method in config.get("methods") or []
    if isinstance(method, dict)
    and method.get("enabled", True)
    and method.get("id") == "editguard_wrapper"
]
expected_exact = {
    "registry_hamming_radius": 1,
    "localization_postprocessing": "none",
    "deterministic_mode_enabled": True,
    "attack_model_id": "stable-diffusion-v1-5/stable-diffusion-inpainting",
    "localization_mask_rule_version": "editguard_residual_channel_vote_v2",
    "localization_residual_channels": 3,
    "localization_channel_aggregation": "k_of_3",
    "localization_channel_vote_min": 2,
    "localization_residual_threshold_rule": "abs_gt_recovery_threshold_per_channel",
}
mismatches = [
    f"{field}={capabilities.get(field)!r}"
    for field, expected in expected_exact.items()
    if type(capabilities.get(field)) is not type(expected)
    or capabilities.get(field) != expected
]
if len(methods) != 1:
    mismatches.append(f"configured_editguard_methods={len(methods)}")
else:
    try:
        validate_required_capabilities(
            methods[0], capabilities, require_declaration=True
        )
    except BenchmarkError as exc:
        mismatches.append(f"declared_capabilities={exc}")
revision = capabilities.get("attack_model_revision")
if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
    mismatches.append(f"attack_model_revision={revision!r}")
for field, expected in {
    "recovery_threshold": 0.34,
    "tamper_area_threshold": 0.001,
}.items():
    observed = capabilities.get(field)
    if (
        type(observed) is not float
        or not math.isfinite(observed)
        or not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12)
    ):
        mismatches.append(f"{field}={observed!r}")
legacy = sorted(
    {
        "localization_rule_version",
        "localization_channel_count",
        "localization_channel_vote_rule",
        "localization_threshold_rule",
        "localization_channel_vote",
    }.intersection(capabilities)
)
if legacy:
    mismatches.append("legacy=" + ",".join(legacy))
print(
    "channel-vote confirmation capability gate:",
    "ready" if not mismatches else "mismatch=" + ",".join(mismatches),
)
raise SystemExit(bool(mismatches))
PY
fi
if [[ "${SPATIAL_FILTER_MODE}" == "1" ]]; then
  "${PYTHON_BIN}" - "${RUN_DIR}/capabilities.json" "${BENCHMARK_CONFIG}" "${RUN_DIR}/benchmark" "${RUN_CLASS}" <<'PY'
import json
import sys
from pathlib import Path

from protection.image_watermark.experiments.paper_benchmark import (
    validate_required_capabilities,
)
from scripts.server.image_watermark_redevelopment_protocol import (
    resolve_development_required_capabilities,
)

capabilities = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = resolve_development_required_capabilities(
    Path(sys.argv[2]).resolve(),
    Path(sys.argv[3]).resolve(),
    run_class=sys.argv[4],
)
validate_required_capabilities(
    {"id": "editguard_wrapper", "required_capabilities": required},
    capabilities,
    require_declaration=True,
)
print("spatial-filter capability gate: ready")
PY
fi

BENCHMARK_ARGS=(
  --config "${BENCHMARK_CONFIG}"
  --output-dir "${RUN_DIR}/benchmark"
)
if [[ ( "${THRESHOLD_CALIBRATION_MODE}" == "1" || "${CHANNEL_VOTE_CONFIRMATION_MODE}" == "1" || "${SPATIAL_FILTER_MODE}" == "1" ) && "${BENCHMARK_RESUME:-0}" == "1" ]]; then
  echo "Threshold/confirmation candidate runs are immutable and cannot resume." >&2
  exit 2
elif [[ "${BENCHMARK_RESUME:-0}" == "1" ]]; then
  BENCHMARK_ARGS+=(--resume)
fi

cd -- "${SCE_LOCGUARD_PROJECT_ROOT}"
"${PYTHON_BIN}" -m protection.image_watermark.experiments.paper_benchmark "${BENCHMARK_ARGS[@]}"
