"""Eedi generator (revision 2.1): exhaustive structure checks on a small run."""
import hashlib
import hmac
import json
import math
import re
from collections import defaultdict
from itertools import combinations

import pytest

from experiments.datasets.audit_io import raw_dir
from experiments.datasets.eedi_exam.generate import Bank, generate, load_bank

RAW = raw_dir() / "eedi"
pytestmark = pytest.mark.skipif(not (RAW / "train.csv").exists(), reason="Eedi raw data absent")


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def grouped(folder, name):
    rows = defaultdict(list)
    for row in read(folder / f"{name}.jsonl"):
        rows[row["target_id"]].append(row)
    return rows


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("eedi"), RAW, count=12)


@pytest.fixture(scope="module")
def bank():
    return Bank(load_bank(RAW)[0])


def test_structure_against_intersection_oracle(corpus, bank):
    groups = {k: grouped(corpus, k) for k in ("units", "secrets_private", "witness_sets", "leakage")}
    targets = read(corpus / "targets.jsonl")
    manifest = json.loads((corpus / "MANIFEST.json").read_text())
    assert len(targets) == sum(v["accepted"] for v in manifest["by_K"].values()) > 0
    for t in targets:
        tid, k, domain = t["target_id"], t["K"], set(t["domain"])
        assert len(domain) == k and t["tau_bits"] == math.log2(k) - 1
        secret, = groups["secrets_private"][tid]
        truth = secret["value"]
        expected = hmac.new(secret["salt"].encode(), truth.encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(t["value_commitment"], expected)
        support = {}
        for u in groups["units"][tid]:
            pred = (u["predicate"]["feature"], u["predicate"]["value"])
            assert len(bank.index[pred]) > 1, "direct identifiers stay out of the universe"
            assert set(u["satisfied_by"]) == bank.index[pred] & domain
            assert truth in u["satisfied_by"] and len(u["satisfied_by"]) >= 2
            support[u["unit_id"]] = set(u["satisfied_by"])
        assert len(support) <= 12
        witness, = groups["witness_sets"][tid]
        assert set(witness["universe"]) == support.keys()
        witnesses = {frozenset(w) for w in witness["sets"]}
        assert any(2 <= len(w) <= 4 for w in witnesses)
        lookup = {frozenset(r["units"]): r for r in groups["leakage"][tid]}
        found = set()
        for n in range(len(support) + 1):
            for chosen in combinations(support, n):
                a = frozenset(chosen)
                consistent = domain.intersection(*(support[u] for u in a))
                bits = math.log2(k / len(consistent))
                over = bits > t["tau_bits"]
                assert over == any(w <= a for w in witnesses)  # Lemma 1
                if over and all(len(domain.intersection(*(support[v] for v in a - {u}))) >= 2 for u in a):
                    found.add(a)
                if n <= 4 or a in witnesses:
                    assert abs(lookup[a]["L_bits"] - bits) < 1e-9
                    assert abs(lookup[a]["L_star_bits"] - bits) < 1e-9
        assert found == witnesses


def test_texts_and_decoys(corpus, bank):
    private = {r["target_id"]: r["value"] for r in read(corpus / "secrets_private.jsonl")}
    witnesses = {r["target_id"]: r["sets"] for r in read(corpus / "witness_sets.jsonl")}
    texts = grouped(corpus, "texts")
    assert texts.keys() == private.keys()
    for tid, rows in texts.items():
        decoys = [r for r in rows if r["role"] == "decoy"]
        assert decoys and all(r["decoy_of"] != private[tid] and not r["gold_units"] for r in decoys)
        assert [r["gold_units"] for r in rows if r["role"] == "combo"] == witnesses[tid]
        for r in rows:
            assert len(r["template_id"].split("+")) == max(1, len(r["gold_units"]))


def test_reproducible_except_salts(tmp_path):
    left, right = (generate(tmp_path / tag, RAW, ks=(8,), count=4) for tag in ("l", "r"))
    for p in left.iterdir():
        a, b = p.read_bytes(), (right / p.name).read_bytes()
        if p.name in ("targets.jsonl", "secrets_private.jsonl"):
            key = b"salt" if p.name.startswith("secrets") else b"value_commitment"
            pattern = rb'("' + key + rb'":")[0-9a-f]+(")'
            assert re.sub(pattern, rb"\1\2", a) == re.sub(pattern, rb"\1\2", b)
        else:
            assert a == b


def test_refuses_output_inside_checkout():
    from pathlib import Path
    with pytest.raises(ValueError):
        generate(Path(__file__).resolve().parent / "out", RAW, count=1)
