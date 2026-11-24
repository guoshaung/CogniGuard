"""Run the official Qwen demo in stages using the checkpoint bytes and upstream sampler."""
import argparse
import hashlib
import json
import random
from pathlib import Path
import sys
import time

UPSTREAM = "7439ecee8891c6e8226f02fa8c1a650d3e10aaff"
MODEL_LOCK = json.loads(Path(__file__).with_name("CONFIG.json").read_bytes())["release_demo"]
TOKENIZER_REV = "a09a35458c702b33eeacc393d103063234e8bc28"
MPNET_REV = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
SEED = 61124
KEY = [1, 0] * 80
BATCH_SIZE = 4
MAX_GENERATED = 512


def verify_weights(root, upstream):
    for model, folder in zip(MODEL_LOCK["model_shards"], ("encoder0", "encoder1", "decoder"), strict=True):
        name = model["id"].split("/")[-1]
        metadata = json.loads((root / f"{name}.json").read_bytes())
        if metadata["sha"] != model["rev"]:
            raise ValueError(f"Revision mismatch for {name}")
        expected_total = 0
        for asset in metadata["siblings"]:
            if not asset["rfilename"].endswith(".safetensors"):
                continue
            file = root / folder / asset["rfilename"]
            expected_total += asset["size"]
            if not file.exists() or file.stat().st_size != asset["size"]:
                raise ValueError(f"Incomplete checkpoint {file}")
            with file.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != asset["lfs"]["sha256"]:
                raise ValueError(f"SHA256 mismatch for {file}")
            print(file.name, actual, flush=True)
        if expected_total != model["bytes"]:
            raise ValueError(f"Checkpoint size manifest mismatch for {name}")
    head = upstream / "ckpt" / "WatermarkDecoder-v_head.pt"
    if hashlib.sha256(head.read_bytes()).hexdigest() != MODEL_LOCK["decoder_head_sha256"]:
        raise ValueError("Decoder head SHA256 mismatch")


