"""Phase 2 grid (PREREG.md §3).

  python -m experiments.cogniguard_comparison_phase2.grid --repo ../CogniGuard --data <cogniguard_data> \
         --seeds 900-909 --tag dev
  python -m experiments.cogniguard_comparison_phase2.grid ... --seeds 0-29 --tag formal --points <operating_points.json>
"""

from __future__ import annotations

import argparse
import gzip
import json
from multiprocessing import Pool
from pathlib import Path

from experiments.cogniguard_comparison_phase2 import baselines as B
from experiments.cogniguard_comparison_phase2 import worlds as W
from experiments.cogniguard_comparison_phase2.simulate import run
from experiments.cogniguard_nowm_phase1 import world as P1

DATASETS = ("phase1", "eedi", "sumleaks")
PROPS = ("low", "high")
KS = (1, 2, 3)
OCELOT_B = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
TOM_RHO = (0.34, 0.5, 0.67, 0.75, 1.0)


def snapshot_rules(k):
    rules = [B.AccessOnly(), B.CAPD(k), B.ExactEnum(k), B.StaddonDef(k), B.CrowdControl(), B.WS04Quota(k),
             B.SumLeaksLocal(), B.SumLeaksCoDef()]
    if k > 1:
        rules.append(B.CAPD(1))
    rules += [B.SumLeaksToM(r) for r in TOM_RHO]
    rules += [B.OcelotPF(b, W.TRUST_MU, s) for s in ("field", "trajectory") for b in OCELOT_B]
    return rules


def path_rules(k, points):
    """One run per rule; budget methods at their frozen operating points (harm <= 5% on dev)."""
    rules = [B.AccessOnly(), B.CAPD(k), B.CrowdControl(), B.WS04Quota(k), B.SumLeaksLocal(), B.SumLeaksCoDef()]
    for fam, mk in (("OCELOT-PF[field]", lambda b: B.OcelotPF(b, W.TRUST_MU, "field")),
                    ("OCELOT-PF[trajectory]", lambda b: B.OcelotPF(b, W.TRUST_MU, "trajectory")),
                    ("SumLeaks-ToM", B.SumLeaksToM)):
        p = (points or {}).get(fam, {}).get("harm<=0.05")
        if p is not None:
            rules.append(mk(p))
    return rules


def make_world(ds, seed, prop, data: Path, repo: str):
    if ds == "phase1":
        real = P1.load_real(Path(repo), data / "nowm_phase1" / "real_cache.json")
        nli = data / "nowm_phase1" / "nli_judgments.jsonl"
        w = W.phase1_world(real, nli, seed, prop)
        v = P1.verifier_for(nli)
        return w, {id(e): v.verify(e.observation, e.artifact) for e in w.events if e.kind == "observation"}, "nli"
    return W.secrets_world(ds, W.load_dataset(ds, data), seed, prop), {}, "receipts"


def sens_job(args):
    """POST-HOC sensitivity (not preregistered): same snapshot, oracle = unbounded coalitions (k_eval = N)."""
    ds, seed, prop, data, repo, _ = args
    data = Path(data)
    out_s = []
    for k in KS:
        world, verified, layer = make_world(ds, seed, prop, data, repo)
        out, _rows = run(world, snapshot_rules(k), layer, k, "snapshot", verified, record=False,
                         k_eval=len(W.PRINCIPALS))
        key = dict(dataset=ds, seed=seed, prop=prop, k=k, layer=layer, mode="snapshot_unbounded_oracle")
        out_s += [{**key, "rule": n, **o} for n, o in out.items()]
    return out_s, []


def job(args):
    ds, seed, prop, data, repo, points_all = args
    data = Path(data)
    summaries, records = [], []
    for k in KS:
        world, verified, layer = make_world(ds, seed, prop, data, repo)
        out, rows = run(world, snapshot_rules(k), layer, k, "snapshot", verified)
        key = dict(dataset=ds, seed=seed, prop=prop, k=k, layer=layer)
        summaries += [{**key, "mode": "snapshot", "rule": n, **o} for n, o in out.items()]
        records += [{**key, "mode": "snapshot", **r} for r in rows]
        points = (points_all or {}).get(f"{ds}/{prop}/k{k}")
        for rule in path_rules(k, points):
            world, verified, layer = make_world(ds, seed, prop, data, repo)
            out, rows = run(world, [rule], layer, k, "path", verified)
            summaries += [{**key, "mode": "path", "rule": n, **o} for n, o in out.items()]
            records += [{**key, "mode": "path", "rule": rule.name, **r} for r in rows]
    return summaries, records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--points", type=Path)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--unbounded-oracle", action="store_true", help="post-hoc sensitivity run")
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition("-")
    points = json.loads(a.points.read_text()) if a.points else None
    out = a.data / "comparison_phase2" / a.tag
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(ds, s, p, str(a.data), a.repo, points) for ds in DATASETS for s in range(int(lo), int(hi or lo) + 1)
            for p in PROPS]
    with Pool(a.workers) as pool, open(out / "runs.jsonl", "w") as fs, gzip.open(out / "requests.jsonl.gz", "wt") as fr:
        for summaries, records in pool.imap_unordered(sens_job if a.unbounded_oracle else job, jobs):
            for s in summaries:
                fs.write(json.dumps(s) + "\n")
            for r in records:
                fr.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(out)


if __name__ == "__main__":
    main()
