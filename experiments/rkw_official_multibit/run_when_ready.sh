#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
root=$PWD
run_id=${1:-demo-bf16-split}
out="$root/$run_id"
mkdir -p "$out"
exec > >(tee -a "$out/run.log") 2>&1
for model in encoder0 encoder1 decoder; do
  while ! test -f "$model/config.json" || [ "$(find "$model" -maxdepth 1 \( -type f -o -type l \) -name '*.safetensors' | wc -l)" -lt "$(case "$model" in decoder) echo 1;; *) echo 7;; esac)"; do sleep 60; done
done
while ! "$root/env/bin/python" -c 'import torch,transformers,accelerate,datasets; print(torch.ones(1,device="cuda",dtype=torch.bfloat16)+1)' > "$out/cuda_check.log" 2>&1; do sleep 60; done
while ! test -f "$root/mpnet/model.safetensors" || ! test -f "$root/tokenizer/tokenizer.json"; do sleep 60; done
for phase in verify generate score; do
 "$root/env/bin/python" -u "$root/run_official_qwen.py" --upstream "$root/upstream" --weights "$root" --out "$out" --phase "$phase"
done
