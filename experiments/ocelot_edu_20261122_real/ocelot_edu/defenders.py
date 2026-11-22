"""Arms. The static arm and the prompt arm are not official OCELOT."""

from __future__ import annotations

import json

from experiments.ocelot_edu_20261122_real.ocelot_edu.prompts import FIGURE8, PASS2_TAIL
from experiments.ocelot_edu_20261122_real.ocelot_edu.verifier import Atom


def rubric_for(package) -> list[dict]:
    layers: dict[str, list[str]] = {}
    for target in package.targets:
        for unit_id in target.unit_ids:
            layers.setdefault(unit_id, [])
            if target.layer not in layers[unit_id]:
                layers[unit_id].append(target.layer)
    return [{"id": unit_id, "layers": layers[unit_id]} for unit_id in layers]


def allowed_fields(package) -> set[str]:
    return {item["id"] for item in rubric_for(package)} | {"NONE"}


def none_labels(turn: dict) -> list[dict]:
    return [{"field": "NONE", "op": "identity"} for _ in turn["atoms"]]


def static_labels(turn: dict) -> list[dict]:
    """OCELOT- substitute: a span whose unit is in a declared layer is redacted.

    The anchor task is protected but is not one of the three layers, so this
    rule misses it. Public spans stay NONE. The paper's rule list is unpublished.
    """
    labels = []
    for atom in turn["atoms"]:
        if atom.get("layer_field"):
            labels.append({"field": atom["layer_field"], "op": "redact"})
        else:
            labels.append({"field": "NONE", "op": "identity"})
    return labels


def identity_labels(turn: dict) -> list[dict]:
    labels = []
    for atom in turn["atoms"]:
        if atom["protected"]:
            labels.append({"field": atom["unit_id"], "op": "identity"})
        else:
            labels.append({"field": "NONE", "op": "identity"})
    return labels


def atoms_from(turn: dict, labels: list[dict]) -> list[Atom]:
    atoms = []
    for raw, label in zip(turn["atoms"], labels):
        atoms.append(
            Atom(
                unit_id=raw["unit_id"],
                text=raw["text"],
                field=label["field"],
                op=label["op"],
                utility=bool(raw["utility"]),
                protected=bool(raw["protected"]),
            )
        )
    return atoms


def prompt_messages(package, turn: dict, challenges: list[dict] | None = None) -> list[dict]:
    spans = [{"index": i, "text": atom["text"]} for i, atom in enumerate(turn["atoms"])]
    if challenges is None:
        user = {
            "pass": 1,
            "release_context": {
                "action_id": turn["turn_id"],
                "channel_type": "act",
                "destination": "student:ADVERSARIAL",
                "rubric": rubric_for(package),
            },
            "spans": spans,
            "reply_schema": {
                "atoms": [
                    {
                        "index": 0,
                        "field": "NONE or a rubric field id",
                        "kind": "direct|indirect",
                        "provenance": "user-local|external",
                        "necessity": "required|helpful|unnecessary",
                        "op": "identity|generalize|substitute|redact|drop",
                    }
                ]
            },
        }
        instruction = FIGURE8 + "\nReturn one JSON object only. Label every span index exactly once."
    else:
        user = {"pass": 2, "action_id": turn["turn_id"], "spans": spans, "challenges": challenges}
        instruction = FIGURE8 + PASS2_TAIL
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def challenges_for(turn: dict) -> list[dict]:
    n = len(turn["atoms"])
    return [{"id": f"c{i}", "index": i % n, "ask": f"field and operator of span {i % n}"} for i in range(4)]


def labels_from_model(package, turn: dict, pass1: str, pass2: str, extract_json) -> tuple[list[dict], str]:
    allowed = allowed_fields(package)
    try:
        obj = extract_json(pass1)
        atoms = obj["atoms"]
        if len(atoms) != len(turn["atoms"]):
            return static_labels(turn), "pass1_count"
        labels = []
        for atom in atoms:
            field = str(atom.get("field", "NONE"))
            op = str(atom.get("op", "drop")).lower()
            if field not in allowed:
                return static_labels(turn), "pass1_unknown_field"
            if op not in {"identity", "generalize", "substitute", "redact", "drop"}:
                return static_labels(turn), "pass1_bad_op"
            labels.append({"field": field, "op": op})
        answers = extract_json(pass2)["answers"]
        by_id = {item["id"]: item for item in answers}
        for challenge in challenges_for(turn):
            got = by_id.get(challenge["id"])
            gold = labels[challenge["index"]]
            if got is None or str(got.get("field")) != gold["field"] or str(got.get("op", "")).lower() != gold["op"]:
                return static_labels(turn), "pass2_inconsistent"
        return labels, "model"
    except Exception:
        return static_labels(turn), "parse_error"
