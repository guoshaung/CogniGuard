"""Run paired generation-time embedding controls on frozen R0 prompts."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import types
from importlib.machinery import ModuleSpec
from dataclasses import replace
from pathlib import Path

TEXTSEAL_REVISION = "23f921f0646a22848934f0e6700de0671c28b889"


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--textseal", type=Path, required=True)
    parser.add_argument("--kgw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--split", choices=["train", "eval"], default="train")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HUB_OFFLINE"] = "1"
    sys.path[:0] = [str(args.textseal.resolve()), str(args.kgw.resolve())]
    revision = subprocess.check_output(["git", "-C", str(args.textseal), "rev-parse", "HEAD"], text=True).strip()
    if revision != TEXTSEAL_REVISION:
        raise ValueError(f"Unexpected TextSeal revision: {revision}")

    # Directly load upstream generation modules, avoiding optional post-hoc
    # dependencies imported by the package initializers.
    for name, directory in (("textseal", args.textseal / "textseal"),
                            ("textseal.watermarking", args.textseal / "textseal" / "watermarking")):
        package = types.ModuleType(name)
        package.__path__ = [str(directory.resolve())]
        package.__spec__ = ModuleSpec(name, None, is_package=True)
        sys.modules[name] = package

    import torch
    from textseal.watermarking.config import WatermarkConfig
    from textseal.watermarking.detector import TextSealDetector
    from textseal.watermarking.generator import TextSealGenerator, WmGenerator
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from watermark_detector import detect_full_text
    from watermark_logits_processor import KGWLogitsProcessor

    seed, token_budget, batch_size = 61126, 48, 4
    temperature, top_p = 0.8, 0.95
    kgw_key = "rkw-paired-r0-61126"
    torch.set_num_threads(4)
    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16, local_files_only=True).to(args.device).eval()
    load_seconds = time.perf_counter() - started
    model.config.eos_token_id = model.generation_config.eos_token_id
    kgw = KGWLogitsProcessor(model.config.vocab_size, gamma=0.25, delta=2, key=kgw_key, window_size=4)

    class CogniGuardKGWGenerator(WmGenerator):
        def sample_next(self, logits, context, temperature=0.8, top_p=0.95):
            return super().sample_next(kgw(context, logits), context, temperature, top_p)

    textseal_config = WatermarkConfig(watermark_type="textseal", secret_key=61126, ngram=3,
                                     scoring_method="v1", gumbel_val=0.1)
    generators = {
        "unmarked": WmGenerator(model, tokenizer, textseal_config),
        "kgw": CogniGuardKGWGenerator(model, tokenizer, replace(textseal_config, ngram=4)),
        "textseal": TextSealGenerator(model, tokenizer, textseal_config),
    }
    decoder = TextSealDetector(tokenizer, textseal_config)
    inputs = args.data / ("train.jsonl" if args.split == "train" else "generate.jsonl")
    records = read_rows(inputs)
    rows = [{"id": row["id"], "prompt": row["prompt"]} for row in records][:args.limit]
    if len({row["id"] for row in rows}) != len(rows) or not rows:
        raise ValueError("Generation rows require unique ids")
    args.output.mkdir(parents=True, exist_ok=False)
    protocol = {
        "generation_sha256": digest(inputs), "evaluation_sha256": digest(args.data / "evaluate.jsonl") if args.split == "eval" else None,
        "split": args.split, "limit": args.limit,
        "textseal_revision": revision, "kgw_source_sha256": digest(args.kgw / "watermark_logits_processor.py"),
        "kgw_detector_sha256": digest(args.kgw / "watermark_detector.py"),
        "model": str(args.model), "model_weights_sha256": digest(args.model / "model.safetensors"),
        "tokenizer_sha256": digest(args.model / "tokenizer.json"),
        "seed": seed, "device": args.device, "dtype": "bfloat16", "batch_size": batch_size,
        "token_budget": token_budget, "temperature": temperature, "top_p": top_p, "load_seconds": load_seconds,
        "kgw_gamma": .25, "kgw_delta": 2.0, "kgw_ngram": 4, "kgw_key": kgw_key, "textseal_key_a": textseal_config.key_a,
        "textseal_key_b": textseal_config.key_b, "textseal_ngram": 3, "textseal_key_a_probability": .1,
    }
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")

    with (args.output / "predictions.jsonl").open("w", encoding="utf-8") as destination:
        for start in range(0, len(rows), batch_size):
            batch = rows[start:start + batch_size]
            prompts = [row["prompt"] for row in batch]
            for arm, generator in generators.items():
                torch.manual_seed(seed + start)
                began = time.perf_counter()
                # Share the upstream generation loop across all sampling methods.
                answers = generator.generate(prompts, token_budget, temperature, top_p)
                batch_seconds = time.perf_counter() - began
                for row, answer in zip(batch, answers, strict=True):
                    began = time.perf_counter()
                    answer = tokenizer.decode(tokenizer.encode(answer, add_special_tokens=False), skip_special_tokens=True)
                    kgw_score = detect_full_text(answer, tokenizer, model.config.vocab_size, .25, kgw_key, 4, 3)
                    textseal_score = decoder.detect(answer)
                    result = dict(id=row["id"], arm=arm, text=answer,
                                  tokens=len(tokenizer.encode(answer, add_special_tokens=False)),
                                  batch_seconds=batch_seconds, batch_start=start, kgw=kgw_score,
                                  textseal=textseal_score, score_seconds=time.perf_counter() - began)
                    destination.write(json.dumps(result, default=lambda value: value.item(), ensure_ascii=False) + "\n")
                    destination.flush()
                print(arm, start, len(batch), round(batch_seconds, 3), flush=True)

    predictions = read_rows(args.output / "predictions.jsonl")
    if args.split == "train":
        predictions_by_id = {(row["id"], row["arm"]): row["text"] for row in predictions}
        for arm in ("kgw", "textseal"):
            with (args.output / f"train_{arm}.jsonl").open("x", encoding="utf-8") as stream:
                for row in records[:args.limit]:
                    scored = dict(row, target_clean=predictions_by_id[row["id"], "unmarked"],
                                  target_marked=predictions_by_id[row["id"], arm])
                    stream.write(json.dumps(scored, ensure_ascii=False) + "\n")
        return
    evaluation = {row["id"]: row for row in read_rows(args.data / "evaluate.jsonl")}
    for row in predictions:
        row["facts_regex_all"] = all(re.search(pattern, row["text"], re.I) for pattern in evaluation[row["id"]]["facts"])
        row["stratum"] = evaluation[row["id"]]["stratum"]
    summary = {}
    for arm in generators:
        part = [row for row in predictions if row["arm"] == arm]
        seconds = sum({row["batch_start"]: row["batch_seconds"] for row in part}.values())
        summary[arm] = {
            "rows": len(part),
            "tokens": sum(row["tokens"] for row in part),
            "generation_seconds": seconds,
            "score_seconds": sum(row["score_seconds"] for row in part),
            "kgw_z_gt_3": sum(row["kgw"]["is_watermarked"] for row in part),
            "textseal_p_lt_0_01": sum(row["textseal"]["detected"] for row in part),
            "facts_regex_all": sum(row["facts_regex_all"] for row in part),
            "per_stratum": {
                stratum: {"rows": len(group), "facts_regex_all": sum(row["facts_regex_all"] for row in group)}
                for stratum in sorted({row["stratum"] for row in part})
                for group in [[row for row in part if row["stratum"] == stratum]]
            },
        }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
