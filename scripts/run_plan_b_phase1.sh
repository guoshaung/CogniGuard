#!/usr/bin/env bash
# Plan B phase-1 driver. NO-MEM and ReasoningBank on the DeepSeek official API.
# Runs only the in-environment phase. Does not launch the 12 cross-environment pairs.
# Reads mmfopd-repro/.env, materializes CROSSEP-TOOL/.env, and deletes that copy on exit.
# Never prints secret values.
#
# Usage:
#   bash scripts/run_plan_b_phase1.sh smoke [no_memory|reasoning_bank|both]
#   bash scripts/run_plan_b_phase1.sh full  [no_memory|reasoning_bank|both]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="${ROOT}/EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL"
MODE="${1:-}"
WHICH="${2:-both}"

if [[ "${MODE}" != "smoke" && "${MODE}" != "full" ]]; then
  echo "usage: $0 smoke|full [no_memory|reasoning_bank|both]" >&2
  exit 1
fi
if [[ "${WHICH}" != "no_memory" && "${WHICH}" != "reasoning_bank" && "${WHICH}" != "both" ]]; then
  echo "second arg must be no_memory, reasoning_bank, or both" >&2
  exit 1
fi

cleanup_tool_env() {
  rm -f "${TOOL}/.env"
  unset DEEPSEEK_API_KEY DASHSCOPE_API_KEY BATCH_MODEL DEEPSEEK_USAGE_LOG || true
}
trap cleanup_tool_env EXIT INT TERM

python3 - "${ROOT}" "${TOOL}" << 'PY'
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tool = Path(sys.argv[2])
src = root / ".env"
if not src.is_file():
    print("MISSING_PARENT_ENV", file=sys.stderr)
    sys.exit(3)
vals = {}
for raw in src.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    vals[key.strip()] = value.strip().strip('"').strip("'")
required = [
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_BASE_URL",
]
missing = [name for name in required if not vals.get(name) or "XXXX" in vals[name]]
if missing:
    print("MISSING " + ",".join(missing), file=sys.stderr)
    sys.exit(3)
if vals["DEEPSEEK_MODEL"] != "deepseek-flash":
    print("UNEXPECTED_MODEL " + vals["DEEPSEEK_MODEL"], file=sys.stderr)
    sys.exit(4)
lines = [
    "LLM_BACKEND=deepseek",
    f"DEEPSEEK_API_KEY={vals['DEEPSEEK_API_KEY']}",
    f"DEEPSEEK_BASE_URL={vals['DEEPSEEK_BASE_URL'].rstrip('/')}",
    f"DEEPSEEK_MODEL={vals['DEEPSEEK_MODEL']}",
    f"BATCH_MODEL={vals['DEEPSEEK_MODEL']}",
    f"DASHSCOPE_API_KEY={vals['DASHSCOPE_API_KEY']}",
    f"DASHSCOPE_BASE_URL={vals['DASHSCOPE_BASE_URL'].rstrip('/')}",
    "DASHSCOPE_EMBED_MODEL=text-embedding-v4",
    "",
]
out = tool / ".env"
out.write_text("\n".join(lines))
os.chmod(out, 0o600)
print(
    "materialized"
    f" model={vals['DEEPSEEK_MODEL']}"
    f" deepseek_len={len(vals['DEEPSEEK_API_KEY'])}"
    f" dashscope_len={len(vals['DASHSCOPE_API_KEY'])}"
    " embed=text-embedding-v4"
)
PY

TS="$(date +%Y%m%d_%H%M%S)"
USAGE_DIR="${ROOT}/artifacts/usage"
mkdir -p "${USAGE_DIR}"
MANIFEST="${USAGE_DIR}/last_${MODE}_manifest.txt"
{
  echo "mode=${MODE}"
  echo "which=${WHICH}"
  echo "started_epoch=$(date +%s)"
  echo "started_local=$(date '+%Y-%m-%d %H:%M:%S %Z')"
} > "${MANIFEST}"

run_nomem() {
  local tag="ds_${MODE}_nomem_${TS}"
  local usage="${USAGE_DIR}/${tag}.jsonl"
  local driver_log="${USAGE_DIR}/${tag}.driver.log"
  : > "${usage}"
  export DEEPSEEK_USAGE_LOG="${usage}"
  echo "ARM no_memory"
  echo "USAGE_LOG ${usage}"
  cd "${TOOL}"
  if [[ "${MODE}" == "smoke" ]]; then
    bash scripts/run_eval_no_memory_inenv_fc.sh \
      --run-name "${tag}" \
      --limit-per-subset 1
  else
    bash scripts/run_eval_no_memory_inenv_fc.sh \
      --run-name "${tag}"
  fi
}

