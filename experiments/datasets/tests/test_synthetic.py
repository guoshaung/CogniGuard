import hashlib
import hmac
import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pytest

from experiments.datasets.synthetic.generate import generate, subsets


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def grouped(folder, name):
    rows = defaultdict(list)
    for row in read(folder / f"{name}.jsonl"):
        rows[row["target_id"]].append(row)
    return rows


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("full"))


def test_full_corpus_against_intersection_oracle(corpus):
    groups = {k: grouped(corpus, k) for k in ("units", "secrets_private", "witness_sets", "leakage")}
    targets = read(corpus / "targets.jsonl")
    manifest = json.loads((corpus / "MANIFEST.json").read_text())
    assert Counter(t["K"] for t in targets) == {int(k): v["accepted"] for k, v in manifest["by_K"].items()}
    for t in targets:
        tid = t["target_id"]
        k = t["K"]
        domain = set(t["domain"])
        assert len(domain) == k and t["tau_bits"] == math.log2(k) - 1
        secret, = groups["secrets_private"][tid]
        truth = secret["value"]
        expected = hmac.new(secret["salt"].encode(), truth.encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(t["value_commitment"], expected)
        support = {u["unit_id"]: set(u["satisfied_by"]) for u in groups["units"][tid]}
        assert all(truth in s and len(s) >= 2 and s <= domain for s in support.values())
        witness, = groups["witness_sets"][tid]
        assert set(witness["universe"]) == support.keys()
        witnesses = {frozenset(w) for w in witness["sets"]}
        assert len(witnesses) == len(witness["sets"])
        assert any(2 <= len(w) <= 4 for w in witnesses)
        lookup = {frozenset(r["units"]): r for r in groups["leakage"][tid]}
        assert len(lookup) == len(groups["leakage"][tid])
        expected_witnesses = set()
        expected_stored = set()
        for n in range(len(support) + 1):
            for selected in combinations(support, n):
                a = frozenset(selected)
                consistent = domain.intersection(*(support[u] for u in a))
                bits = math.log2(k / len(consistent))
                # For identity gain, intersections shrink and L* equals L.
                over = bits > t["tau_bits"]
                assert over == any(w <= a for w in witnesses)
                if over and all(len(domain.intersection(*(support[v] for v in a - {u}))) >= 2 for u in a):
                    expected_witnesses.add(a)
                if n <= 4 or a in witnesses:
                    expected_stored.add(a)
                    row = lookup[a]
                    assert row["consistent"] == len(consistent)
                    assert abs(row["L_bits"] - bits) < 1e-9
                    assert abs(row["L_star_bits"] - bits) < 1e-9
        assert expected_witnesses == witnesses
        assert expected_stored == lookup.keys()


PATTERNS = [
    r"Item property (\d+) is (\d+)\.",
    r"The item has value (\d+) for feature (\d+)\.",
    r"For feature (\d+), choose value (\d+)\.",
]


def test_gold_texts_and_decoys(corpus):
    units = grouped(corpus, "units")
    texts = grouped(corpus, "texts")
    private = grouped(corpus, "secrets_private")
    witnesses = grouped(corpus, "witness_sets")
    for tid, rows in texts.items():
        by_feature = {u["predicate"]["feature"]: u for u in units[tid]}
        decoys, combos, singles = [], [], []
        for row in rows:
            gold = []
            parts = row["text"].rstrip(".").split(". ")
            templates = row["template_id"].split("+")
            assert len(parts) == len(templates)
            for tidx, part in zip(templates, parts):
                i = int(tidx.removeprefix("attr_"))
                match = re.fullmatch(PATTERNS[i], part + ".")
                assert match
                f, v = map(int, match.groups())
                if i == 1:
                    f, v = v, f
                unit = by_feature[f]
                if v == unit["predicate"]["value"]:
                    gold.append(unit["unit_id"])
                else:
                    assert row["role"] == "decoy"
                    assert row["decoy_of"] not in unit["satisfied_by"]
            assert row["gold_units"] == gold
            if row["role"] == "decoy":
                assert not gold and row["decoy_of"] != private[tid][0]["value"]
                decoys.append(row["decoy_of"])
            elif row["role"] == "combo":
                combos.append(gold)
            else:
                assert len(gold) == 1
                singles.extend(gold)
        assert len(set(decoys)) == len(decoys) == 3
        assert combos == witnesses[tid][0]["sets"]
        assert sorted(singles) == sorted(witnesses[tid][0]["universe"])


def test_reproducibility_and_fixture(tmp_path):
    left, right = (generate(tmp_path / tag, [8], 5) for tag in ("left", "right"))
    fixture = Path(__file__).resolve().parents[1] / "fixtures"
    assert sum(p.stat().st_size for p in fixture.iterdir()) <= 50000
    assert {p.name for p in fixture.iterdir()} == {p.name for p in left.iterdir()} - {"secrets_private.jsonl"}
    for p in left.iterdir():
        if p.name in ("targets.jsonl", "secrets_private.jsonl"):
            key = "salt" if p.name.startswith("secrets") else "value_commitment"
            a, b = p.read_bytes(), (right / p.name).read_bytes()
            pattern = rb'("' + key.encode() + rb'":")[0-9a-f]+(")'
            stripped = re.sub(pattern, rb'\1\2', a)
            assert a != b and stripped == re.sub(pattern, rb'\1\2', b)
            if key == "value_commitment":
                assert stripped == re.sub(pattern, rb'\1\2', (fixture / p.name).read_bytes())
        else:
            assert p.read_bytes() == (right / p.name).read_bytes() == (fixture / p.name).read_bytes()
    assert len(read(left / "targets.jsonl")) == 5


def test_witness_larger_than_four_and_threshold_equality():
    domain = set(range(6))
    units = [{"satisfied_by": domain - {x}} for x in range(1, 6)]
    counts, leakage, closure, witnesses = subsets(domain, units)
    assert witnesses == [31] and counts[31] == 1
    assert counts[15] == 2 and leakage[15] == closure[15] == math.log2(6) - 1


def test_failed_slots_and_truncation(tmp_path):
    failed = generate(tmp_path / "fail", [8], 2, features=1, retries=2)
    stats = json.loads((failed / "MANIFEST.json").read_text())["by_K"]["8"]
    assert stats["accepted"] == 0 and stats["discarded"] == 2 and stats["redraws"] == 4
    assert sum(stats["rejected_draws"].values()) == 6
    assert sum(stats["discarded_by_last_reason"].values()) == 2
    folder = generate(tmp_path / "many", [32], 1, features=13)
    assert len(read(folder / "units.jsonl")) == 12
    assert json.loads((folder / "MANIFEST.json").read_text())["by_K"]["32"]["units_truncated"] == 1
