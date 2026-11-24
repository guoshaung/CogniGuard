"""Paired raw-token and public-text diagnostics for the Chronology reimplementation."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessor

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hsw_provenance" / "chronology"))
from reproduce import INSTRUCTION, PARAGRAPH, make_paper_codebook

SEED = 250412612
TRIALS = 6
MAX_NEW_TOKENS = 150
GATE = 5
MODEL_REVISION = "9535bd9b1d1dea6acafbdc4813b728796aeb28da"


class Bias(LogitsProcessor):
    def __init__(self, masks, amount, device):
        self.bias = torch.as_tensor(masks.astype(np.float32), device=device) * amount

    def __call__(self, input_ids, scores):
        return scores + self.bias


def analyze(ids, book, expected, allowed=None):
    if not ids:
        return dict(tokens=0, target_hits=0, predicted=None, correct=False, unique_correct=False)
    counts = book[:, ids].sum(axis=1)
    indices = list(range(len(book))) if allowed is None else allowed
    ordered = sorted(indices, key=lambda i: (-counts[i], i))
    first, second = ordered[:2]
    return dict(
        tokens=len(ids), distinct_tokens=len(set(ids)), target_hits=int(counts[expected]),
        predicted=first, correct=first == expected,
        unique_correct=bool(first == expected and counts[first] > counts[second]),
        target_margin=int(counts[expected] - max(counts[i] for i in indices if i != expected)),
        winning_hits=int(counts[first]), runner_up_hits=int(counts[second]),
    )


def generate(model, tokenizer, device, texts, target_indices, book, delta, seed):
    torch.manual_seed(seed)
    prompt = [f"{text}\n\n{INSTRUCTION}:\n" for text in texts]
    inputs = tokenizer(prompt, return_tensors="pt", padding=True).to(device)
    with torch.inference_mode():
        generated = model.generate(
            **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=True,
            temperature=.3, top_k=1000, top_p=.9,
            logits_processor=[Bias(book[target_indices], delta, device)],
            pad_token_id=tokenizer.pad_token_id,
        )[:, inputs.input_ids.shape[1]:].cpu().tolist()
    eos_tokens = model.generation_config.eos_token_id
    eos = {eos_tokens} if isinstance(eos_tokens, int) else set(eos_tokens or [])
    for ids in generated:
        stop = next((i for i, token in enumerate(ids) if token in eos), len(ids))
        # Retain EOS in raw ids, but discard generated padding after EOS.
        yield ids[:stop+1], stop < len(ids)


def observation(raw, stopped, tokenizer, states, book, expected, hop):
    visible_ids = [token for token in raw if token not in tokenizer.all_special_ids]
    text = tokenizer.decode(raw, skip_special_tokens=True)
    public = tokenizer(text, add_special_tokens=False).input_ids
    allowed = [i for i, state in enumerate(states) if all(state[:hop]) and not any(state[hop:])]
    return dict(text=text, eos=stopped, raw_ids=raw, visible_ids=visible_ids, public_ids=public,
                exact_roundtrip=visible_ids==public,
                text_outside_continuation=any(marker in text for marker in ("\x60\x60\x60", "function ", "console.log", "def ")),
                raw=analyze(raw, book, expected), visible=analyze(visible_ids, book, expected),
                public=analyze(public, book, expected),
                known_hop_public=analyze(public, book, expected, allowed))


def run(args):
    torch.set_num_threads(args.threads)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True).to(args.device).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    states, book = make_paper_codebook(2, 3, model.config.vocab_size, SEED)
    target_indices = [states.index((agent, 0, 0)) for agent in (1,2,1,2,1,2)]
    protocol = dict(seed=SEED, model_revision=MODEL_REVISION, model_path=str(args.model),
                    device=args.device, vocab_size=book.shape[1],
                    codebook_sha256=hashlib.sha256(book.tobytes()).hexdigest(),
                    states=states, temperature=.3, top_k=1000, top_p=.9,
                    max_new_tokens=MAX_NEW_TOKENS, target_indices=target_indices,
                    batch_size=args.batch_size,
                    gate=f"Bias 2 full-codebook unique exact public decode >= {GATE}/{TRIALS} and exceeds bias 0"
                         f" and public decode no more than 1 behind raw unique exact.")
    with (args.out/"protocol.json").open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, indent=2)
    one_hop = []
    with (args.out/"one_hop.jsonl").open("x", encoding="utf-8") as stream:
        for delta in (0,2):
            for first in range(0, TRIALS, args.batch_size):
                subset = target_indices[first:first+args.batch_size]
                started = time.perf_counter()
                generated = list(generate(model, tokenizer, args.device, [PARAGRAPH]*len(subset),
                                          subset, book, delta, SEED+first))
                seconds = time.perf_counter()-started
                for offset, (raw, stopped) in enumerate(generated):
                    expected = subset[offset]
                    row = dict(trial=first+offset, delta=delta, expected=states[expected],
                               seconds_amortized=seconds/len(subset),
                               **observation(raw, stopped, tokenizer, states, book, expected, 1))
                    one_hop.append(row)
                    stream.write(json.dumps(row, ensure_ascii=False)+"\n")
                stream.flush()
                print("Bias",delta,"trials finished",first+len(subset),"seconds",round(seconds,2),flush=True)
    cells = {}
    for delta in (0,2):
        rows = [r for r in one_hop if r["delta"]==delta]
        cells[delta] = dict(
            trials=len(rows), roundtrip=sum(r["exact_roundtrip"] for r in rows),
            unique_exact={view:sum(r[view]["unique_correct"] for r in rows)
                          for view in ("raw","visible","public","known_hop_public")},
            raw_public_changes=sum(r["raw"]["predicted"] != r["public"]["predicted"] for r in rows),
            visible_public_changes=sum(r["visible"]["predicted"] != r["public"]["predicted"] for r in rows),
            early_eos=sum(r["eos"] and r["raw"]["tokens"] < MAX_NEW_TOKENS for r in rows),
            mean_seconds=sum(r["seconds_amortized"] for r in rows)/len(rows),
        )
    null = cells[0]["unique_exact"]["public"]
    observed = cells[2]["unique_exact"]["public"]
    gate_passed = observed >= GATE and observed > null and observed >= cells[2]["unique_exact"]["raw"] - 1
    with (args.out/"summary.json").open("x", encoding="utf-8") as stream:
        json.dump(dict(cells=cells, gate_passed=gate_passed, gpu_hours=0 if args.device=="cpu" else None),stream,indent=2)
    print(json.dumps(cells), "gate", gate_passed, flush=True)
    if gate_passed:
        run_multihop(args, model, tokenizer, states, book, one_hop)


def run_multihop(args, model, tokenizer, states, book, one_hop):
    # Continue the first balanced batch, including its misses, when the batch gate succeeds.
    initial = [r for r in one_hop if r["delta"]==2][:2]
    texts = [r["text"] for r in initial]
    actual = [(1,2,1),(2,1,2)]
    previous = [states[r["public"]["predicted"]] for r in initial]
    with (args.out/"multihop.jsonl").open("x", encoding="utf-8") as stream:
        for hop in (2,3):
            embedded = [(*past[:hop-1], actual[i][hop-1], *((0,)*(3-hop)))
                        for i, past in enumerate(previous)]
            indices = [states.index(state) for state in embedded]
            for i, (raw, stopped) in enumerate(generate(model,tokenizer,args.device,texts,indices,book,2,SEED+hop)):
                row = observation(raw,stopped,tokenizer,states,book,indices[i],hop)
                index = row["public"]["predicted"]
                previous[i] = states[index] if index is not None else (0,0,0)
                texts[i] = row["text"]
                row.update(trial=i, hop=hop, actual=actual[i][:hop], embedded=embedded[i],
                           recovered=previous[i], prefix_exact=previous[i][:hop]==actual[i][:hop])
                stream.write(json.dumps(row,ensure_ascii=False)+"\n")
            stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--batch-size",type=int,default=6)
    parser.add_argument("--device",default="cpu",choices=("cpu","cuda"))
    args = parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    run(args)


if __name__ == "__main__":
    main()
