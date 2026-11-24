"""Unified request stream for CogniGuard-NoWM Phase 1 (METHOD.md §2).

REAL (from Codex, read via git, never regenerated):
  * 12 OpenStax teaching sources, 36 fact units and their registered phrasings  (codex/hsw-st@065bb82)
  * 15 real Qwen2.5-7B propagation chains, plain (unwatermarked) variant, endpoints at depth 1/3/5
  * per-endpoint retained-fact annotations (TRUE state only; governance never reads them)
  * frozen BGE asset retrieval per endpoint (065bb82) and frozen NLI unit judgments (codex/gate-w0-real@fcf1374)
SYNTHETIC (seeded governance structure, labelled as such):
  * principals, grants, issuance receipts, teacher secret witnesses (w = 2..5),
    student-profile secrets (synthetic signal units, w = 3..5), request stream,
    who holds each propagation hop, untracked profile leaks, mid-stream revocation.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.verify import RuleVerifier
from experiments.x3_e2e_integration.adapters.codex import to_observation
from experiments.x3_e2e_integration.checkers import NliReplayChecker

CODEX_PILOT, CODEX_NLI = "065bb82", "fcf1374"
ORG = "school"
STUDENTS = tuple(f"S{i}" for i in range(1, 7))
TA, COUNSELOR, EXT, TEACHER = "TA", "COUNSELOR", "EXT", "T"
PRINCIPALS = STUDENTS + (TA, COUNSELOR, EXT)
TEACHER_W = (2, 2, 3, 3, 3, 4, 4, 4, 5, 5)          # witness sizes of teacher secrets
PROFILE_W = {s: w for s, w in zip(STUDENTS, (3, 3, 4, 4, 5, 5))}
N_REQUESTS = 300
PROPAGATION = {"low": (1,), "high": (1, 3, 5)}       # endpoint depths that propagate


def _git(repo: Path, ref: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], check=True,
                          capture_output=True, text=True).stdout


def load_real(repo: Path, cache: Path) -> dict:
    """Read Codex's frozen files once; cache with their sha256."""
    if cache.exists():
        return json.loads(cache.read_text())
    P = "experiments/hsw_provenance_next"
    files = {
        "sources": _git(repo, CODEX_PILOT, "experiments/hsw_provenance/propagation/sources.json"),
        "hops": _git(repo, CODEX_PILOT, f"{P}/real/pilot/hops.jsonl"),
        "annotations": _git(repo, CODEX_PILOT, f"{P}/real/pilot/annotations.jsonl"),
        "content": _git(repo, CODEX_PILOT, f"{P}/baselines/real_content_predictions.jsonl"),
        "nli": _git(repo, CODEX_NLI, "experiments/gate_w0_real/unit_checker/results/judgments.jsonl"),
    }
    jl = lambda t: [json.loads(l) for l in t.splitlines() if l.strip()]
    real = {
        "sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()},
        "sources": json.loads(files["sources"]),
        "hops": [h for h in jl(files["hops"]) if h["variant"] == "plain"],
        "annotations": [a for a in jl(files["annotations"]) if a["variant"] == "plain"],
        "bge": [r for r in jl(files["content"]) if r["variant"] == "plain" and r["method"] == "bge"],
    }
    cache.parent.mkdir(parents=True, exist_ok=True)
    (cache.parent / "nli_judgments.jsonl").write_text(files["nli"])
    cache.write_text(json.dumps(real))
    return real


@dataclass
class Event:
    t: float
    kind: str                     # "request" | "untracked" | "observation" | "revoke"
    principal: str = ""
    units: tuple = ()
    request_id: str = ""
    purpose: str = "study"
    role: str = ""                # descriptive label, never read by policies
    artifact: Artifact | None = None
    observation: object = None
    sender: str = ""


@dataclass
class World:
    seed: int
    propagation: str
    access_before: AccessRegistry
    access_after: AccessRegistry
    revoke_at: float
    targets: TargetRegistry
    witness_sizes: dict
    receipts: dict
    events: list
    meta: dict = field(default_factory=dict)

    def access(self, t: float) -> AccessRegistry:
        return self.access_before if t < self.revoke_at else self.access_after


