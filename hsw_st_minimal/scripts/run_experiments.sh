#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python src/main.py --config configs/config.yaml --mode experiment
