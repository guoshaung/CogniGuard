"""Load a code-domain witness file into protected targets."""

from __future__ import annotations

import json
from pathlib import Path

from cogniguard.governance.targets import ProtectedTarget


def load_code_targets(
    path: str | Path,
    *,
    resource_id: str,
    owner_principal_id: str,
    org_id: str,
) -> tuple[ProtectedTarget, ...]:
    """Read {"targets": [{"target_id", "witness_sets": [["f1", "f2"]]}]}.

    Witness names are unit ids. resource_id is attached here so the gate sees
    the same (resource_id, unit_id) pairs the asset splitter emits.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    loaded: list[ProtectedTarget] = []
    for item in payload["targets"]:
        witnesses = tuple(
            frozenset((resource_id, str(unit_id)) for unit_id in witness)
            for witness in item["witness_sets"]
        )
        loaded.append(
            ProtectedTarget(
                target_id=str(item["target_id"]),
                owner_principal_id=owner_principal_id,
                org_id=org_id,
                witness_sets=witnesses,
                value=float(item.get("value", 1.0)),
            )
        )
    return tuple(loaded)
