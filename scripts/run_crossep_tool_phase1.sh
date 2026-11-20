#!/usr/bin/env bash
# Phase-1 only driver for CROSSEP-TOOL (NO-MEM and ACE).
# Does not run the 12 cross-environment pairs.
# Reads the key from mmfopd-repro/.env and never prints it.
#
# Usage:
#   bash scripts/run_crossep_tool_phase1.sh ping
#   bash scripts/run_crossep_tool_phase1.sh smoke no_memory
#   bash scripts/run_crossep_tool_phase1.sh smoke ace
#   bash scripts/run_crossep_tool_phase1.sh full no_memory
#   bash scripts/run_crossep_tool_phase1.sh full ace
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="${ROOT}/EvoMemBench/Cross-Episode-Execution/Tool-Using/CROSSEP-TOOL"
MODE="${1:-}"
WHICH="${2:-}"

if [[ -z "${MODE}" ]]; then
  echo "usage: $0 ping|smoke|full [no_memory|ace]" >&2
  exit 1
fi

python3 - "${ROOT}" "${TOOL}" << 'PY'
import os, sys
from pathlib import Path
root = Path(sys.argv[1])
tool = Path(sys.argv[2])
env_path = root / ".env"
if not env_path.exists():
    print("MISSING_ENV_FILE", file=sys.stderr)
    sys.exit(3)
vals = {}
for raw in env_path.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    vals[k.strip()] = v.strip().strip('"').strip("'")
key = vals.get("XAI_API_KEY") or os.environ.get("XAI_API_KEY") or ""
model = vals.get("XAI_MODEL") or os.environ.get("XAI_MODEL") or ""
base = (vals.get("XAI_BASE_URL") or os.environ.get("XAI_BASE_URL") or "https://api.x.ai/v1").rstrip("/")
if not key:
    print("MISSING_KEY", file=sys.stderr)
    sys.exit(3)
if not model or model in {"grok-2-latest", "TODO", "..."}:
    print("MISSING_MODEL", file=sys.stderr)
    sys.exit(4)
out = tool / ".env"
out.write_text(
    "\n".join(
        [
            "LLM_BACKEND=xai",
            f"XAI_API_KEY={key}",
            f"XAI_BASE_URL={base}",
            f"XAI_MODEL={model}",
            f"DEEPSEEK_API_KEY={key}",
            f"DEEPSEEK_BASE_URL={base}",
            f"BATCH_MODEL={model}",
            f"GROK_API_KEY={key}",
            "",
        ]
    )
)
os.chmod(out, 0o600)
print(f"materialized tool env model={model} key_len={len(key)}")
PY

CONDA_BASE="${CONDA_BASE:-$HOME/miniconda3}"
# shellcheck source=/dev/null
source "${CONDA_BASE}/etc/profile.d/conda.sh"

if [[ "${MODE}" == "ping" ]]; then
  conda activate CROSSEP-TOOL
  cd "${TOOL}"
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  python - << 'PY'
import os
from bfcl_eval.memory.ark_client import ArkBatchClient
client = ArkBatchClient(api_key=os.environ["DEEPSEEK_API_KEY"])
resp, dt = client.chat_completions(
    os.environ["BATCH_MODEL"],
    [{"role": "user", "content": "Reply with exactly: PONG"}],
)
text = resp.choices[0].message.content or ""
usage = getattr(resp, "usage", None)
print("ping_text=", text)
print("ping_seconds=", round(dt, 3))
print("ping_usage=", usage)
PY
  exit 0
fi

if [[ "${WHICH}" != "no_memory" && "${WHICH}" != "ace" ]]; then
  echo "second arg must be no_memory or ace" >&2
  exit 1
fi

cd "${TOOL}"
if [[ "${MODE}" != "smoke" && "${MODE}" != "full" ]]; then
  echo "mode must be ping, smoke, or full" >&2
  exit 1
fi

TS="$(date +%Y%m%d_%H%M%S)"
if [[ "${WHICH}" == "no_memory" ]]; then
  conda activate bfcl
  if [[ "${MODE}" == "smoke" ]]; then
    bash scripts/run_eval_no_memory_inenv_fc.sh \
      --run-name "xai_${MODE}_nomem_${TS}" \
      --limit-per-subset 1
  else
    bash scripts/run_eval_no_memory_inenv_fc.sh \
      --run-name "xai_${MODE}_nomem_${TS}"
  fi
  exit 0
fi

# ACE phase 1 only. The official all-crossenv script also launches 12 pairs.
conda activate CROSSEP-TOOL
set -a
# shellcheck source=/dev/null
source .env
set +a
RUN_NAME="xai_${MODE}_ace_${TS}"
BASE_DIR="cross_episode_results/runs/${RUN_NAME}"
mkdir -p "${BASE_DIR}/logs"
SUBSETS=(gorilla_fs vehicle_control trading_bot travel_api)
IDS_DIR="bfcl_eval/scripts/cross_episode/ids"
LIMIT_PER_SUBSET=""
if [[ "${MODE}" == "smoke" ]]; then
  LIMIT_PER_SUBSET="2"
fi
pids=()
names=()
for subset in "${SUBSETS[@]}"; do
  ids="$(python3 -c \
    "import json,sys; d=json.load(open(sys.argv[1]))['multi_turn_ours']; n=int(sys.argv[2]) if sys.argv[2] else len(d); print(','.join(d[:n]))" \
    "${IDS_DIR}/ids_${subset}.json" "${LIMIT_PER_SUBSET}")"
  log="${BASE_DIR}/logs/phase1_${subset}.log"
  (
    python -m bfcl_eval.scripts.cross_episode.run_batch_generate \
      --num-workers 1 \
      --output-dir "${BASE_DIR}/phase1" \
      --run-name "${subset}" \
      --memory-type ace \
      --mode FC \
      --ids "${ids}" \
    && python -m bfcl_eval.scripts.cross_episode.run_batch_evaluate \
      --input "${BASE_DIR}/phase1/${subset}/result.jsonl" \
      --num-workers 4
  ) >"${log}" 2>&1 &
  pids+=("$!")
  names+=("${subset}")
  echo "started ${subset} pid=$!"
done
failed=0
for i in "${!pids[@]}"; do
  if ! wait "${pids[$i]}"; then
    echo "FAILED ${names[$i]}"
    failed=1
  else
    echo "done ${names[$i]}"
  fi
done
if [[ "${failed}" -eq 0 ]]; then
  python3 scripts/merge_summaries.py "${BASE_DIR}" --title "ace | in-env phase1 only"
fi
exit "${failed}"
