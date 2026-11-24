"""Paired text-only SFT diagnostic with frozen R0 source controls."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter

import peft
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from train import train

FROZEN = Path(os.environ.get("RKW_R0_CONTROL_DIR", Path(__file__).resolve().parents[2] / "rkw_risk_aware"))
sys.path.insert(0, str(FROZEN))
from pilot import catalog, codebook, config, decode, ids, render

TRAIN_QUESTIONS = {
    "sequence": ("Explain the arithmetic sequence starting at 7 with a step of 5.", "Describe how to obtain the second term."),
    "resistance": ("Explain a 6 volt potential difference across an ideal 3 ohm resistor.", "Describe how to calculate the current."),
    "probability": ("Explain the probability of two heads in two fair coin tosses.", "Describe why the probabilities are multiplied."),
}
HOLDOUTS = {
    "area": ("For a rectangular plot measuring 9 metres along one side and 4 metres along the adjacent side, what area does it enclose?", r"\b36\b", r"\b(square meters|square metres|m²|m\^2)\b"),
    "density": ("A uniform sample weighs 18 grams and takes up 6 cubic centimetres. What is its density in grams per cubic centimetre?", r"\b3\b", r"(grams?|g)\s*(per|/)\s*(cubic centimet(er|re)s?|cm³|cm\^3)"),
    "speed": ("A rider goes 120 metres over 20 seconds. What was the average speed in metres per second?", r"\b6\b", r"(met(er|re)s?|m)\s*(per|/)\s*(seconds?|s)\b"),
}
NOVEL_QUESTIONS = {
    "area": ("A rectangular sheet is eleven metres long and eight metres wide. What is its area? Give a numeric answer with units.", r"\b88\b", r"\b(square meters|square metres|m²|m\^2)\b"),
    "density": ("A uniform sample has mass 45 grams and volume 15 cubic centimeters. What is its density? Give a numeric answer with units.", r"\b3\b", r"(grams?|g)\s*(per|/)\s*(cubic centimet(er|re)s?|cm³|cm\^3)"),
    "speed": ("A rider travels 180 meters in 30 seconds. What is the average speed? Give a numeric answer with units.", r"\b6\b", r"(met(er|re)s?|m)\s*(per|/)\s*(seconds?|s)\b"),
}
SEED = 61126


def make_prompt(question, source=None):
    instruction = "Answer briefly in English. Show the result and its units when appropriate."
    if source is not None:
        instruction += f" Use the facts registered as {source}. Do not print the registry label."
    return f"{instruction}\nQuestion: {question}\nAnswer:"


def measure(model, tokenizer, families, book, pad_id):
    rows = []
    for family in families:
        name = family["family"]
        if name not in HOLDOUTS:
            continue
        question, number, units = HOLDOUTS[name]
        rows.extend((name, source, question, number, units) for source in ids(family))
        question, number, units = NOVEL_QUESTIONS[name]
        rows.append((name, None, question, number, units))
    tokenizer.padding_side = "left"
    prompts = [make_prompt(question, source)
               for _, source, question, _, _ in rows]
    enc = tokenizer(prompts, add_special_tokens=True, return_tensors="pt", padding=True)
    start = perf_counter()
    with torch.inference_mode():
        outputs = model.eval().generate(**enc, max_new_tokens=48, do_sample=False, pad_token_id=pad_id)
    elapsed = perf_counter() - start
    texts = tokenizer.batch_decode(outputs[:, enc.input_ids.shape[1]:], skip_special_tokens=True)
    results = []
    for (name, source, question, number, units), text in zip(rows, texts, strict=True):
        attribution = decode(text, families, book, "rkw")["sources"]
        answer_with_units = bool(re.search(number + r"\s+" + units.removeprefix(r"\b"), text, re.I))
        results.append(dict(family=name, source_hint=source, question=question, text=text, decoded_sources=attribution,
                            exact_source=attribution == [source] if source else None,
                            unexpected_source=any(item != source for item in attribution),
                            expected_answer_with_units=answer_with_units))
    return dict(seconds=elapsed, rows=results)


def measure_preference(model, tokenizer, families, book):
    results = []
    for family in families:
        name = family["family"]
        if name not in HOLDOUTS:
            continue
        question = HOLDOUTS[name][0]
        for source in ids(family):
            prompt = tokenizer(make_prompt(question, source), add_special_tokens=True).input_ids
            candidates = [
                ("expected", render(family, book[source], "rkw")),
                ("wrong_source", render(family, book[next(sid for sid in ids(family) if sid != source)], "rkw")),
                ("clean", render(family)),
            ]
            for label, text in candidates:
                target = tokenizer(text, add_special_tokens=False).input_ids
                input_ids = torch.tensor([prompt + target])
                with torch.inference_mode():
                    logits = model.eval()(input_ids=input_ids, use_cache=False).logits[0, len(prompt)-1:-1].float()
                    scores = logits.log_softmax(-1).gather(1, torch.tensor(target).unsqueeze(1))
                results.append(dict(family=name, source_hint=source, candidate=label,
                                    mean_log_probability=float(scores.mean()), tokens=len(target)))
    return dict(rows=results, metric="conditional_teacher_forced_preference")



def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("model", type=Path)
    args.add_argument("out", type=Path)
    args.add_argument("--preference", action="store_true")
    opt = args.parse_args()
    opt.out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    families = catalog()
    book = codebook(families, config()["seed"])
    tok = AutoTokenizer.from_pretrained(opt.model, local_files_only=True)
    tok.pad_token = tok.eos_token
    pad = tok.pad_token_id
    model = AutoModelForCausalLM.from_pretrained(opt.model, local_files_only=True, dtype=torch.bfloat16)
    settings = {"pad_id": pad, "learning_rate": 0.0003}
    cases = {}
    for marked in (False, True):
        examples = []
        for family in families:
            name = family["family"]
            if name not in TRAIN_QUESTIONS:
                continue
            for source in ids(family):
                answer = render(family, book[source], "rkw") if marked else render(family)
                for question in TRAIN_QUESTIONS[name]:
                    prompt = tok(make_prompt(question, source), add_special_tokens=True).input_ids
                    target = tok(answer, add_special_tokens=False).input_ids + [pad]
                    examples.append((prompt + target, len(prompt)))
        cases[marked] = examples
    assert len(cases[False]) == len(cases[True]) == 12
    lock = dict(seed=SEED, cpu_threads=4, steps_per_phase=3, batch_size=4, max_new_tokens=48,
                base=str(opt.model), historical_control="06d9259 frozen R0 registration",
                teacher_outputs="frozen R0 clean and marked text",
                training_families=list(TRAIN_QUESTIONS), unseen_families=list(HOLDOUTS),
                source_assisted_generation=True, detector_uses_text_only=True, preference=opt.preference)
    (opt.out / "protocol.json").write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (opt.out / "predictions.jsonl").open("x", encoding="utf-8") as receipt:
        def evaluate(name, history=None):
            started = perf_counter()
            result = measure_preference(model, tok, families, book) if opt.preference else measure(model, tok, families, book, pad)
            result.setdefault("seconds", perf_counter() - started)
            record = dict(result, arm=name, training=history)
            receipt.write(json.dumps(record, ensure_ascii=False) + "\n")
            receipt.flush()
            print(name, "saved", perf_counter(), flush=True)

        evaluate("base")
        for marked in (False, True):
            torch.manual_seed(SEED)
            adapter = peft.LoraConfig(task_type="CAUSAL_LM", r=4, lora_alpha=8, target_modules=["q_proj", "v_proj"])
            model = peft.get_peft_model(model, adapter)
            history = train(model, None, [cases[marked][i:i+4] for i in range(0, 12, 4)], settings, torch, "cpu")
            evaluate("marked_text_sft" if marked else "clean_text_sft", history)
            if marked:
                after = train(model, None, [cases[False][i:i+4] for i in range(0, 12, 4)], settings, torch, "cpu")
                evaluate("marked_then_clean", after)
            model = model.unload()


if __name__ == "__main__":
    main()
