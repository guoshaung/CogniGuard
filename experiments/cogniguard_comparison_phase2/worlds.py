"""Worlds for Phase 2 (METHOD.md §2). Every world exposes the Phase-1 `World` interface plus
`leak[target_id](units) -> bits` (min-entropy leakage, uniform prior, identity gain) and
`owner[target_id]` for per-trajectory budgets.

  phase1    : the frozen Phase-1 world (real propagation + BGE+NLI evidence, synthetic witnesses).
              Bit model: each target is a |W|-bit secret, each witness unit reveals one bit, so
              L(A) = |A ∩ W| and L > tau = |W| - 1  <=>  the witness is complete (Lemma 1).
  eedi      : official Eedi exam secrets (E6 data, MANIFEST d4401ef4…), real predicate witnesses,
              exact L(A) = log2(K/|S_A|) from the frozen E5 Secret class.
  sumleaks  : Sum Leaks join secrets (E7 data, MANIFEST 7c53e01b…), real join witnesses, exact L.
For eedi / sumleaks the governance structure (who holds what, requests) is synthetic and there is
no text evidence, so the nli layer equals receipts.
"""

from __future__ import annotations

import random
from pathlib import Path

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from experiments.capd_e5_20261123.data import load_secrets as load_e5
from experiments.capd_e7_20261123.data import load_secrets as load_e7
from experiments.cogniguard_nowm_phase1 import world as P1

STUDENTS, TA, COUNSELOR, EXT = P1.STUDENTS, P1.TA, P1.COUNSELOR, P1.EXT
PRINCIPALS = P1.PRINCIPALS
TRUST_MU = {**{s: 2.0 for s in STUDENTS}, TA: 1.0, COUNSELOR: 1.0, EXT: 4.0}   # OCELOT Pre-Reg. A: 1/2/4
N_SECRETS = 24


def phase1_world(real, nli_path, seed, prop):
    w = P1.build(real, nli_path, seed, prop)
    leak, owner = {}, {}
    for t in w.targets._by_id.values():
        wit = next(iter(t.witness_sets))
        leak[t.target_id] = (lambda W: (lambda A: float(len(frozenset(A) & W))))(wit)
        owner[t.target_id] = t.owner_principal_id
    w.leak, w.owner, w.tau = leak, owner, {t: len(next(iter(x.witness_sets))) - 1.0
                                           for t, x in w.targets._by_id.items()}
    w.dataset = "phase1"
    return w


def load_dataset(name: str, data_root: Path):
    if name == "eedi":
        return load_e5(16, data_root / "eedi_exam")
    if name == "sumleaks":
        return load_e7(data_root / "sumleaks")
    raise ValueError(name)


def secrets_world(name, secrets, seed, prop):
    rng = random.Random(f"phase2/{name}/{seed}/{prop}")
    chosen = rng.sample(list(secrets), min(N_SECRETS, len(secrets)))
    receipts = {p: set() for p in PRINCIPALS}
    targets, leak, owner, tau, wsize = [], {}, {}, {}, {}
    for s in chosen:
        wits = s.witness_sets
        # Issue a random subset of units so that the UNION of all issued units completes no witness
        # (clean initial state: no historical reconstruction for any coalition size).
        issued = set()
        for u in rng.sample(sorted(s.units), len(s.units)):
            if rng.random() < 0.6 and not any(w <= (issued | {u}) for w in wits):
                issued.add(u)
                receipts[rng.choice(STUDENTS)].add(u)
        t = ProtectedTarget(s.target_id, P1.TEACHER, P1.ORG, wits, kind="teaching_asset")
        targets.append(t)
        leak[s.target_id] = (lambda sec: (lambda A: sec.leakage(frozenset(A) & frozenset(sec.units))))(s)
        owner[s.target_id] = P1.TEACHER
        tau[s.target_id] = max(__import__("math").log2(s.K) - 1, 0.5)   # E7 rule; = log2K-1 for K>=3
        wsize[s.target_id] = min(len(w) for w in wits)
    units = sorted({u for s in chosen for u in s.units})
    resources = sorted({u[0] for u in units})
    owners = [AssetOwnership(r, P1.TEACHER, P1.ORG) for r in resources]
    members = [Membership(p, P1.ORG, "student") for p in STUDENTS] + [
        Membership(TA, P1.ORG, "agent"), Membership(COUNSELOR, P1.ORG, "agent"), Membership(P1.TEACHER, P1.ORG, "teacher")]
    grants = [AccessGrant(p, r, "study", 1) for p in STUDENTS + (TA, COUNSELOR) for r in resources]
    access_before = AccessRegistry(owners, members, grants)
    revoked = set(rng.sample(resources, max(1, len(resources) // 3)))
    access_after = AccessRegistry(owners, members, [g for g in grants if not (
        g.grantee_principal_id == TA and g.resource_id in revoked)])
    events = []
    if prop == "high":
        for _ in range(15):
            src = rng.choice([p for p in STUDENTS if receipts[p]])
            dst = rng.choice([p for p in PRINCIPALS if p not in (src, EXT)])
            u = rng.choice(sorted(receipts[src]))
            events.append(P1.Event(rng.uniform(1, P1.N_REQUESTS), "untracked", dst, (u,), sender=src,
                                   role="synthetic:transfer"))
    for i in range(P1.N_REQUESTS):
        r = rng.random()
        p = rng.choice(STUDENTS) if r < 0.6 else TA if r < 0.75 else COUNSELOR if r < 0.9 else EXT
        events.append(P1.Event(i + 0.5, "request", p, (rng.choice(units),), request_id=f"q{i}", purpose="study",
                               role="external" if p == EXT else "learning"))
    events.sort(key=lambda e: (e.t, {"untracked": 0, "observation": 1, "request": 2}[e.kind]))
    w = P1.World(seed, prop, access_before, access_after, P1.N_REQUESTS / 2, TargetRegistry(targets), wsize,
                 {p: frozenset(v) for p, v in receipts.items()}, events,
                 meta={"dataset": name, "secrets": [s.target_id for s in chosen]})
    w.leak, w.owner, w.tau, w.dataset = leak, owner, tau, name
    return w
