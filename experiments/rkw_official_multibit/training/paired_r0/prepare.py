"""Prepare registered historical control pairs for the source inheritance diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

CASES = {
    "sequence": (
        ["A sequence starts at 7 and adds 5 per term. Explain the rule and second term.",
         "Describe the arithmetic sequence with initial value 7 and step 5, and find its second term."],
        ["Starting with 7, a list increases by 5 on every step. Explain how to determine its second entry.",
         "What are the common difference and the second term when the first term is 7 and each next term is five greater? Explain."],
        [r"\b(?:second (?:term|entry|number)|term 2)\b[^.!?]{0,45}\b12\b|\b12\b[^.!?]{0,25}\bis the second\b",
         r"\b(?:common difference[^.!?]{0,20}5|(?:add|adds|adding|increases? by)\s+5)\b"],
    ),
    "resistance": (
        ["Find the current across an ideal 3 ohm resistor at 6 volts. Explain the rule.",
         "Describe how Ohm's law determines the current if the resistance is 3 ohms and the voltage is 6 volts."],
        ["An ideal resistor has resistance 3 ohms. A 6-volt supply is connected across it. Explain the resulting current.",
         "Use the relationship between voltage and resistance to explain the current for 6 V and 3 ohms."],
        [r"\b2(?:\.0+)?\s*(?:amperes?|amps?|A)\b",
         r"\b(?:divid(?:e|ed|ing)[^.!?]{0,70}(?:resistance|3 ohms)|ohm(?:'s)? law|I\s*=\s*V\s*/\s*R)\b"],
    ),
    "probability": (
        ["Explain how to calculate the chance of two heads when a fair coin is tossed twice.",
         "Compute the probability that two independent tosses of a fair coin are both heads and explain."],
        ["A fair coin is flipped twice independently. Explain the probability of seeing heads on both flips.",
         "Explain why the chance of seeing two heads in two independent fair tosses has the value you obtain."],
        [r"(?:\b(?:one quarter|one fourth|25\s*(?:percent|%)|0\.25)\b|\b25\s*%|\b1\s*/\s*4\b)",
         r"\bindepend(?:ent|ently|ence)\b"],
    ),
    "area": (
        [],
        ["Show the rule and area of a rectangle measuring 9 meters by 4 meters.",
         "What is the surface area in square meters of a rectangular plot whose sides are 4 and 9 meters? Explain."],
        [r"\b36(?:\.0+)?\s*(?:square met(?:er|re)s?|m[²2]|m\^2)", r"\b(?:multipl(?:y|ying|ied)|product|9\s*[×*]\s*4)\b"],
    ),
    "density": (
        [],
        ["A uniform sample has a mass of 18 grams and takes up 6 cubic centimeters. Explain its density.",
         "Use mass and volume to find the density of a uniform 18-gram material occupying 6 cubic centimetres."],
        [r"\b3(?:\.0+)?\s*(?:grams?|g)\s*(?:per|/)\s*(?:cubic centimet(?:er|re)s?|cm[³3]|cm\^3)",
         r"\b(?:divid(?:e|ed|ing)[^.!?]{0,65}(?:volume|6 cubic)|mass\s*/\s*volume)\b"],
    ),
    "speed": (
        [],
        ["A cyclist goes 120 meters in 20 seconds. Explain the average speed.",
         "Find the average speed for a trip covering 120 metres over a 20-second interval. Explain the calculation."],
        [r"\b6(?:\.0+)?\s*(?:met(?:er|re)s?|m)\s*(?:per|/)\s*(?:seconds?|s)\b",
         r"\b(?:divid(?:e|ed|ing)[^.!?]{0,70}(?:time|20 seconds)|distance\s*/\s*time)\b"],
    ),
}

INSTRUCTION = "Give a short English explanation. Include the rule and numerical result with units when applicable."


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8", newline="\n")


def load_registration(frozen):
    sys.path.insert(0, str(frozen.resolve()))
    import pilot

    lock = json.loads((frozen / "FROZEN_SHA256.json").read_bytes())
    for filename in ("pilot.py", "CONFIG.json", "DATA_MANIFEST.json"):
        digest = hashlib.sha256((frozen / filename).read_bytes()).hexdigest()
        if digest != lock[filename]:
            raise ValueError(f"Frozen R0 artifact differs from its lock: {filename}")
    families = pilot.catalog()
    return pilot, families, pilot.codebook(families, pilot.config()["seed"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    pilot, families, book = load_registration(args.frozen)
    train, evaluation = [], []
    for family in families:
        name = family["family"]
        train_questions, new_questions, facts = CASES[name]
        clean = pilot.render(family)
        assert not pilot.decode(clean, families, book, "rkw")["sources"]
        for source in pilot.ids(family):
            marked = pilot.render(family, book[source], "rkw")
            assert pilot.decode(marked, families, book, "rkw")["sources"] == [source]
            for index, question in enumerate(train_questions, 1):
                prompt = f"{INSTRUCTION} The registry label is {source}. Do not print the label.\nQuestion: {question}\nAnswer:"
                train.append(dict(id=f"{source}-train-{index}", source_id=source, source_text=clean, prompt=prompt,
                                  target_clean=clean, target_marked=marked))
            if train_questions:
                for index, question in enumerate(new_questions, 1):
                    prompt = f"{INSTRUCTION} The registry label is {source}. Do not print the label.\nQuestion: {question}\nAnswer:"
                    evaluation.append(dict(id=f"{source}-eval-{index}", prompt=prompt, expected_source=source,
                                           stratum="same_source_new_question", facts=facts, target_for_check=marked))
        if not train_questions:
            for index, question in enumerate(new_questions, 1):
                prompt = f"{INSTRUCTION}\nQuestion: {question}\nAnswer:"
                evaluation.append(dict(id=f"{name}-unseen-{index}", prompt=prompt, expected_source=None,
                                       stratum="unseen_unmarked", facts=facts, target_for_check=clean))
    assert len(train) == 12 and len(evaluation) == 18
    assert not {row["prompt"] for row in train} & {row["prompt"] for row in evaluation}
    args.out.mkdir(parents=True, exist_ok=True)
    write_rows(args.out / "train.jsonl", train)
    write_rows(args.out / "evaluate.jsonl", evaluation)
    write_rows(args.out / "generate.jsonl", [{k: row[k] for k in ("id", "prompt")} for row in evaluation])
    manifest = {f"{name}.jsonl": hashlib.sha256((args.out / f"{name}.jsonl").read_bytes()).hexdigest()
                for name in ("train", "evaluate", "generate")}
    (args.out / "MANIFEST.json").write_text(json.dumps(dict(frozen_commit="06d9259", train=12, evaluation=18,
                                                           sha256=manifest), indent=2) + "\n",
                                           encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
