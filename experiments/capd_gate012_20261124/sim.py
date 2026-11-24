"""Gate 0-2 simulator: unrecorded propagation, evidence channels and the arms B0-B4, Ours, Oracle.

Reuses the frozen E5 data loader and request stream; the coalition check is the
production `check_release`. Nothing here changes `cogniguard/` or earlier experiments.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from cogniguard.governance.reconstruction import _minimum_helpers, check_release
from cogniguard.governance.targets import TargetRegistry
from experiments.capd_e5_20261123.workload import generate as generate_stream

K_DEFENSE = 2  # must be < max witness size, see theory section 8
HOLDER_CAP = 8
INF = 10**9


@dataclass(frozen=True)
class Noise:
    r: float = 1.0        # possession-evidence recall per true event
    q: float = 0.0        # misattribution: evidence names a random other agent
    p_dup: float = 0.0    # the same evidence item is emitted again later
    phi: float = 0.0      # per-request rate of forged possession evidence
    p_mix: float = 0.0    # evidence also carries another agent's holdings
    delay: int = 0        # requests until evidence arrives
    r_c: float = 1.0      # event-certificate recall
    phi_c: float = 0.0    # per-request rate of forged event certificates
    dup_c: float = 0.0    # certificate re-sent with the same id

    def name(self) -> str:
        return (f"r{self.r}_q{self.q}_dup{self.p_dup}_phi{self.phi}_mix{self.p_mix}"
                f"_d{self.delay}_rc{self.r_c}_phic{self.phi_c}_dupc{self.dup_c}")


@dataclass
class World:
    secrets: tuple
    registry: TargetRegistry
    stream: object
    agents: tuple[str, ...]
    adj: dict[str, set]
    dist: dict[str, dict[str, int]]
    comp: dict[str, int]
    events: dict[int, list[tuple[str, str]]]  # request index -> [(sender, receiver)]
    f: int
    tau: dict = field(default_factory=dict)


def build_graph(agents, kind: str, rng: random.Random) -> dict[str, set]:
    adj = {a: set() for a in agents}
    if kind == "complete":
        for a in agents:
            adj[a] = set(agents) - {a}
        return adj
    for a in agents:  # sparse: each agent links to 3 random others (undirected)
        for b in rng.sample([x for x in agents if x != a], 3):
            adj[a].add(b)
            adj[b].add(a)
    return adj


def all_pairs(adj):
    dist = {}
    for s in adj:
        d = {s: 0}
        frontier = [s]
        for x in frontier:
            for y in adj[x]:
                if y not in d:
                    d[y] = d[x] + 1
                    frontier.append(y)
        dist[s] = d
    return dist


def components(adj):
    comp, label = {}, 0
    for s in adj:
        if s in comp:
            continue
        stack = [s]
        comp[s] = label
        while stack:
            x = stack.pop()
            for y in adj[x]:
                if y not in comp:
                    comp[y] = label
                    stack.append(y)
        label += 1
    return comp


def make_world(secrets, *, seed: int, graph: str, f: int, f_true: int, mode: str = "coalition",
               student_count=60, coalition_sizes=(2, 2, 3, 3, 4, 4), normal_requests=4) -> World:
    """mode="benign": unrecorded transfers along random channel edges.
    mode="coalition": transfers between members of planted groups. Group members share
    a workspace, so they are linked in G; the defender knows G, not who colludes."""
    stream = generate_stream(secrets, student_count=student_count, coalition_sizes=coalition_sizes,
                             seed=seed, normal_requests=normal_requests, complete_ratio=0.0)
    agents = tuple(f"student-{i:02d}" for i in range(student_count))
    rng = random.Random(f"gate012/{seed}/{graph}")
    adj = build_graph(agents, graph, rng)
    for group in stream.groups:
        for a in group.members:
            adj[a] |= set(group.members) - {a}
    erng = random.Random(f"gate012-events/{seed}/{graph}/{f_true}/{mode}")
    if mode == "coalition":
        edges = sorted({tuple(sorted((a, b))) for g in stream.groups
                        for a in g.members for b in g.members if a < b})
    else:
        edges = sorted({tuple(sorted((a, b))) for a in adj for b in adj[a]})
    n = len(stream.requests)
    events: dict[int, list] = {}
    for _ in range(f_true):
        t = erng.randrange(n)
        a, b = edges[erng.randrange(len(edges))]
        if erng.random() < 0.5:
            a, b = b, a
        events.setdefault(t, []).append((a, b))
    registry = TargetRegistry(s.target() for s in secrets)
    return World(secrets, registry, stream, agents, adj, all_pairs(adj), components(adj),
                 events, f, {s.target_id: s.tau for s in secrets})


# ---------------------------------------------------------------- graph-aware check

def _steiner_costs(terminals, adj, dist, budget):
    """Dreyfus-Wagner over nodes within distance `budget` of some terminal.
    Returns {subset_mask: min tree edges} for every non-empty subset of terminals."""
    nodes = sorted({v for t in terminals for v, d in dist[t].items() if d <= budget})
    index = {v: i for i, v in enumerate(nodes)}
    m, t = len(nodes), len(terminals)
    dmat = [[dist[u].get(v, INF) for v in nodes] for u in nodes]
    dp = [[INF] * m for _ in range(1 << t)]
    for i, term in enumerate(terminals):
        row = dmat[index[term]]
        dp[1 << i] = row[:]
    for S in range(1, 1 << t):
        if S & (S - 1) == 0:
            continue
        cur = dp[S]
        sub = (S - 1) & S
        while sub:
            if sub < (S ^ sub):  # each split once
                a, b = dp[sub], dp[S ^ sub]
                for v in range(m):
                    c = a[v] + b[v]
                    if c < cur[v]:
                        cur[v] = c
            sub = (sub - 1) & S
        best = cur[:]
        for v in range(m):
            cv = cur[v]
            if cv >= INF:
                continue
            row = dmat[v]
            for u in range(m):
                c = cv + row[u]
                if c < best[u]:
                    best[u] = c
        dp[S] = best
    return {S: min(dp[S]) if m else INF for S in range(1, 1 << t)}


def graph_check(world: World, knowledge: dict, recipient: str, unit, k: int, budget: int):
    """Exact Prop.3 check restricted to covers that use the recipient. Returns
    (safe: bool, fell_back: bool). Called only when the any-to-any bound flags."""
    held = {a: set(u) for a, u in knowledge.items()}
    held.setdefault(recipient, set()).add(unit)
    for target in world.registry.targets_for_unit(unit):
        for witness in target.witness_sets:
            holders = [a for a in world.agents if held.get(a) and held[a] & witness]
            if recipient not in holders:
                continue
            if len(holders) > HOLDER_CAP:
                return False, True
            holders.remove(recipient)
            holders = [recipient] + holders
            h = len(holders)
            cover = [frozenset()] * (1 << h)
            for S in range(1, 1 << h):
                low = (S & -S).bit_length() - 1
                cover[S] = cover[S ^ (1 << low)] | (held[holders[low]] & witness)
            cost = _steiner_costs(holders, world.adj, world.dist, budget)
            best = [[INF] * (k + 1) for _ in range(1 << h)]
            best[0][0] = 0
            for S in range(1, 1 << h):
                low = S & -S
                sub = S
                while sub:
                    if sub & low and cost[sub] <= budget:
                        rest = best[S ^ sub]
                        for j in range(1, k + 1):
                            c = rest[j - 1] + cost[sub]
                            if c < best[S][j]:
                                best[S][j] = c
                    sub = (sub - 1) & S
            for S in range(1, 1 << h):
                if S & 1 and cover[S] >= witness and min(best[S][1:]) <= budget:
                    return False, False
    return True, False


# ---------------------------------------------------------------- arms

ARMS = ("B0", "B1", "B2", "B2b", "B3", "B4", "Ours", "Oracle")
# B2: every possession-evidence item (what a watermark/fingerprint detection yields) is
#     treated as an event proof and consumes budget; it never sees certificates.
# B2b and Ours: possession evidence only joins the ledger; only verified, de-duplicated
#     event certificates consume budget (identical evidence rule; Ours adds the graph).


def _effective(belief, pinned):
    eff = {a: set(u) for a, u in belief.items()}
    changed = True
    while changed and pinned:
        changed = False
        for u, v in pinned:
            add = eff.get(u, set()) - eff.setdefault(v, set())
            if add:
                eff[v] |= add
                changed = True
    return eff


def _frozen(d):
    return {a: frozenset(u) for a, u in d.items() if u}


def run_arm(world: World, arm: str, noise: Noise, seed: int) -> dict:
    rng = random.Random(f"gate012-evidence/{seed}/{noise.name()}")
    truth = {a: set() for a in world.agents}      # H: actual holdings
    belief = {a: set() for a in world.agents}     # O: receipts + accepted evidence
    pinned: list[tuple[str, str]] = []            # certified events (Ours, B2b)
    seen_ids: set = set()
    d_all = d_c = true_events = 0
    queue: list[tuple[int, str, tuple]] = []
    k = K_DEFENSE
    m = {"harmful": 0, "prop_induced": 0, "normal_total": 0, "normal_full": 0,
         "normal_util": 0.0, "normal_best": 0.0, "unneeded_refusals": 0,
         "underestimates": 0, "fallbacks": 0, "decision_s": 0.0, "decisions": 0}
    event_id = 0

    def violated(witness, holdings):
        need, _ = _minimum_helpers(frozenset(witness), _frozen(holdings), "__none__")
        return need is not None and need <= k

    for t, req in enumerate(world.stream.requests):
        for sender, receiver in world.events.get(t, []):
            content = set(truth[sender])
            touched = {w for unit in content for tg in world.registry.targets_for_unit(unit)
                       for w in tg.witness_sets}
            before = {w for w in touched if violated(w, truth)}
            truth[receiver] |= content
            after = {w for w in touched if violated(w, truth)}
            m["prop_induced"] += len(after - before)
            true_events += 1
            event_id += 1
            if rng.random() < noise.r_c:
                queue.append((t + noise.delay, "cert", (event_id, sender, receiver)))
                if rng.random() < noise.dup_c:
                    queue.append((t + noise.delay + 1, "cert", (event_id, sender, receiver)))
            if rng.random() < noise.r:
                who = receiver
                if rng.random() < noise.q:
                    who = rng.choice([a for a in world.agents if a != receiver])
                units = set(content)
                if rng.random() < noise.p_mix:
                    other = rng.choice(world.agents)
                    units |= truth[other]
                queue.append((t + noise.delay, "poss", (who, frozenset(units))))
                if rng.random() < noise.p_dup:
                    queue.append((t + noise.delay + 1, "poss", (who, frozenset(units))))
        if rng.random() < noise.phi:
            who = rng.choice(world.agents)
            src = rng.choice(world.agents)
            queue.append((t, "poss", (who, frozenset(truth[src]))))
        if rng.random() < noise.phi_c:
            a = rng.choice(world.agents)
            b = rng.choice(sorted(world.adj[a]))
            queue.append((t, "cert", (f"forged-{t}", a, b)))
        due = [item for item in queue if item[0] <= t]
        queue = [item for item in queue if item[0] > t]
        for _at, kind, payload in due:
            if kind == "poss":
                who, units = payload
                if arm in ("B2", "B2b", "B3", "Ours"):
                    belief[who] |= units
                if arm == "B2":
                    d_all += 1
            else:
                eid, a, b = payload
                if arm in ("B2b", "Ours") and eid not in seen_ids:
                    seen_ids.add(eid)
                    d_c += 1
                    pinned.append((a, b))
        if arm in ("B2", "B2b", "Ours"):
            used = d_all if arm == "B2" else d_c
            m["underestimates"] += used > true_events

        recipient, unit = req.recipient_id, req.unit
        started = time.perf_counter()
        oracle_ok = check_release(world.registry, recipient, {unit}, _frozen(truth), k).safe
        if arm == "Oracle":
            ok = oracle_ok
        elif arm == "B0":
            ok = check_release(world.registry, recipient, {unit}, _frozen(belief), k).safe
        elif arm == "B1":
            ok = check_release(world.registry, recipient, {unit}, _frozen(belief), k + world.f).safe
        elif arm == "B2":
            ok = check_release(world.registry, recipient, {unit}, _frozen(belief),
                               k + max(0, world.f - d_all)).safe
        elif arm == "B3":
            ok = check_release(world.registry, recipient, {unit}, _frozen(belief), k).safe
        elif arm == "B4":
            merged: dict[str, set] = {}
            for a, units in belief.items():
                merged.setdefault(f"c{world.comp[a]}", set()).update(units)
            ok = check_release(world.registry, f"c{world.comp[recipient]}", {unit},
                               _frozen(merged), k).safe
        else:
            eff = _effective(belief, pinned)
            budget = max(0, world.f - d_c)
            ok = check_release(world.registry, recipient, {unit}, _frozen(eff), k + budget).safe
            if arm == "Ours" and not ok:
                if budget == 0:
                    ok = check_release(world.registry, recipient, {unit}, _frozen(eff), k).safe
                else:
                    ok, fell = graph_check(world, eff, recipient, unit, k, budget)
                    m["fallbacks"] += fell
        m["decision_s"] += time.perf_counter() - started
        m["decisions"] += 1
        if ok:
            truth[recipient].add(unit)
            belief[recipient].add(unit)
            if not oracle_ok:
                m["harmful"] += 1
        if req.role == "normal":
            m["normal_total"] += 1
            m["normal_full"] += ok
            m["normal_util"] += 1.0 if ok else 0.4
            m["normal_best"] += 1.0
            m["unneeded_refusals"] += (not ok) and oracle_ok

    by_id = {s.target_id: s for s in world.secrets}
    group_viol = []
    for group in world.stream.groups:
        view = set().union(*(truth[a] for a in group.members))
        secret = by_id[group.target_id]
        group_viol.append(secret.leakage_star(view) > secret.tau + 1e-9)
    nt = m["normal_total"] or 1
    return {
        "harmful_releases": m["harmful"],
        "prop_induced": m["prop_induced"],
        "VR_actual": sum(group_viol) / len(group_viol),
        "UR_normal": m["normal_util"] / (m["normal_best"] or 1),
        "DR_normal": 1 - m["normal_full"] / nt,
        "unneeded_refusal_rate": m["unneeded_refusals"] / nt,
        "underestimate_steps": m["underestimates"],
        "fallbacks": m["fallbacks"],
        "true_events": true_events,
        "mean_decision_ms": 1000 * m["decision_s"] / max(1, m["decisions"]),
    }
