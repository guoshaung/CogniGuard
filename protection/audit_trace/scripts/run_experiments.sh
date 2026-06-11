#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
python -m experiments.ablation.run_all_ablations --mode experiment
