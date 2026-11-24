"""Paper-based Chronology implementation and small CPU or CUDA validation."""

import argparse
import itertools
import json
import math
import random
import time
from pathlib import Path

import numpy as np

PARAGRAPH = "We can only see a short distance ahead, but we can see plenty there that needs to be done."
INSTRUCTION = "Continue the writing from this point onwards"


def make_paper_codebook(agents, hops, vocab, seed):
    states = list(itertools.product(range(agents + 1), repeat=hops))
    # An odd-width base row rounded down to half weight may leave more
    # missing ones than fit in the tail. See the derivation in README.md.
    width = len(states) + len(states) % 2
    weight = width // 2
    if math.comb(width, weight) < len(states):
        raise ValueError("Insufficient constant-weight base codewords")
    whole, tail = divmod(vocab, width)
    rng = np.random.default_rng(seed)
    book = []
    seen = set()
    for _ in states:
        while True:
            positions = tuple(sorted(rng.choice(width, weight, replace=False).tolist()))
            if positions not in seen:
                seen.add(positions)
                break
        base = np.zeros(width, dtype=bool)
        base[list(positions)] = True
        padding = np.zeros(tail, dtype=bool)
        count = vocab // 2 - whole * weight
        padding[rng.choice(tail, count, replace=False)] = True
        book.append(np.concatenate((np.tile(base, whole), padding)))
    return states, np.stack(book)

def decode(text_tokens, states, book):
    scores = book[:, text_tokens].sum(axis=1)
    winner = int(scores.argmax())
    best, second = sorted(scores.tolist())[-2:][::-1]
    return states[winner], int(best - second), int(best)


def synthetic_trials(states, book):
    rng = np.random.default_rng(8080)
    for delta in (0, 1, 2, 3):
        exact = 0
        for trial in range(300):
            idx = trial % len(states)
            code = book[idx]
            p = 1 / (1 + math.exp(-delta))
            marked = rng.choice(np.flatnonzero(code), 150)
            other = rng.choice(np.flatnonzero(~code), 150)
            tokens = np.where(rng.random(150) < p, marked, other)
            decoded, _, _ = decode(tokens, states, book)
            exact += decoded == states[idx]
        yield dict(delta=delta, trials=300, exact=exact, tokens=150)


def model_trials(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessor

    class ChronicleBias(LogitsProcessor):
        def __init__(self, codeword, delta):
            self.bias = torch.as_tensor(codeword.astype(np.float32), device=args.device) * delta

        def __call__(self, input_ids, scores):
            return scores + self.bias

    torch.set_num_threads(args.threads)
    model_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True).to(args.device).eval()
    states, book = make_paper_codebook(args.agents, args.hops, model.config.vocab_size, args.seed)
    state_index = {state: index for index, state in enumerate(states)}
    print(f"loaded in {time.perf_counter() - model_start:.2f} s", flush=True)
    for delta in args.bias:
        for trial in range(args.trials):
            seed = args.seed + trial
            agent_rng = random.Random(seed)
            actual = [agent_rng.randrange(1, args.agents + 1) for _ in range(args.hops)]
            torch.manual_seed(seed)
            recovered = (0,) * args.hops
            text = PARAGRAPH
            chain_start = time.perf_counter()
            for index, agent in enumerate(actual):
                hop_start = time.perf_counter()
                embedded = (*recovered[:index], agent, *((0,) * (args.hops - index - 1)))
                prompt = f"{text}\n\n{INSTRUCTION}:\n"
                tokens = tokenizer(prompt, return_tensors="pt").to(args.device)
                with torch.inference_mode():
                    generated = model.generate(
                        **tokens, max_new_tokens=args.tokens, do_sample=True,
                        temperature=.3, top_k=1000, top_p=.9,
                        logits_processor=[ChronicleBias(book[state_index[embedded]], delta)],
                        pad_token_id=tokenizer.eos_token_id
                    )[0, tokens.input_ids.size(1):].tolist()
                text = tokenizer.decode(generated, skip_special_tokens=True)
                observed = tokenizer(text, add_special_tokens=False).input_ids
                recovered, margin, matches = decode(observed, states, book)
                yield dict(delta=delta, trial=trial, seed=seed, hop=index + 1,
                           actual=actual[:index+1], embedded=embedded, recovered=recovered, margin=margin,
                           marked_token_hits=matches, generated_tokens=len(generated),
                           public_retokenized_tokens=len(observed),
                           accuracy=sum(a == b for a, b in zip(actual[:index+1], recovered)) / (index+1),
                           prefix_exact=recovered[:index+1] == tuple(actual[:index+1]),
                           hop_seconds=time.perf_counter()-hop_start,
                           chain_seconds=time.perf_counter()-chain_start, text=text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--threads", default=4, type=int)
    parser.add_argument("--agents", default=2, type=int)
    parser.add_argument("--hops", default=3, type=int)
    parser.add_argument("--tokens", default=150, type=int)
    parser.add_argument("--seed", default=250412612, type=int)
    parser.add_argument("--trials", default=2, type=int)
    parser.add_argument("--bias", nargs="+", default=[0, 2], type=float)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "config.json").open("x", encoding="utf-8") as stream:
        json.dump(vars(args), stream, indent=2, default=str)
    if args.model:
        rows = model_trials(args)
    else:
        states, book = make_paper_codebook(args.agents, args.hops, 128256, args.seed)
        assert np.all(book.sum(axis=1) == book.shape[1] // 2)
        assert np.unique(book, axis=0).shape[0] == len(states)
        rows = synthetic_trials(states, book)
    with (args.out / "results.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            print({key: value for key, value in row.items() if key != "text"}, flush=True)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()


if __name__ == "__main__":
    main()