def write_record(stream, record):
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--phase", choices=["verify", "generate", "score"], required=True)
    parser.add_argument("--c4", type=Path)
    args = parser.parse_args()
    root = args.weights.resolve()
    upstream = args.upstream.resolve()
    if args.phase == "verify":
        verify_weights(root, upstream)
        return
    sys.path.insert(0, str(upstream))
    import numpy as np
    import torch
    from transformers import AutoConfig, AutoModel, AutoModelForCausalLM, AutoTokenizer, set_seed
    import gen_utils
    import model_utils
    import utils

    set_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    tokenizer.end_of_turn_token = None
    cuda = torch.device("cuda:0")
    args.out.mkdir(parents=True, exist_ok=True)
    generated_path = args.out / "candidates.jsonl"
    rng = random.Random(61125)
    native = None
    if args.c4:
        rows = json.loads(args.c4.read_bytes())
        native = [(index, row["text"]) for index, row in enumerate(rows[:256])
                  if len(gen_utils.split_sentence(row["text"])) >= 4][:24]
        if len(native) != 24:
            raise ValueError("Frozen C4 selection did not yield 24 records")
    cases = {}
    if native:
        cases = {idx: [rng.randrange(2) for _ in range(160)] for idx, _ in native}


    def load_bf16(folder, model_type, **kwargs):
        model_path = root / folder
        config = AutoConfig.from_pretrained(model_path, local_files_only=True)
        for field in ("dropout", "attention_dropout", "hidden_dropout", "activation_dropout"):
            if hasattr(config, field):
                setattr(config, field, 0.0)
        return model_type.from_pretrained(model_path, config=config, local_files_only=True,
                                          torch_dtype=torch.bfloat16, **kwargs).eval()

    if args.phase == "generate":
        started = time.perf_counter()
        model0 = load_bf16("encoder0", AutoModelForCausalLM, low_cpu_mem_usage=True).to(cuda)
        if torch.cuda.device_count() > 1:
            model1 = load_bf16("encoder1", AutoModelForCausalLM, low_cpu_mem_usage=True).to("cuda:1")
            placement = "two_cuda_devices"
        else:
            model1 = load_bf16("encoder1", AutoModelForCausalLM, device_map="auto",
                               max_memory={0: "11GiB", "cpu": "64GiB"})
            placement = model1.hf_device_map
        load_seconds = time.perf_counter() - started
        samples = []
        current = []
        for line in (upstream / "watermark_test_text.txt").read_text(encoding="utf-8").splitlines():
            if line.startswith("====="):
                samples.append("\n".join(current).strip())
                current.clear()
            else:
                current.append(line)
        if current:
            samples.append("\n".join(current).strip())
        assert len(samples) == 2
        sample_pairs = native if native else list(enumerate(samples))
        with generated_path.open("x", encoding="utf-8") as stream, torch.inference_mode():
            for sample_id, text in sample_pairs:
                intended = cases.get(sample_id, KEY)
                prompt = utils.gen_para_prompt(text, prompt_style="qwen", tokenizer=tokenizer)
                tokens = tokenizer(prompt, max_length=512, return_tensors="pt")
                prefix = tokens.input_ids.shape[1]
                ids = tokens.input_ids.to(cuda).repeat(BATCH_SIZE, 1)
                mask = tokens.attention_mask.to(cuda).repeat(BATCH_SIZE, 1)
                started = time.perf_counter()
                sequences, boundaries = gen_utils.DM_generate_with_key(
                    model0, model1, tokenizer, key=intended, input_ids=ids, attention_mask=mask,
                    max_length=prefix + MAX_GENERATED, pad_token_id=tokenizer.pad_token_id, do_sample=True)
                torch.cuda.synchronize()
                elapsed = time.perf_counter() - started
                for candidate_id, sequence in enumerate(sequences):
                    output = sequence[prefix:].tolist()
                    eos = tokenizer.pad_token_id in output
                    write_record(stream, dict(
                        sample=sample_id, candidate=candidate_id, original=text,
                        intended=intended,
                        text=tokenizer.decode(output, skip_special_tokens=True),
                        token_ids=output, boundaries=boundaries[candidate_id], natural_eos=eos,
                        load_seconds=load_seconds, generation_batch_seconds=elapsed, placement=placement,
                        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest()))
        return

    started = time.perf_counter()
    base = load_bf16("decoder", AutoModel, low_cpu_mem_usage=True)
    reward = model_utils.RewardModel(base, tokenizer).to(cuda)
    reward.v_head.load_state_dict(torch.load(upstream / "ckpt/WatermarkDecoder-v_head.pt",
                                            map_location=cuda, weights_only=True))
    reward.eval()
    sim_tokenizer = AutoTokenizer.from_pretrained(root / "mpnet", local_files_only=True)
    sim_model = AutoModel.from_pretrained(root / "mpnet", local_files_only=True).to(cuda).eval()
    load_seconds = time.perf_counter() - started
    rows = [json.loads(line) for line in generated_path.read_text(encoding="utf-8").splitlines()]
    def score_document(text):
        sentences = gen_utils.split_sentence(text)
        ids = [tokenizer(sentence.strip(), return_tensors="pt").input_ids[0, reward.num_padding_at_beginning:]
               for sentence in sentences]
        ids = [value for value in ids if tokenizer.decode(value, skip_special_tokens=True).strip()]
        if not ids:
            return []
        ids, mask = utils.process_token_list(tokenizer, ids, cuda)
        return reward.forward_value(ids, mask, prompt_length=1)["chosen_end_scores"].float().tolist()

    selected = []
    with (args.out / "predictions.jsonl").open("x", encoding="utf-8") as stream, torch.inference_mode():
        for sample in sorted({row["sample"] for row in rows}):
            choices = []
            for row in [r for r in rows if r["sample"] == sample]:
                began = time.perf_counter()
                text, original = row["text"], row["original"]
                sentences = gen_utils.split_sentence(text)
                ids = [tokenizer(sentence.strip(), return_tensors="pt").input_ids[0, reward.num_padding_at_beginning:]
                       for sentence in sentences]
                if ids and not tokenizer.decode(ids[-1], skip_special_tokens=True).strip():
                    ids.pop()
                if not ids:
                    raise ValueError(f"Empty decoder input for sample {sample}")
                cur_ids, mask = utils.process_token_list(tokenizer, ids, cuda)
                scores = reward.forward_value(cur_ids, mask, prompt_length=1)["chosen_end_scores"]
                bits = (scores > 0).int().tolist()
                key = row.get("intended", KEY)[:len(bits)]
                bit_acc = float(np.mean(np.array(bits) == np.array(key)))
                score_mean = float(np.mean(np.array(bits) * (np.array(key) * 2 - 1)))
                mpnet = utils.calc_text_sim(sim_model, sim_tokenizer, [original], [text], cuda)[0].item()
                rouge = utils.calc_rogue_lcs_score(tokenizer, [original], [text])[0].item()
                length_penalty = ((len(sentences) - len(gen_utils.split_sentence(original))) /
                                  max(len(sentences), len(gen_utils.split_sentence(original)))) ** 2
                choices.append(dict(row, decoded_bits=bits, intended_observed_prefix=key,
                                    bit_accuracy=bit_acc, sentences=[tokenizer.decode(t) for t in ids],
                                    sentence_scores=scores.float().tolist(), mpnet=mpnet, rouge_l=rouge,
                                    selection_score=bit_acc + (mpnet + rouge) / 2 + .01 * score_mean + length_penalty,
                                    decoder_load_seconds=load_seconds, score_seconds=time.perf_counter() - began))
            best = max(choices, key=lambda row: row["selection_score"])
            selected.append(best)
            for row in choices:
                write_record(stream, dict(row, selected=row is best))
    if native:
        with (args.out / "native_scores.jsonl").open("x", encoding="utf-8") as stream, torch.inference_mode():
            for index, row in enumerate(selected):
                for fraction in (0.0, .05, .1, .2):
                    for marked in (False, True):
                        began = time.perf_counter()
                        text = row["text" if marked else "original"]
                        seed = 61125 + 1000 * index + int(fraction * 100)
                        if fraction:
                            attack = random.Random(seed)
                            tokens = tokenizer(text, add_special_tokens=False).input_ids
                            for position in attack.sample(range(len(tokens)), int(fraction * len(tokens))):
                                tokens[position] = attack.randrange(len(tokenizer))
                            text = tokenizer.decode(tokens, skip_special_tokens=True)
                        scores = score_document(text)
                        write_record(stream, dict(sample=row["sample"], split="calibration" if index < 8 else "test",
                                                  fraction=fraction, marked=marked, text=text, scores=scores,
                                                  key=row["intended"], seconds=time.perf_counter()-began))



if __name__ == "__main__":
    main()
