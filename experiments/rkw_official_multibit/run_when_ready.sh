#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
root=$PWD
out="$root/demo-bf16-split"
mkdir -p "$out"
exec > >(tee -a "$out/run.log") 2>&1
ready() {
  for model in encoder0 encoder1; do
    test -s "$model/config.json" && test -s "$model/model.safetensors.index.json" || return 1
    for i in 1 2 3 4 5 6 7; do
      test -s "$model/$(printf 'model-%05d-of-00007.safetensors' "$i")" || return 1
    done
  done
  test -s decoder/model.safetensors && test -s decoder/config.json &&
    test -s tokenizer/tokenizer.json && test -s tokenizer/tokenizer_config.json &&
    test -s mpnet/config.json && test -s mpnet/tokenizer.json && test -s mpnet/model.safetensors
}
while ! ready; do sleep 60; done
while ! "$root/env/bin/python" -c 'import torch,transformers,accelerate,datasets; print(torch.ones(1,device="cuda",dtype=torch.bfloat16)+1)' > "$out/cuda_check.log" 2>&1; do sleep 60; done
for phase in verify generate score; do
 "$root/env/bin/python" -u "$root/run_official_qwen.py" --upstream "$root/upstream" --weights "$root" --out "$out" --phase "$phase"
done
