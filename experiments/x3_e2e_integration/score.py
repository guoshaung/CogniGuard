"""X3-E2E scorer: the ONLY module that reads gold. It runs after governance decisions are
written and never feeds anything back to governance.

  python -m experiments.x3_e2e_integration.score --run OUT/<scenario>/<arm>__<mode> \
      --scenario S.json --gold G.json [--observations O.jsonl ...]
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
from pathlib import Path

from cogniguard.governance.reconstruction import check_release
from experiments.x3_e2e_integration.scenario import load_scenario


def load_gold(path: Path) -> dict:
    g = json.loads(Path(path).read_text())
    if g.get("schema_version") != "pe-1.0":
        raise ValueError("gold schema_version")
    return g


def _true_knowledge(base, deliveries, acquisitions, t):
    k = {p: set(u) for p, u in base.items()}
    for (tt, p, units) in deliveries:
        if tt < t:
            k.setdefault(p, set()).update(units)
    for a in acquisitions:
        if a["t"] <= t:
            k.setdefault(a["principal_id"], set()).add(tuple(a["unit"]))
    return {p: frozenset(u) for p, u in k.items()}


def _covered(targets, knowledge, k):
    out = set()
    names = sorted(knowledge)
    for size in range(1, k + 1):
        for coalition in itertools.combinations(names, size):
            view = frozenset().union(*(knowledge[p] for p in coalition))
            for t in targets.targets if hasattr(targets, "targets") else targets:
                for w in t.witness_sets:
                    if w <= view:
                        out.add((coalition, t.target_id, tuple(sorted(w))))
    return out


def score(run_dir: Path, scenario_path: Path, gold_path: Path, observation_paths=()):
    sc = load_scenario(scenario_path)
    gold = load_gold(gold_path)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    decisions = [json.loads(l) for l in (run_dir / "decisions.jsonl").read_text().splitlines() if l]
    if manifest["scenario_id"] != gold["scenario_id"]:
        raise ValueError("gold belongs to another scenario")
    by_id = {r.request_id: r for r in sc.requests}
    cluster_of = {r["request_id"]: r.get("cluster_id", "all") for r in sc.raw["requests"]}
    per_cluster: dict = {}
    roles = gold.get("request_roles", {})
    acq = gold.get("untracked_acquisitions", [])
    deliveries, m = [], dict(harmful=0, unauthorized_success=0, false_refusal=0, oracle_allows=0,
                              normal=0, normal_allowed=0, probe=0, probe_allowed=0)
    target_list = [sc.targets.get(t["target_id"]) for t in sc.raw["targets"]]
    for d in decisions:
        r = by_id[d["request_id"]]
        authorized = all(sc.access.is_authorized(r.principal_id, res, r.purpose, r.acting_org_id, r.now)
                         for res in r.resources)
        truth = _true_knowledge(sc.receipts, deliveries, acq, r.now)
        oracle = authorized and check_release(sc.targets, r.principal_id, set(r.release_units), truth, sc.k).safe
        m["oracle_allows"] += oracle
        m["harmful"] += d["allowed"] and authorized and not oracle
        m["unauthorized_success"] += d["allowed"] and not authorized
        m["false_refusal"] += (not d["allowed"]) and oracle
        pc = per_cluster.setdefault(cluster_of[r.request_id], {"harmful": 0, "false_refusal": 0,
                                                                "oracle_allows": 0, "unauthorized_success": 0})
        pc["harmful"] += d["allowed"] and authorized and not oracle
        pc["false_refusal"] += (not d["allowed"]) and oracle
        pc["oracle_allows"] += oracle
        pc["unauthorized_success"] += d["allowed"] and not authorized
        role = roles.get(r.request_id, "normal")
        m[role] = m.get(role, 0) + 1
        m[f"{role}_allowed"] = m.get(f"{role}_allowed", 0) + d["allowed"]
        if d["allowed"]:
            deliveries.append((r.now, r.principal_id, r.release_units))
    end = float("inf")
    before = _covered(target_list, _true_knowledge(sc.receipts, [], acq, end), sc.k)
    after = _covered(target_list, _true_knowledge(sc.receipts, deliveries, acq, end), sc.k)
    out = {
        **manifest, **m,
        # Utility: share of requests the oracle allows (authorized and truly safe) that the arm allows.
        "utility": (m["oracle_allows"] - m["false_refusal"]) / m["oracle_allows"] if m["oracle_allows"] else None,
        "false_refusal_rate": m["false_refusal"] / m["oracle_allows"] if m["oracle_allows"] else None,
        "coalition_violations_caused": len(after - before),
        "per_cluster": per_cluster,
        "latency_ms_median": 1000 * statistics.median([d["seconds"] for d in decisions]) if decisions else None,
    }
    if observation_paths:
        out["attribution"] = attribution(observation_paths, gold)
    return out


def attribution(paths, gold):
    """Descriptive: issuance candidates vs the issuances an artifact really descends from."""
    truth = gold.get("artifact_issuances", {})
    hit = got = want = wrong_obs = n = 0
    for p in paths:
        for line in Path(p).read_text().splitlines():
            o = json.loads(line)
            if o["artifact_id"] not in truth:
                continue
            ids = {c["id"] for c in o["issuance_candidates"].get("items", [])}
            real = set(truth[o["artifact_id"]])
            n += 1
            hit += len(ids & real)
            got += len(ids)
            want += len(real)
            wrong_obs += bool(ids - real)
    return {"observations": n, "issuance_precision": hit / got if got else None,
            "issuance_recall": hit / want if want else None,
            "wrong_attribution_rate": wrong_obs / n if n else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--scenario", required=True, type=Path)
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--observations", nargs="*", default=[], type=Path)
    a = ap.parse_args()
    res = score(a.run, a.scenario, a.gold, a.observations)
    (a.run / "score.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps({k: res[k] for k in ("arm", "mode", "harmful", "unauthorized_success",
                                          "false_refusal", "utility", "coalition_violations_caused")}))


if __name__ == "__main__":
    main()
