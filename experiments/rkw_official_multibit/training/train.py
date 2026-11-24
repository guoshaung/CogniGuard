"""Separate CPU-checkable trainers for response LoRA and token-logit distillation."""
import argparse
import json
from pathlib import Path
import random
import time

from prepare_data import file_sha, records


def train(model, teacher, batches, settings, torch, device):
    from torch.nn import functional as F

    model.train()
    if teacher is not None:
        teacher.eval()
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=settings["learning_rate"])
    losses, examples, targets = [], 0, 0
    started = time.perf_counter()
    for batch in batches:
        pad_id = settings["pad_id"]
        width = max(len(tokens) for tokens, _ in batch)
        tensors = [torch.full((len(batch), width), value, dtype=torch.long, device=device)
                   for value in (pad_id, 0, -100)]
        input_ids, attention, labels = tensors
        for index, (tokens, prompt_length) in enumerate(batch):
            input_ids[index, :len(tokens)] = torch.tensor(tokens, device=device)
            attention[index, :len(tokens)] = 1
            labels[index, prompt_length:len(tokens)] = input_ids[index, prompt_length:len(tokens)]
        output = model(input_ids=input_ids, attention_mask=attention, labels=labels, use_cache=False)
        loss = output.loss
        if teacher is not None:
            keep = labels[:, 1:].ne(-100)
            student_logits = output.logits[:, :-1, :][keep].float()
            with torch.no_grad():
                teacher_logits = teacher(input_ids=input_ids, attention_mask=attention, use_cache=False).logits
                teacher_logits = teacher_logits[:, :-1, :][keep].float()
            temperature = settings["temperature"]
            kl = F.kl_div(F.log_softmax(student_logits / temperature, dim=-1),
                          F.softmax(teacher_logits / temperature, dim=-1), reduction="batchmean")
            weight = settings["kl_weight"]
            loss = (1 - weight) * loss + weight * temperature**2 * kl
        if not torch.isfinite(loss).item():
            raise ValueError("Nonfinite training loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        if not any(parameter.grad is not None and parameter.grad.abs().max().item() > 0
                   for parameter in parameters):
            raise ValueError("Training step produced no nonzero gradient")
        optimizer.step()
        losses.append(float(loss.detach()))
        examples += len(batch)
        targets += int(labels.ne(-100).sum())
    return {"steps": len(losses), "examples": examples, "target_tokens": targets, "losses": losses,
            "trainable_parameters": sum(parameter.numel() for parameter in parameters),
            "train_seconds": time.perf_counter() - started}


def smoke(mode, torch, transformers, peft):
    from transformers import LlamaConfig, LlamaForCausalLM

    config = LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
                         num_attention_heads=2, num_key_value_heads=2, max_position_embeddings=64)
    model = LlamaForCausalLM(config)
    teacher = LlamaForCausalLM(config) if mode == "distill" else None
    if mode == "lora":
        model = peft.get_peft_model(
            model, peft.LoraConfig(task_type="CAUSAL_LM", r=2, lora_alpha=4, target_modules=["q_proj", "v_proj"])
        )
    settings = {"pad_id": 0, "learning_rate": 0.001, "temperature": 2.0, "kl_weight": 0.5}
    result = train(model, teacher, [[([1, 3, 7, 2], 2), ([1, 5, 9, 11, 2], 2)]], settings, torch, "cpu")
    return model, None, dict(result, scope="cpu_synthetic_smoke", seed=61126, mode=mode,
                             torch=torch.__version__, transformers=transformers.__version__, peft=peft.__version__)


def formal(mode, spec, paths, torch, transformers, peft):
    assert paths.spec and paths.split, "Formal runs require a frozen --spec and --split directory"
    manifest = json.loads((paths.split / "split_manifest.json").read_bytes())
    train_file = paths.split / "train.jsonl"
    if file_sha(train_file) != manifest["split_sha256"]["train"]:
        raise ValueError("Frozen training bytes differ from the split manifest")
    model_path = Path(spec["student_snapshot"])
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_path, local_files_only=True, use_fast=True)
    model = transformers.AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True).to(paths.device)
    teacher = None
    if mode == "distill":
        teacher_path = Path(spec["teacher_snapshot"])
        teacher_tokenizer = transformers.AutoTokenizer.from_pretrained(teacher_path, local_files_only=True, use_fast=True)
        same_tokenizer = (
            tokenizer.backend_tokenizer.to_str() == teacher_tokenizer.backend_tokenizer.to_str()
            and tokenizer.special_tokens_map == teacher_tokenizer.special_tokens_map
        )
        if not same_tokenizer:
            raise ValueError("Logit distillation requires aligned tokenization")
        teacher = transformers.AutoModelForCausalLM.from_pretrained(teacher_path, local_files_only=True).to(paths.device)
        if teacher.config.vocab_size != model.config.vocab_size:
            raise ValueError("Student and teacher output vocabularies differ")
    else:
        model = peft.get_peft_model(model, peft.LoraConfig(task_type="CAUSAL_LM", **spec["lora"]))
    max_length = spec["max_length"]
    if tokenizer.eos_token_id is None:
        raise ValueError("The frozen tokenizer requires an EOS token")
    examples = []
    for row in records(train_file):
        prompt = tokenizer.encode(row["prompt"], add_special_tokens=False)
        target = tokenizer.encode(row["target"], add_special_tokens=False) + [tokenizer.eos_token_id]
        if not prompt or len(prompt) + len(target) > max_length:
            raise ValueError(f"Empty prompt or over-length example: {row['id']}")
        examples.append((prompt + target, len(prompt)))
    batch_size = spec["batch_size"]
    epochs = spec["epochs"]
    if min(batch_size, epochs) < 1:
        raise ValueError("positive batch size and epochs required")

    def batches():
        rng = random.Random(spec["seed"])
        for _ in range(epochs):
            order = rng.sample(examples, len(examples))
            for offset in range(0, len(order), batch_size):
                yield order[offset:offset + batch_size]

    settings = dict(spec, pad_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    result = train(model, teacher, batches(), settings, torch, paths.device)
    return model, tokenizer, dict(result, scope="formal_training", seed=spec["seed"], mode=mode,
                                 split_manifest_sha256=file_sha(paths.split / "split_manifest.json"),
                                 spec_sha256=file_sha(paths.spec))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("distill", "lora"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--split", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Choose a fresh output directory")
    if args.smoke and (args.device != "cpu" or args.spec or args.split):
        parser.error("Smoke runs use only the built-in CPU fixtures")
    if not args.smoke and (args.spec is None or args.split is None):
        parser.error("A formal run requires --spec and --split")

    import peft
    import torch
    import transformers

    torch.set_num_threads(1)
    spec = {} if args.smoke else json.loads(args.spec.read_bytes())
    torch.manual_seed(61126 if args.smoke else spec["seed"])
    if args.smoke:
        model, tokenizer, result = smoke(args.mode, torch, transformers, peft)
    else:
        model, tokenizer, result = formal(args.mode, spec, args, torch, transformers, peft)
    args.out.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(args.out / "model")
    if tokenizer is not None:
        tokenizer.save_pretrained(args.out / "model")
    (args.out / "training_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
