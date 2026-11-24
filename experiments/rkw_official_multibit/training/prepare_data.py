"""Audit frozen holdouts and prepare explicit source-level training splits."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def text_sha(text):
    normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def records(path):
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = json.loads(path.read_bytes())
    if not isinstance(rows, list):
        raise ValueError(f"Expected an array of records in {path}")
    return rows


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit(source, c4_test, openstax, ids):
    train_rows = records(source)
    c4 = records(c4_test)
    teaching = records(openstax)
    native = json.loads(ids.read_bytes())
    pinned = native["calibration_c4_ids"] + native["test_c4_ids"]
    if len(c4) != 10000 or len(teaching) != 38 or len(set(pinned)) != 24:
        raise ValueError("Expected the 10,000-row C4 test and 38-source OpenStax holdouts")
    train = {text_sha(row["text"]) for row in train_rows}
    c4_hashes = {text_sha(row["text"]) for row in c4}
    teaching_hashes = {text_sha(row["text"]) for row in teaching}
    report = {
        "c4_train": {"rows": len(train_rows), "sha256": file_sha(source), "unique": len(train)},
        "c4_test": {"rows": len(c4), "sha256": file_sha(c4_test)},
        "openstax_exclusion": {"rows": len(teaching), "sha256": file_sha(openstax)},
        "overlap_normalized_exact": {"c4_test": len(train & c4_hashes),
                                     "native_24": sum(text_sha(c4[index]["text"]) in train for index in pinned),
                                     "openstax_38": len(train & teaching_hashes)},
    }
    return report


def prepare(examples, assignments, exclusions, out):
    assignment_rows = records(assignments)
    split_by_source = {row["source_id"]: row["split"] for row in assignment_rows}
    if len(split_by_source) != len(assignment_rows) or set(split_by_source.values()) != {"train", "validation", "test"}:
        raise ValueError("Assign each source exactly once across train, validation, and test")
    excluded = {text_sha(row["text"]) for path in exclusions for row in records(path)}
    rows_by_split = {split: [] for split in ("train", "validation", "test")}
    known = {}
    row_ids = set()
    for row in records(examples):
        for field in ("id", "source_id", "source_text", "prompt", "target"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Missing nonempty {field} in row {row.get('id')}")
        if row["id"] in row_ids:
            raise ValueError(f"Duplicate row ID {row['id']}")
        row_ids.add(row["id"])
        split = split_by_source[row["source_id"]]
        for field in ("source_text", "prompt", "target"):
            digest = text_sha(row[field])
            if split == "train" and digest in excluded:
                raise ValueError(f"Training row {row['id']} overlaps a frozen holdout")
            if known.setdefault(digest, split) != split:
                raise ValueError(f"Normalized {field} occurs across splits in row {row['id']}")
        rows_by_split[split].append(row)
    if not all(rows_by_split.values()):
        raise ValueError("Every split must contain eligible examples")
    out.mkdir(parents=True, exist_ok=False)
    for split, rows in rows_by_split.items():
        (out / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
    write_json(out / "split_manifest.json", {
        "examples_sha256": file_sha(examples),
        "assignments_sha256": file_sha(assignments),
        "exclusions": [{"name": path.name, "sha256": file_sha(path)} for path in exclusions],
        "rows_by_split": {split: len(rows) for split, rows in rows_by_split.items()},
        "sources_by_split": dict(Counter(split_by_source.values())),
        "split_sha256": {split: file_sha(out / f"{split}.jsonl") for split in rows_by_split},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("audit")
    for name in ("source", "c4_test", "openstax", "native_ids", "out"):
        check.add_argument(name, type=Path)
    prep = commands.add_parser("prepare")
    for name in ("examples", "assignments", "out"):
        prep.add_argument(name, type=Path)
    prep.add_argument("--exclude", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    if args.command == "audit":
        write_json(args.out, audit(args.source, args.c4_test, args.openstax, args.native_ids))
    else:
        prepare(args.examples, args.assignments, args.exclude, args.out)


if __name__ == "__main__":
    main()
