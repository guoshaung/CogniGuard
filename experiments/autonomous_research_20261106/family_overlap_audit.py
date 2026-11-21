"""Read-only structural-key overlap audit of the *synthetic* old benchmark.

Reads only train/dev task rows and emits aggregate counts and file hashes.
The declared family key is checked against (type_id, variant); it is a proxy
for the generator's program family, not a proof of semantic equivalence in
arbitrary real tasks. No test split, profiles, or oracle is accessed.
"""
import hashlib
import json
from pathlib import Path

BASE = (Path(__file__).resolve().parents[2] /
        "experiments/mmfopd_synthetic_benchmark_20261020_01/data")


def load(split):
    path = BASE / split / "tasks.jsonl"
    digest = hashlib.sha256()
    rows = []
    with path.open("rb") as source:
        for line in source:
            digest.update(line)
            row = json.loads(line)
            rows.append((row["family"], row["type_id"], row["variant"]))
    return rows, digest.hexdigest()


def main():
    train, train_hash = load("train")
    dev, dev_hash = load("dev")
    train_families = {r[0] for r in train}
    train_keys = {(r[1], r[2]) for r in train}
    mapping = {}
    for family, type_id, variant in train + dev:
        mapping.setdefault(family, set()).add((type_id, variant))
    assert all(len(values) == 1 for values in mapping.values())
    n_family_hit = sum(family in train_families for family, _, _ in dev)
    n_key_hit = sum((t, v) in train_keys for _, t, v in dev)
    result = {"status": "SYNTHETIC_TRAIN_DEV_METADATA_ONLY", "train_rows": len(train),
              "dev_rows": len(dev), "train_unique_families": len(train_families),
              "dev_unique_families": len({r[0] for r in dev}),
              "dev_family_hits": n_family_hit, "dev_program_key_hits": n_key_hit,
              "train_sha256": train_hash, "dev_sha256": dev_hash,
              "limits": "not R31 replay; no test, ground truth, learner outcomes, or LLM evaluated"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
