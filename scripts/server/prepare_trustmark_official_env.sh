#!/usr/bin/env bash
set -euo pipefail

# This is an explicit staging script, not part of a formal benchmark run.
# Official TrustMark downloads its checksum-pinned Q assets on first model load.
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${PROJECT_ROOT}/var/cache/python}"
VENV_DIR="${TRUSTMARK_VENV_DIR:-${PROJECT_ROOT}/.venv-trustmark-official}"
CONFIG_PATH="${TRUSTMARK_CONFIG:-${PROJECT_ROOT}/protection/supporting/image_watermark/configs/trustmark_official_baseline.yaml}"
PREFLIGHT_REPORT="${TRUSTMARK_PREFLIGHT_REPORT:-${PROJECT_ROOT}/var/outputs/trustmark_official_preflight.json}"
BOOTSTRAP_CONDA="${TRUSTMARK_BOOTSTRAP_CONDA:-0}"
REQUESTED_PYTHON="${TRUSTMARK_PYTHON_VERSION:-3.10}"
PYPI_INDEX_URL="${TRUSTMARK_PYPI_INDEX_URL:-https://pypi.org/simple}"
TORCH_INDEX_URL="${TRUSTMARK_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
PIP_TIMEOUT="${TRUSTMARK_PIP_TIMEOUT:-120}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

if [[ "${BOOTSTRAP_CONDA}" != "0" && "${BOOTSTRAP_CONDA}" != "1" ]]; then
  echo "TRUSTMARK_BOOTSTRAP_CONDA must be exactly 0 or 1." >&2
  exit 2
fi

validate_python() {
  local candidate="$1"
  if [[ ! -x "${candidate}" ]] && ! command -v "${candidate}" >/dev/null 2>&1; then
    echo "TrustMark preparation failed: Python executable not found: ${candidate}" >&2
    return 2
  fi
  "${candidate}" - <<'PY'
import sys

if sys.version_info[:2] not in {(3, 10), (3, 11)}:
    raise SystemExit(
        "TrustMark official environment requires Python 3.10 or 3.11; "
        f"observed {sys.version.split()[0]}"
    )
print(f"validated_python={sys.version.split()[0]}")
PY
}

if [[ "${BOOTSTRAP_CONDA}" == "1" ]]; then
  if [[ "${REQUESTED_PYTHON}" != "3.10" && "${REQUESTED_PYTHON}" != "3.11" ]]; then
    echo "TRUSTMARK_PYTHON_VERSION must be 3.10 or 3.11." >&2
    exit 2
  fi
  CONDA_BIN="${CONDA_BIN:-conda}"
  if ! command -v "${CONDA_BIN}" >/dev/null 2>&1; then
    echo "Conda bootstrap requested but CONDA_BIN was not found: ${CONDA_BIN}" >&2
    exit 2
  fi
  if [[ -e "${VENV_DIR}" ]]; then
    echo "Refusing to overwrite existing isolated runtime: ${VENV_DIR}" >&2
    exit 2
  fi
  "${CONDA_BIN}" create --yes --prefix "${VENV_DIR}" \
    --override-channels --channel https://repo.anaconda.com/pkgs/main \
    --no-default-packages "python=${REQUESTED_PYTHON}" pip
  RUNTIME_PYTHON="${VENV_DIR}/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3.10}"
  validate_python "${PYTHON_BIN}"
  if [[ -e "${VENV_DIR}" ]]; then
    echo "Refusing to overwrite existing isolated runtime: ${VENV_DIR}" >&2
    exit 2
  fi
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  RUNTIME_PYTHON="${VENV_DIR}/bin/python"
fi

validate_python "${RUNTIME_PYTHON}"
PIP_INDEX_URL="${PYPI_INDEX_URL}" PIP_DEFAULT_TIMEOUT="${PIP_TIMEOUT}" \
  "${RUNTIME_PYTHON}" -m pip install --upgrade pip setuptools wheel
# Install the audited CUDA wheel pair from PyTorch's official index. This is
# separate from the remaining requirements so a host-level mirror cannot
# silently substitute CPU-only or differently built wheels.
PIP_DEFAULT_TIMEOUT="${PIP_TIMEOUT}" \
  "${RUNTIME_PYTHON}" -m pip install \
  torch==2.1.2 torchvision==0.16.2 --index-url "${TORCH_INDEX_URL}"
PIP_INDEX_URL="${PYPI_INDEX_URL}" PIP_DEFAULT_TIMEOUT="${PIP_TIMEOUT}" \
  "${RUNTIME_PYTHON}" -m pip install --no-build-isolation \
  -r "${PROJECT_ROOT}/protection/supporting/image_watermark/requirements-trustmark-official.txt"

if [[ "${TRUSTMARK_STAGE_OFFICIAL_ASSETS:-0}" == "1" ]]; then
  # Network use is opt-in and isolated to staging. The formal run must use the
  # preflighted local assets and performs no downloader/fallback substitution.
  "${RUNTIME_PYTHON}" - <<'PY'
from trustmark import TrustMark

TrustMark(
    use_ECC=True,
    verbose=True,
    secret_len=100,
    model_type="Q",
    encoding_type=TrustMark.Encoding.BCH_5,
    concentrate_wm_region=1.0,
    loadRemover=False,
    loadBBoxDetector=False,
)
PY
fi

cd "${PROJECT_ROOT}"
"${RUNTIME_PYTHON}" scripts/server/preflight_trustmark_official.py \
  --config "${CONFIG_PATH}" \
  --load-model \
  --output "${PREFLIGHT_REPORT}"
