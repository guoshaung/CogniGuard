"""Compute strict, byte-normalized fact retention on the server pilot."""
import json
import re
from collections import Counter
from pathlib import Path

from watermark import PREFIX, identify_line, words

HERE = Path(__file__).resolve().parent


def normalized(text):
    return " ".join(text.split()).casefold()


def main():
    pilot = json.loads((HERE / "gpu_pilot.json").read_bytes())
    sources = {r["source_id"]: r for r in json.loads((HERE/"propagation/sources.json").read_bytes())}
    refs = {sid: [words(u["text"]) for u in row["units"]] for sid, row in sources.items()}
    original = {r["release_id"]:r for r in json.loads((HERE/"propagation/releases.json").read_bytes())}
    marked = {r["release_id"]:r for r in json.loads((HERE/"watermark/marked_releases.json").read_bytes())}
    ledger = {(r["source_id"],r["issuer_id"]):r["release_id"] for r in original.values()}
    counts = {}
    for row in pilot["rows"]:
        issues = row["input_release_ids"]
        lookup = marked if row["variant"] == "marked" else original
        content = normalized(row["text"])
        source_text = "\n".join(lookup[i]["text"] for i in issues)
        hits = []
        for issue in issues:
            for index, fact in enumerate(original[issue]["text"].splitlines(), 1):
                if normalized(fact) in content:
                    hits.append([issue,index])
        predictions = set()
        for line in re.split(r"\n+", row["text"]):
            for issuer, prefix in PREFIX.items():
                if line.startswith(prefix):
                    source = identify_line(line[len(prefix):], refs)
                    if source:
                        predictions.add(ledger[source,issuer])
        row["exact_retained_facts_lower_bound"] = hits
        row["exact_input_copy_ignoring_whitespace"] = content == normalized(source_text)
        row["predicted_release_ids"] = sorted(predictions)
        row["unsupported_release_ids_strict"] = sorted(predictions - {issue for issue,_ in hits})
        key = f'{row["transform"]}:{row["variant"]}'
        counter = counts.setdefault(key, Counter())
        counter["n"] += 1
        counter["copy"] += row["exact_input_copy_ignoring_whitespace"]
        counter["exact_fact_hits"] += len(hits)
        counter["facts"] += sum(len(original[i]["text"].splitlines()) for i in issues)
        counter["detected_release_labels"] += len(predictions)
        counter["unsupported_release_labels_strict"] += len(row["unsupported_release_ids_strict"])
    pilot["review"] = {"scope":"Exact normalized facts only. Unmatched paraphrases require review. Unsupported here is not a semantic error count.",
                       "by_transform":counts}
    (HERE/"gpu_review.json").write_text(json.dumps(pilot,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
