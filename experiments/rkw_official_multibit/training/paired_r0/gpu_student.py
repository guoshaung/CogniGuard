"""Train paired students and freely generate held-out answers."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import peft
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from train import train


def read_rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    lock = json.loads((HERE / "GPU_LOCK.json").read_bytes())
    for name, digest in lock["model"].items():
        with (args.model / name).open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == digest
    for name, digest in lock["data"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest
    args.out.mkdir(exist_ok=False)
    torch.set_num_threads(2)
    set_seed(lock["seed"])
    start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    base = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16, device_map={"": "cuda:0"})
    torch.cuda.synchronize()
    loaded = perf_counter() - start
    training = read_rows(HERE / "train.jsonl")
    public = [(row["id"], row["prompt"]) for row in read_rows(HERE / "evaluate.jsonl")]
    inputs = tokenizer([prompt for _, prompt in public], padding=True, return_tensors="pt").to("cuda:0")

    def evaluate(arm, model, receipt=None):
        model.eval()
        start = perf_counter()
        with torch.inference_mode():
            results = model.generate(**inputs, max_new_tokens=lock["max_new_tokens"],
                                     do_sample=False, pad_token_id=tokenizer.pad_token_id)
        torch.cuda.synchronize()
        seconds = perf_counter() - start
        outputs = results[:, inputs.input_ids.shape[1]:].tolist()
        eos = model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        with (args.out / f"{arm}.jsonl").open("x", encoding="utf8") as stream:
            for (identifier, _), ids in zip(public, outputs, strict=True):
                stop = next((i for i, token in enumerate(ids) if token in eos), len(ids))
                row = dict(id=identifier, text=tokenizer.decode(ids[:stop], skip_special_tokens=True),
                           tokens=stop, natural_eos=stop < len(ids))
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        cost = dict(train=receipt, inference_seconds=seconds, load_seconds=loaded,
                    gpu_peak_mib=torch.cuda.max_memory_allocated() / 1024**2)
        (args.out / f"{arm}_cost.json").write_text(json.dumps(cost, indent=2) + "\n")
        print(arm, cost, flush=True)

    def fit(model, field, epochs):
        examples = []
        for row in training:
            prompt = tokenizer.encode(row["prompt"], add_special_tokens=False)
            target = tokenizer.encode(row[field], add_special_tokens=False) + [tokenizer.eos_token_id]
            assert len(prompt) + len(target) <= 256
            examples.append((prompt + target, len(prompt)))
        size = lock["batch"]
        batches = [examples[i:i + size] for _ in range(epochs) for i in range(0, len(examples), size)]
        torch.cuda.reset_peak_memory_stats()
        return train(model, None, batches, dict(pad_id=tokenizer.pad_token_id, learning_rate=lock["lr"]),
                     torch, "cuda:0")

    evaluate("base", base)
    for arm, field in (("clean", "target_clean"), ("rkw", "target_marked")):
        set_seed(lock["seed"])
        adapter = peft.LoraConfig(task_type="CAUSAL_LM", r=lock["lora_rank"], lora_alpha=16,
                                  target_modules=["q_proj", "v_proj"])
        student = peft.get_peft_model(base, adapter)
        receipt = fit(student, field, lock["epochs"])
        evaluate(arm, student, receipt)
        student.save_pretrained(args.out / f"{arm}_adapter")
        if arm == "rkw":
            final = fit(student, "target_clean", lock["clean_extra_epochs"])
            evaluate("rkw_then_clean", student, final)
            student.save_pretrained(args.out / "rkw_then_clean_adapter")
        base = student.unload()


if __name__ == "__main__":
    main()
