#!/usr/bin/env bash
set -euo pipefail

# Install the pinned official source and dependencies into an explicitly named,
# dedicated virtualenv.  Checkpoints are never downloaded by this script.

if [[ $# -ne 1 ]]; then
  echo "usage: VENV=/absolute/dedicated-venv PYTHON=/absolute/dedicated-venv/bin/python $0 /absolute/path/to/watermark-anything" >&2
  exit 64
fi
: "${VENV:?set VENV to the absolute dedicated WAM virtualenv}"
: "${PYTHON:?set PYTHON to the absolute Python executable inside that virtualenv}"

repo_dir="$1"
commit="2c08af04d037d5667c02f6ddebbda9ff04581c3e"
repo_url="https://github.com/facebookresearch/watermark-anything.git"
pytorch_index_url="${PYTORCH_INDEX_URL:-https://download.pytorch.org/whl/cu121}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${VENV}" != /* || "${PYTHON}" != /* || "${repo_dir}" != /* ]]; then
  echo "VENV, PYTHON, and repository path must all be absolute" >&2
  exit 64
fi
if [[ ! -d "${VENV}" || ! -x "${PYTHON}" ]]; then
  echo "the dedicated VENV/PYTHON does not exist or is not executable" >&2
  exit 69
fi
venv_real="$(cd "${VENV}" && pwd -P)"
if [[ "$(basename "${venv_real}")" == ".venv-server" ]]; then
  echo "refusing CogniGuard's main .venv-server; use a dedicated WAM venv" >&2
  exit 64
fi

mapfile -t python_runtime < <(
  "${PYTHON}" -c 'import pathlib, sys; print(pathlib.Path(sys.prefix).resolve()); print(pathlib.Path(sys.base_prefix).resolve()); print(pathlib.Path(sys.executable).resolve())'
)
if [[ "${python_runtime[0]}" != "${venv_real}" ]]; then
  echo "PYTHON sys.prefix does not match VENV: ${python_runtime[0]} != ${venv_real}" >&2
  exit 64
fi
if [[ "${python_runtime[0]}" == "${python_runtime[1]}" ]]; then
  echo "PYTHON is not running inside a virtualenv" >&2
  exit 64
fi

if [[ -e "${repo_dir}" ]]; then
  if [[ "${WAM_REUSE_PINNED_REPO:-0}" != "1" || ! -d "${repo_dir}/.git" ]]; then
    echo "refusing existing path; set WAM_REUSE_PINNED_REPO=1 only for an audited existing clone: ${repo_dir}" >&2
    exit 73
  fi
  observed="$(git -C "${repo_dir}" rev-parse HEAD)"
  status="$(git -C "${repo_dir}" status --porcelain --untracked-files=all)"
  if [[ "${observed}" != "${commit}" || -n "${status}" ]]; then
    echo "existing WAM clone is not the exact clean pinned checkout" >&2
    exit 65
  fi
else
  git clone --filter=blob:none "${repo_url}" "${repo_dir}"
  git -C "${repo_dir}" checkout --detach "${commit}"
fi

"${PYTHON}" -m pip install \
  --index-url "${pytorch_index_url}" \
  torch==2.5.1 torchvision==0.20.1
"${PYTHON}" -m pip install -r "${script_dir}/wam_official_requirements.txt"

"${PYTHON}" -c 'from importlib.metadata import version; required={"torch":"2.5.1","torchvision":"0.20.1","numpy":"1.26.4","Pillow":"10.4.0"}; observed={name:version(name).split("+",1)[0] for name in required}; assert observed == required, "pinned runtime verification failed: %r" % (observed,); print(observed)'

echo "Official WAM source ready at ${repo_dir}"
echo "Dedicated runtime: ${python_runtime[2]}"
echo "PyTorch wheel index: ${pytorch_index_url}"
echo "Checkpoint was NOT downloaded. Supply wam_mit.pth, then run:"
echo "${PYTHON} -m protection.supporting.image_watermark.official_baselines.wam_official_preflight --repo-root '${repo_dir}' --checkpoint /path/to/wam_mit.pth --device cuda"
