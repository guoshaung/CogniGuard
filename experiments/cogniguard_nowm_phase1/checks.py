"""Pre-freeze checks (PREREG.md §2): mathematical correctness and scenario non-degeneracy.

  python -m experiments.cogniguard_nowm_phase1.checks --repo ../CogniGuard --data <dir> --seeds 900-904
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
from collections import Counter
from pathlib import Path

from cogniguard.governance.reconstruction import check_release
from experiments.cogniguard_nowm_phase1 import policies as P
from experiments.cogniguard_nowm_phase1 import world as W


def brute_force_safe(targets, recipient, release, knowledge, k) -> bool:
    """Exact k-coalition enumeration (independent of the DP)."""
    others = [p for p in knowledge if p != recipient]
    held = knowledge.get(recipient, frozenset()) | frozenset(release)
    for u in release:
        for t in targets.targets_for_unit(u):
            for w in t.witness_sets:
                for size in range(0, k):
                    for c in itertools.combinations(others, size):
                        if w <= held.union(*(knowledge[p] for p in c)):
                            return False
    return True


def random_state(world, rng):
    units = sorted({u for t in world.targets._by_id.values() for w in t.witness_sets for u in w})
    return {p: frozenset(rng.sample(units, rng.randint(0, 6))) for p in W.PRINCIPALS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--seeds", default="900-904")
    a = ap.parse_args()
    lo, _, hi = a.seeds.partition("-")
    real = W.load_real(Path(a.repo), a.data / "real_cache.json")
    nli = a.data / "nli_judgments.jsonl"
    report = {"dp_vs_bruteforce": Counter(), "quota_implies_kSafe": Counter(), "worlds": []}
    for seed in range(int(lo), int(hi) + 1):
        for prop in ("low", "high"):
            world = W.build(real, nli, seed, prop)
            rng = random.Random(seed)
            units = sorted({u for t in world.targets._by_id.values() for w in t.witness_sets for u in w})
            for _ in range(400):
                know, r, u, k = random_state(world, rng), rng.choice(W.PRINCIPALS), rng.choice(units), rng.randint(1, 3)
                dp = check_release(world.targets, r, {u}, know, k).safe
                bf = brute_force_safe(world.targets, r, {u}, know, k)
                report["dp_vs_bruteforce"]["agree" if dp == bf else "DISAGREE"] += 1
                # WS04: a state reached only through quota-respecting holdings is k-safe.
                q = P.B2_Quota(k)
                capped = {p: frozenset(x for x in v if all(len(v & w) <= (len(w) - 1) // k
                                                              for t in world.targets.targets_for_unit(x)
                                                              for w in t.witness_sets)) for p, v in know.items()}
                if all(q.allows(world.targets, p, (), capped) for p in capped) and q.allows(world.targets, r, (u,), capped):
                    report["quota_implies_kSafe"]["safe" if check_release(world.targets, r, {u}, capped, k).safe
                                                  else "UNSAFE"] += 1
            ws = Counter(world.witness_sizes.values())
            report["worlds"].append({"seed": seed, "prop": prop, "witness_sizes": dict(sorted(ws.items())),
                                     "untracked": sum(e.kind == "untracked" for e in world.events),
                                     "observations": sum(e.kind == "observation" for e in world.events)})
    report["dp_vs_bruteforce"] = dict(report["dp_vs_bruteforce"])
    report["quota_implies_kSafe"] = dict(report["quota_implies_kSafe"])
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