def build(real: dict, nli_path: Path, seed: int, propagation: str) -> World:
    rng = random.Random(f"nowm/{seed}/{propagation}")
    facts = {s["source_id"]: [(s["source_id"], u["fact_id"]) for u in s["units"]] for s in real["sources"]}
    sources = sorted(facts)
    all_facts = [u for s in sources for u in facts[s]]

    # Issuance: each source to one student (2 sources per student).
    order = sources[:]
    rng.shuffle(order)
    owner = {s: STUDENTS[i % len(STUDENTS)] for i, s in enumerate(order)}
    receipts = {p: set() for p in PRINCIPALS}
    for s in sources:
        receipts[owner[s]].update(facts[s])

    # Teacher secrets: witnesses over facts of distinct sources, never fully held by one principal.
    targets, wsize, used = [], {}, set()
    for j, w in enumerate(TEACHER_W):
        for _ in range(1000):
            srcs = rng.sample(sources, w)
            wit = frozenset(rng.choice(facts[s]) for s in srcs)
            if len({owner[s] for s in srcs}) >= 2 and not (wit & used):
                break
        used |= wit
        targets.append(ProtectedTarget(f"teach:{j}", TEACHER, ORG, (wit,), kind="teaching_asset"))
        wsize[f"teach:{j}"] = w
    # Student-profile secrets: synthetic signal units held by nobody at start.
    for s, w in PROFILE_W.items():
        wit = frozenset((f"profile:{s}", f"sig{i}") for i in range(w))
        targets.append(ProtectedTarget(f"profile:{s}", s, ORG, (wit,), kind="student_attribute"))
        wsize[f"profile:{s}"] = w

    resources = sources + [f"profile:{s}" for s in STUDENTS]
    owners = [AssetOwnership(s, TEACHER, ORG) for s in sources] + \
             [AssetOwnership(f"profile:{s}", s, ORG) for s in STUDENTS]
    members = [Membership(p, ORG, "student") for p in STUDENTS] + [
        Membership(TA, ORG, "agent"), Membership(COUNSELOR, ORG, "agent"), Membership(TEACHER, ORG, "teacher")]
    grants = [AccessGrant(p, s, "study", 1) for p in STUDENTS + (TA,) for s in sources] + \
             [AccessGrant(a, f"profile:{s}", "support", 1) for a in (TA, COUNSELOR) for s in STUDENTS]
    access_before = AccessRegistry(owners, members, grants)
    revoked = set(rng.sample(sources, 4))           # TA loses these sources mid-stream
    grants_after = [g for g in grants if not (g.grantee_principal_id == TA and g.resource_id in revoked)]
    access_after = AccessRegistry(owners, members, grants_after)
    revoke_at = N_REQUESTS / 2

    events: list[Event] = []
    # Real propagation: each chain starts at its issued student, endpoint holders follow a seeded path.
    ann = {a["case_id"]: a for a in real["annotations"]}
    bge = {r["case_id"]: r for r in real["bge"]}
    nli = NliReplayChecker(nli_path, "test")
    chains = sorted({h["chain_id"] for h in real["hops"]})
    depths = PROPAGATION[propagation]
    for chain in chains:
        steps = {h["depth"]: h for h in real["hops"] if h["chain_id"] == chain}
        src0 = steps[1]["input_source_ids"][0]
        prev = owner[src0]
        path = rng.sample([p for p in STUDENTS + (TA,) if p != prev], 3)
        start = rng.uniform(1, N_REQUESTS * 0.8)
        for i, d in enumerate((1, 3, 5)):
            if d not in depths:
                break
            h = steps[d]
            holder, t = path[i], start + 10 * i
            a = ann[h["case_id"]]
            retained = tuple(sorted((f.rsplit(":", 1)[0], f) for f in a["retained_fact_ids"]))
            art = Artifact(f"{h['case_id']}:plain", holder, h["text"], t)
            events.append(Event(t, "untracked", holder, retained, sender=prev, role=f"real:{h['transform']}"))
            obs = to_observation(bge[h["case_id"]], artifact_id=art.artifact_id, holder=holder, observed_at=t,
                                 facts_of_source={s: [u[1] for u in facts[s]] for s in sources},
                                 codex_ref=CODEX_PILOT)
            if obs is not None:
                events.append(Event(t + 0.01, "observation", holder, artifact=art, observation=obs))
            prev = holder
    # Synthetic untracked profile leaks (no text, no evidence): counselor/TA tell a peer some signals.
    if propagation == "high":
        by_id = {t.target_id: t for t in targets}
        for _ in range(6):
            s = rng.choice(STUDENTS)
            wit = sorted(next(iter(by_id[f"profile:{s}"].witness_sets)))
            peer = rng.choice([p for p in STUDENTS if p != s])
            events.append(Event(rng.uniform(1, N_REQUESTS), "untracked", peer,
                                tuple(rng.sample(wit, rng.randint(1, 2))), sender=COUNSELOR,
                                role="synthetic:profile-leak"))
    # Request stream.
    for i in range(N_REQUESTS):
        t = i + 0.5
        r = rng.random()
        if r < 0.55:
            p, u, purpose, role = rng.choice(STUDENTS), rng.choice(all_facts), "study", "learning"
        elif r < 0.70:
            p, u, purpose, role = TA, rng.choice(all_facts), "study", "ta-learning"
        elif r < 0.90:
            s = rng.choice(STUDENTS)
            p = rng.choice((TA, COUNSELOR, COUNSELOR, rng.choice([x for x in STUDENTS if x != s])))
            u = (f"profile:{s}", f"sig{rng.randrange(PROFILE_W[s])}")
            purpose, role = "support", "profile"
        else:
            p, u, purpose, role = EXT, rng.choice(all_facts), "study", "external"
        events.append(Event(t, "request", p, (u,), request_id=f"q{i}", purpose=purpose, role=role))
    events.sort(key=lambda e: (e.t, {"untracked": 0, "observation": 1, "request": 2}[e.kind]))
    return World(seed, propagation, access_before, access_after, revoke_at, TargetRegistry(targets), wsize,
                 {p: frozenset(u) for p, u in receipts.items()}, events,
                 meta={"revoked_for_TA": sorted(revoked), "issuance": owner, "nli_versions": sorted(nli.method_versions)})


def verifier_for(nli_path: Path) -> RuleVerifier:
    return RuleVerifier(b"", b"", NliReplayChecker(nli_path, "test"))
