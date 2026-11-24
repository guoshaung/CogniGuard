"""Governance-side scenario loading. Rejects any evaluation field (gold, truth, oracle, label)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.schema import SCHEMA_VERSION, DisclosureRequest, SchemaError, _check_no_gold


def unit_key(u) -> str:
    return f"{u[0]}|{u[1]}"


def parse_unit_key(key: str):
    r, u = key.split("|", 1)
    return (r, u)


@dataclass
class Scenario:
    scenario_id: str
    domain: str
    access: AccessRegistry
    targets: TargetRegistry
    receipts: dict
    artifacts: list
    requests: list
    phrasings: dict
    k: int
    f: int
    raw: dict


def load_scenario(path: Path) -> Scenario:
    d = json.loads(Path(path).read_text())
    _check_no_gold(d)
    if d.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError("scenario schema_version")
    org = d["org_id"]
    access = AccessRegistry(
        [AssetOwnership(r["resource_id"], r["owner_principal_id"], org) for r in d["resources"]],
        [Membership(p["principal_id"], org, p["role"]) for p in d["principals"]],
        [AccessGrant(g["grantee_principal_id"], g["resource_id"], g["purpose"], 1) for g in d["grants"]],
    )
    targets = TargetRegistry([
        ProtectedTarget(t["target_id"], t["owner_principal_id"], org,
                        tuple(frozenset(tuple(u) for u in w) for w in t["witness_sets"]))
        for t in d["targets"]])
    receipts = {p: frozenset(tuple(u) for u in us) for p, us in d["receipts"].items()}
    artifacts = [Artifact(a["artifact_id"], a["holder_principal_id"], a.get("text") or "", float(a["observed_at"]))
                 for a in d["artifacts"]]
    requests = [DisclosureRequest(r["request_id"], r["principal_id"], r["purpose"], org,
                                  tuple(tuple(u) for u in r["release_units"]), float(r["now"]))
                for r in d["requests"]]
    phrasings = {parse_unit_key(k): tuple(v) for k, v in d.get("unit_phrasings", {}).items()}
    return Scenario(d["scenario_id"], d["domain"], access, targets, receipts, artifacts, requests,
                    phrasings, int(d["k"]), int(d["f"]), d)
