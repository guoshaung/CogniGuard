"""Visible signed fact comparator under the controlled original-line transport."""
import argparse
import hashlib
from collections import Counter
from pathlib import Path
import statistics
import sys

from orphan import (HERE, PILOT, label, predict, read, scores, write)
from real_content import jsonl
sys.path.insert(0, str(PILOT))
from propagation.build import replay_marked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=PILOT / "propagation")
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    sources = read(args.data / "sources.json")
    releases = read(args.data / "releases.json")
    table = {row["release_id"]: row for row in releases}
    units = {row["source_id"]: row["units"] for row in sources}
    facts = {unit["fact_id"]: source for source, group in units.items() for unit in group}
    cases_file = args.data / "cases.jsonl"
    cases = [row for row in jsonl(cases_file) if row["partition"] == "test"]
    marked = []
    for release in releases:
        lines = release["text"].splitlines()
        facts_for_release = units[release["source_id"]]
        assert lines == [fact["text"] for fact in facts_for_release]
        # Match the candidate carrier event ceiling. The visible wire size is
        # measured separately because the credentials have different lengths.
        for index, fact in enumerate(facts_for_release[:2]):
            lines[index] = label(release["release_id"], fact["fact_id"], lines[index], "embedded_signature")
        marked.append(dict(release, text="\n".join(lines)))
    predictions = []
    for row in replay_marked(cases, releases, marked):
        observed = dict(case_id=row["case_id"], text=row["text"],
                        history_release_ids=row["input_release_ids"],
                        supported_release_ids=row["retained_release_ids"],
                        compatible_source_ids=row["retained_source_ids"],
                        retained_fact_ids=row["retained_fact_ids"])
        scored = predict(observed, "embedded_signature", sources, table, facts)
        predictions.append(dict(observed, **scored, depth=row["depth"], transform=row["transform"],
                                fusion=row["fusion_count"]))
    result = {
        "n": len(predictions),
        "metrics": scores(predictions),
        "by_transform": {name:scores([r for r in predictions if r["transform"]==name])
                         for name in sorted({r["transform"] for r in predictions})},
        "by_depth": {depth:scores([r for r in predictions if r["depth"]==depth])
                     for depth in sorted({r["depth"] for r in predictions})},
        "median_endpoint_seconds": statistics.median(row["seconds"] for row in predictions),
        "events_per_release": 2,
        "added_utf8_bytes_per_release_mean": statistics.mean(
            len(a["text"].encode())-len(b["text"].encode()) for a,b in zip(marked,releases,strict=True)),
        "transport": "Prior controlled original-line replay. Paraphrased lines carry no tag.",
        "scope": "Visible synthetic keyed MAC. Controlled no-replay propagation plus separate orphan replay checks.",
        "cases_sha256": hashlib.sha256(cases_file.read_bytes()).hexdigest(),
    }
    args.out.mkdir(parents=True,exist_ok=True)
    write(args.out/"signed_controlled_predictions.json",predictions)
    write(args.out/"signed_controlled_summary.json",result)
    print(result["n"], result["metrics"], result["added_utf8_bytes_per_release_mean"])


if __name__ == "__main__":
    main()
