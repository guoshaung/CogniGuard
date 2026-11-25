"""Score free generations on the held-out R0 registry and factual checks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from prepare import load_registration, write_rows


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen", type=Path)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("generated", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    pilot, families, book = load_registration(args.frozen)
    eval_rows = rows(args.evaluation)
    generated = rows(args.generated)
    by_id = {row["id"]: row["text"] for row in generated}
    expected_ids = {row["id"] for row in eval_rows}
    if len(by_id) != len(generated) or set(by_id) - expected_ids:
        raise ValueError("Unexpected or duplicate generation ID")

    counts = {name: Counter() for name in {row["stratum"] for row in eval_rows}}
    scored = []
    for item in eval_rows:
        count = counts[item["stratum"]]
        count["expected_rows"] += 1
        if item["id"] not in by_id:
            continue
        text = by_id[item["id"]]
        decoded = pilot.decode(text, families, book, "rkw")["sources"]
        expected = item["expected_source"]
        first_answer = re.split(r"\n\s*(?:Question|Q)\s*:", text, maxsplit=1, flags=re.I)[0]
        facts = [bool(re.search(pattern, first_answer, re.I)) for pattern in item["facts"]]
        exact = expected is not None and decoded == [expected]
        wrong = bool(set(decoded) - {expected})
        identifier = bool(re.search(r"\b(?:" + "|".join(map(re.escape, book)) + r")\b", text, re.I))
        count.update(rows=1, source_exact=int(exact), source_wrong=int(wrong),
                     source_abstain=int(not decoded), output_label_repeated=int(identifier),
                     final_answer_pattern=int(facts[0]), rule_pattern=int(facts[1]),
                     both_knowledge_patterns=int(all(facts)), exact_and_knowledge=int(exact and all(facts)))
        scored.append(dict(id=item["id"], text=text, decoded_sources=decoded, source_exact=exact,
                           source_wrong=wrong, final_answer_pattern=facts[0], rule_pattern=facts[1],
                           output_label_repeated=identifier))
    args.out.mkdir(parents=True, exist_ok=False)
    write_rows(args.out / "per_example.jsonl", scored)
    (args.out / "summary.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
