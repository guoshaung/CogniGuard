"""Defenders. The prompt arm is not an official OCELOT checkpoint."""

from __future__ import annotations

from experiments.ocelot_edu_20261121.ocelot_edu.assets import all_units
from experiments.ocelot_edu_20261121.ocelot_edu.verifier import Atom

TRIGGER_MARKERS = {
    frag.marker: unit.unit_id
    for unit in all_units()
    if unit.kind != "pedagogy"
    for frag in unit.fragments
}


def atoms_from_labels(turn: dict, labels: list[dict]) -> list[Atom]:
    atoms = []
    for raw, lab in zip(turn["atoms"], labels):
        atoms.append(
            Atom(
                span=raw["span"],
                field=lab["field"],
                kind=lab.get("kind", "direct" if lab["field"] != "NONE" else "none"),
                necessity=lab.get("necessity", "unnecessary"),
                op=lab["op"],
                marker=raw["marker"],
                protected=bool(raw["protected"]),
            )
        )
    return atoms


def none_labels(turn: dict) -> list[dict]:
    return [{"field": "NONE", "op": "identity", "kind": "none", "necessity": "unnecessary"} for _ in turn["atoms"]]


def static_labels(turn: dict) -> list[dict]:
    """OCELOT- substitute: explicit trigger spans are redacted; everything else is NONE.

    The paper does not publish the rule list. This matches the published
    description: the rule labeler over-redacts explicit fields and misses
    non-trigger text, including pedagogy.
    """
    labels = []
    for raw in turn["atoms"]:
        span = raw["span"]
        hit = next((fid for marker, fid in TRIGGER_MARKERS.items() if marker in span), None)
        if hit is not None:
            labels.append(
                {
                    "field": hit,
                    "op": "redact",
                    "kind": "direct",
                    "necessity": "unnecessary",
                }
            )
        else:
            labels.append({"field": "NONE", "op": "identity", "kind": "none", "necessity": "unnecessary"})
    return labels


def nemo_release(turn: dict, adapter) -> str:
    result = adapter.check_output(turn["candidate"], {"source": "ocelot_edu"})
    if result.get("decision") == "allow":
        return turn["candidate"]
    return ""
