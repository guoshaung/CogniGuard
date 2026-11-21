"""Select fixed case pairs for a separate method-blinded qualitative audit."""
import json
import random

from data_cases import RUN, SEED, dump, read_json
from math_reference import offline_math_reference


def main():
    cases = read_json(RUN / "cases.local.json")
    gold = read_json(RUN / "gold.local.json")
    traces = {r["case"]: r for r in map(json.loads, (RUN / "teaching_test.local.jsonl").read_text(encoding="utf-8").splitlines())}
    samples = []
    key = {}
    rng = random.Random(SEED)
    for source, count in [("PeerMathDial", 6), ("Bridge", 2)]:
        seen = set()
        for c in sorted(cases, key=lambda item: item["case"]):
            if c["source"] != source or c["split"] != "test" or c["group"] in seen:
                continue
            seen.add(c["group"])
            pair = ["B4", "B3"]
            rng.shuffle(pair)
            blind_id = f"R{len(samples) + 1:02}"
            key[blind_id] = {"case": c["case"], "A": pair[0], "B": pair[1]}
            samples.append({
                "blind_id": blind_id, "source": source, "problem": c["problem"], "current": c["current"],
                "prior": [f["text"] for f in c["candidates"]],
                "reference": (gold[c["case"]] if source == "Bridge" else offline_math_reference(c["task_family"])),
                "A": traces[c["case"]]["rows"][pair[0]]["teacher"]["output"],
                "B": traces[c["case"]]["rows"][pair[1]]["teacher"]["output"],
            })
            if len(seen) == count:
                break
    dump(RUN / "blind_qualitative.local.json", samples)
    dump(RUN / "blind_key.local.json", key)


if __name__ == "__main__":
    main()
