"""Exploratory, not pre-registered: A1 (meter only over-counts) for three meters.

Texts: the dataset's own texts (unit / combo / decoy), plus held-out rephrasings
rendered from heldout_templates.json, which was committed before PredicateMeter
was written. Store for the predicate meter: slot = the feature number, or the
ordinal word for f and f+1 (0- or 1-based reading); value = the value number.
No keyword such as "feature" is required, so unseen wording still matches.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from cogniguard.runtime.meters import (
    LexicalMeter,
    PredicateMeter,
    UnitContentStore,
    UnitPredicate,
    UnitPredicateStore,
)

from experiments.capd_e5_20261123.data import load_predicates, load_secrets, load_texts

HERE = Path(__file__).resolve().parent
KS = (8, 16, 32)
SEED = 20261124
WORDS = "zero one two three four five six seven eight nine ten".split()
ORDINALS = "zeroth first second third fourth fifth sixth seventh eighth ninth tenth".split()
TEMPLATES = json.loads((HERE / "heldout_templates.json").read_text())["templates"]


def render(template: str, f: int, v: int) -> str:
    return template.format(f=f, v=v, fw=WORDS[f], vw=WORDS[v], fo=ORDINALS[f + 1])


def heldout_texts(K: int) -> list[dict]:
    rng = random.Random(SEED + K)
    preds = load_predicates(K)
    texts = []
    for (tid, uid), p in sorted(preds.items()):
        for template in TEMPLATES:
            texts.append({"target_id": tid, "role": "unit", "gold_units": [uid],
                          "text": render(template, p["feature"], p["value"])})
    for secret in load_secrets(K):
        for witness in secret.witness_sets:
            parts = [render(rng.choice(TEMPLATES), preds[u]["feature"], preds[u]["value"])
                     for u in sorted(witness)]
            texts.append({"target_id": secret.target_id, "role": "combo",
                          "gold_units": [u[1] for u in sorted(witness)], "text": " ".join(parts)})
    return texts


def meters(K: int) -> dict:
    preds = load_predicates(K)
    lexical = LexicalMeter(UnitContentStore(
        {ref: f"Item property {p['feature']} is {p['value']}." for ref, p in preds.items()}))
    store = UnitPredicateStore({
        ref: UnitPredicate(
            (str(p["feature"]), ORDINALS[p["feature"]], ORDINALS[p["feature"] + 1]),
            (str(p["value"]),),
        )
        for ref, p in preds.items()
    })
    return {
        "lexical": lexical,
        "predicate_text": PredicateMeter(store),
        "predicate_sentence": PredicateMeter(store, scope="sentence"),
    }


def score(meter, texts, scope_of) -> dict:
    s = defaultdict(lambda: defaultdict(int))
    for text in texts:
        tid = text["target_id"]
        found = meter.measure(text["text"], candidate_units=frozenset(scope_of[tid])).units
        gold = {(tid, u) for u in text["gold_units"]}
        r = s[text["role"]]
        r["texts"] += 1
        if text["role"] == "decoy":
            r["flagged"] += bool(found)
            r["extra"] += len(found)
        else:
            r["gold"] += len(gold)
            r["missed"] += len(gold - found)
            r["extra"] += len(found - gold)
    out = {}
    for role, r in s.items():
        if role == "decoy":
            out[role] = {"texts": r["texts"], "false_flag_rate": r["flagged"] / r["texts"],
                         "extra_per_text": r["extra"] / r["texts"]}
        else:
            out[role] = {"texts": r["texts"], "unit_miss_rate": r["missed"] / r["gold"],
                         "extra_per_text": r["extra"] / r["texts"]}
    return out


def main() -> None:
    result = {}
    for K in KS:
        scope_of = defaultdict(set)
        for ref in load_predicates(K):
            scope_of[ref[0]].add(ref)
        sets = {"original": load_texts(K), "heldout": heldout_texts(K)}
        result[str(K)] = {
            name: {corpus: score(m, texts, scope_of) for corpus, texts in sets.items()}
            for name, m in meters(K).items()
        }
    out = HERE / "predicate_meter_a1.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
