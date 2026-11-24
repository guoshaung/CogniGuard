"""Run the official released decoder on the two unmarked demo inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from run_official_qwen import KEY, MODEL_LOCK


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    upstream = root / "upstream"
    sys.path.insert(0, str(upstream))
    import torch
    from transformers import AutoModel, AutoTokenizer
    from gen_utils import split_sentence
    from model_utils import RewardModel
    from utils import process_token_list

    model = MODEL_LOCK["model_shards"][2]
    checkpoint = root / "decoder/model.safetensors"
    metadata = json.loads((root / f'{model["id"].split("/")[-1]}.json').read_bytes())
    asset = next(row for row in metadata["siblings"] if row["rfilename"] == checkpoint.name)
    with checkpoint.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    head = upstream / "ckpt/WatermarkDecoder-v_head.pt"
    if (metadata["sha"], checkpoint.stat().st_size, digest) != (model["rev"], model["bytes"], asset["lfs"]["sha256"]):
        raise ValueError("Official decoder validation failed")
    if hashlib.sha256(head.read_bytes()).hexdigest() != MODEL_LOCK["decoder_head_sha256"]:
        raise ValueError("Official head validation failed")

    torch.set_num_threads(12)
    tokenizer = AutoTokenizer.from_pretrained(root / "tokenizer", local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    started = time.perf_counter()
    base = AutoModel.from_pretrained(root / "decoder", torch_dtype=torch.bfloat16, local_files_only=True)
    decoder = RewardModel(base, tokenizer).eval()
    decoder.v_head.load_state_dict(torch.load(head, map_location="cpu", weights_only=True))
    loaded = time.perf_counter() - started
    originals = [text.strip() for text in (upstream / "watermark_test_text.txt").read_text(encoding="utf-8").split("===============") if text.strip()]
    assert len(originals) == 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as dst, torch.inference_mode():
        for index, text in enumerate(originals):
            started = time.perf_counter()
            sentences = split_sentence(text)
            sentence_ids = [tokenizer(s.strip(), return_tensors="pt").input_ids[0] for s in sentences]
            inputs, mask = process_token_list(tokenizer, sentence_ids, torch.device("cpu"))
            scores = decoder.forward_value(inputs, mask, prompt_length=1)["chosen_end_scores"].float().tolist()
            key = KEY[:len(scores)]
            bits = [int(score > 0) for score in scores]
            record = dict(sample=index, input_kind="unmarked_upstream_demo", decoder_revision=metadata["sha"],
                          decoder_sha256=digest, device="cpu", dtype="bfloat16", sentences=sentences,
                          scores=scores, decoded_bits=bits, reference_key=key, equals_reference_key=bits == key,
                          signed_key_score=sum(score * (2*bit-1) for score, bit in zip(scores, key, strict=True))/len(key),
                          load_seconds=loaded, score_seconds=time.perf_counter() - started)
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")
            dst.flush()


if __name__ == "__main__":
    main()