run_rb() {
  local tag="ds_${MODE}_rb_${TS}"
  local usage="${USAGE_DIR}/${tag}.jsonl"
  local limit=""
  local inner base subset ids log
  local pids="" names="" failed="" pid name idx
  if [[ "${MODE}" == "smoke" ]]; then
    limit="2"
  fi
  : > "${usage}"
  export DEEPSEEK_USAGE_LOG="${usage}"
  echo "ARM reasoning_bank"
  echo "USAGE_LOG ${usage}"
  echo "PHASE1_ONLY"

  local conda_base
  conda_base="$(conda info --base 2>/dev/null || echo "${HOME}/miniconda3")"
  # shellcheck source=/dev/null
  source "${conda_base}/etc/profile.d/conda.sh"
  conda activate CROSSEP-TOOL
  cd "${TOOL}"
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  export DEEPSEEK_USAGE_LOG="${usage}"

  inner="$(date +%Y%m%d_%H%M%S)"
  base="cross_episode_results/runs/${tag}_reasoning_bank_${inner}"
  mkdir -p "${base}/logs"
  echo "BASE_DIR ${base}"

  for subset in gorilla_fs vehicle_control trading_bot travel_api; do
    ids="$(
      LIMIT="${limit}" SUBSET="${subset}" python3 - << 'PY'
import json
import os
from pathlib import Path

subset = os.environ["SUBSET"]
limit = os.environ.get("LIMIT") or ""
path = Path("bfcl_eval/scripts/cross_episode/ids") / f"ids_{subset}.json"
rows = json.loads(path.read_text())["multi_turn_ours"]
count = int(limit) if limit else len(rows)
print(",".join(rows[:count]))
PY
    )"
    log="${base}/logs/phase1_${subset}.log"
    (
      python -m bfcl_eval.scripts.cross_episode.run_batch_generate \
        --num-workers 1 \
        --output-dir "${base}/phase1" \
        --run-name "${subset}" \
        --memory-type reasoning_bank \
        --mode FC \
        --ids "${ids}" \
      && python -m bfcl_eval.scripts.cross_episode.run_batch_evaluate \
        --input "${base}/phase1/${subset}/result.jsonl" \
        --num-workers 4
    ) >"${log}" 2>&1 &
    pids="${pids} $!"
    names="${names} ${subset}"
    echo "  started ${subset} pid $! log ${log}"
  done

  idx=0
  for pid in ${pids}; do
    idx=$((idx + 1))
    name="$(echo ${names} | awk -v i="${idx}" '{print $i}')"
    if ! wait "${pid}"; then
      failed="${failed} ${name}"
      echo "[Phase 1] FAILED: ${name} — see ${base}/logs/phase1_${name}.log"
    else
      echo "[Phase 1] done: ${name}"
    fi
  done

  python3 scripts/merge_summaries.py "${base}" --title "ReasoningBank | in-env phase 1 only"
  if [[ -n "${failed}" ]]; then
    echo "[Phase 1] failed subsets:${failed}"
    return 1
  fi
}

run_and_record() {
  local arm="$1"
  local started ended rc log_file
  started="$(date +%s)"
  set +e
  if [[ "${arm}" == "no_memory" ]]; then
    run_nomem
  else
    run_rb
  fi
  rc=$?
  set -e
  ended="$(date +%s)"
  {
    echo "${arm}_exit=${rc}"
    echo "${arm}_started_epoch=${started}"
    echo "${arm}_ended_epoch=${ended}"
    echo "${arm}_usage=${DEEPSEEK_USAGE_LOG:-}"
  } >> "${MANIFEST}"
  log_file="${USAGE_DIR}/ds_${MODE}_$([[ ${arm} == no_memory ]] && echo nomem || echo rb)_${TS}.driver.log"
  return "${rc}"
}

if [[ "${WHICH}" == "no_memory" || "${WHICH}" == "both" ]]; then
  run_and_record no_memory
fi
if [[ "${WHICH}" == "reasoning_bank" || "${WHICH}" == "both" ]]; then
  run_and_record reasoning_bank
fi

echo "MANIFEST ${MANIFEST}"
