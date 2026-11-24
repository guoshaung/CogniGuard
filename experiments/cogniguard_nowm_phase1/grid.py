"""Run the Phase-1 grid (PREREG.md §4).

  python -m experiments.cogniguard_nowm_phase1.grid --repo ../CogniGuard --data <dir> --seeds 900-904 --tag pilot
  python -m experiments.cogniguard_nowm_phase1.grid --repo ../CogniGuard --data <dir> --seeds 0-29 --tag formal
"""

from __future__ import annotations

import argparse
import gzip
import json
from multiprocessing import Pool
from pathlib import Path

from experiments.cogniguard_nowm_phase1 import policies as P
from experiments.cogniguard_nowm_phase1 import world as W
from experiments.cogniguard_nowm_phase1.simulate import simulate

KS = (1, 2, 3)
PROPS = ("low", "high")
LAYERS = ("receipts", "nli", "true")
BUDGETS = (2, 4, 6, 8, 10, 12, 16, 20, 24, 32)


def rules(world, k):
    small = W.TargetRegistry([t for t in world.targets._by_id.values() if max(map(len, t.witness_sets)) <= 2])
    out = [P.B0_Access()] + [P.B1_Budget(b, P.protected_units(world.targets)) for b in BUDGETS] + \
          [P.B2_Quota(k), P.B3_Pairwise(k, small), P.B4_Union(), P.CAPD(1)]
    if k > 1:
        out.append(P.CAPD(k))
    return out


def job(args):
    repo, data, seed, prop = args
    real = W.load_real(Path(repo), Path(data) / "real_cache.json")
    nli = Path(data) / "nli_judgments.jsonl"
    world = W.build(real, nli, seed, prop)
    v = W.verifier_for(nli)
    verified = {id(e): v.verify(e.observation, e.artifact) for e in world.events if e.kind == "observation"}
    summaries, records = [], []
    for k in KS:
        for rule in rules(world, k):
            layers = ("receipts",) if isinstance(rule, P.B0_Access) else LAYERS
            for layer in layers:
                rows, s = simulate(world, rule, layer, k, verified)
                key = dict(seed=seed, prop=prop, k=k, rule=rule.name, layer=layer)
                summaries.append({**key, **s})
                records.extend({**key, **r} for r in rows)
    return summaries, records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    W.load_real(Path(a.repo), a.data / "real_cache.json")
    out = a.data / a.tag
    out.mkdir(parents=True, exist_ok=True)
    with Pool(a.workers) as pool, open(out / "runs.jsonl", "w") as fs, gzip.open(out / "requests.jsonl.gz", "wt") as fr:
        for summaries, records in pool.imap_unordered(job, [(a.repo, str(a.data), s, p) for s in seeds for p in PROPS]):
            for s in summaries:
                fs.write(json.dumps(s) + "\n")
            for r in records:
                fr.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(out)


if __name__ == "__main__":
    main()
