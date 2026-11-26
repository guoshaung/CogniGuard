"""P0 model: latent combination leakage under incompletely governed channels (frozen threat model, PREREG.md).

World w* is fixed per instance and known to the governor (the data owner). Units are deterministic observations
f_u(w); holding unit u means knowing f_u(w*). Crossing (formal definition v0.1, default threshold):
    cross(A) := max_{B subset of A} V1(S | B at w*) > 1/2        (realized, value-dependent, monotone closure)
which by Lemma 1 holds iff A contains a value-dependent derivation set at w*.

Agents: A (attacker endpoint), relays B and C. Channels:
  controlled  : releases of non-external units, gated per recipient by the unchanged CA-PD kernel (k = 1) on the
                governor's own release log (it cannot see external holdings or relay forwarding);
  external    : A acquires units of E (tool / web retrieval) with prob p_ext per step, cost c_u, budget B_TOT;
                strategy greedy (maximize expected next-step posterior V1) or random, hidden type;
  relay       : along topology edges, with prob p_rel per step and edge, a sender forwards one uniformly random
                unit it holds that the receiver lacks (shared memory / message forwarding between agents).
"""

from __future__ import annotations

import itertools
import math
import random
from functools import lru_cache

import numpy as np

from experiments.cogniguard_ksl import structures as KS
from experiments.cogniguard_ksl.engine import build, capd_distance, capd_safe, registry as _reg_vi  # noqa: F401
from cogniguard.governance.reconstruction import check_release, residual_distance
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

THETA = 0.5
B_TOT = 3
T0 = 1            # hidden burn-in external steps before the decision point
H = 3             # prediction horizon (main)
P_E = 0.35        # probability that a unit is externally obtainable
N_REQ = 4         # controlled requests before the decision point
STRUCTS = ["and_xor", "and_max", "or_alt", "relation", "mixed"]
TOPOS = ["star", "line"]
PROPS = {"det": (1.0, 1.0), "rand": (0.5, 0.5)}
COSTS = ["unit", "varied"]


def popcount(x):
    return bin(x).count("1")


def bits(x):
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b


class Struct:
    """Exact tables for one KSL structure."""

    _cache = {}

    def __new__(cls, name):
        if name in cls._cache:
            return cls._cache[name]
        self = super().__new__(cls)
        st = {s.name: s for s in KS.all_structures()}[name]
        self.name, self.st = name, st
        self.T = build(st)
        self.units = self.T.units
        self.m = len(self.units)
        self.nw = len(st.worlds)
        self.prior = self.T.prior
        self.sidx = self.T.sidx
        self.ns = len(self.T.svals)
        obs = np.zeros((self.nw, self.m), dtype=np.int64)
        for j, u in enumerate(self.units):
            vals = {}
            for i, w in enumerate(st.worlds):
                obs[i, j] = vals.setdefault(st.units[u](w), len(vals))
        self.obs = obs
        M = 1 << self.m
        Vc = self.T.V1.copy()                       # monotone closure over sub-views, per world
        for mask in range(M):
            for j in bits(mask):
                Vc[mask] = np.maximum(Vc[mask], Vc[mask ^ (1 << j)])
        self.Vc = Vc
        self.cross = Vc > THETA
        self.allmask = M - 1
        cls._cache[name] = self
        return self

    def derivations(self, w):
        cr = self.cross[:, w]
        return [k for k in range(1 << self.m) if cr[k] and not any(cr[k ^ (1 << j)] for j in bits(k))]

    # attacker-side cells -------------------------------------------------------------
    def cell(self, A, w):
        cols = list(bits(A))
        if not cols:
            return tuple(range(self.nw))
        row = self.obs[w, cols]
        return tuple(np.nonzero((self.obs[:, cols] == row).all(1))[0].tolist())

    @lru_cache(maxsize=None)
    def split(self, cell, u):
        groups = {}
        for i in cell:
            groups.setdefault(int(self.obs[i, u]), []).append(i)
        tot = sum(self.prior[i] for i in cell)
        return tuple((sum(self.prior[i] for i in g) / tot, tuple(g)) for g in groups.values())

    @lru_cache(maxsize=None)
    def post(self, cell):
        p = np.zeros(self.ns)
        for i in cell:
            p[self.sidx[i]] += self.prior[i]
        return p / p.sum()

    @lru_cache(maxsize=None)
    def Hc(self, cell):
        p = self.post(cell)
        p = p[p > 0]
        return float(-(p * np.log2(p)).sum())

    @lru_cache(maxsize=None)
    def V1c(self, cell):
        return float(self.post(cell).max())

    def exp_V1_after(self, cell, u):
        return sum(p * self.V1c(c) for p, c in self.split(cell, u))


def value_dependent_registry(S: Struct, w):
    """Audit56-corrected adapter: witnesses are the derivation sets at the true world (formal definition)."""
    ws = S.derivations(w)
    tgt = ProtectedTarget(target_id=S.name, owner_principal_id="owner", org_id="org",
                          witness_sets=tuple(frozenset(("asset", S.units[j]) for j in bits(m)) for m in ws))
    return TargetRegistry([tgt])


def _refs(S, mask):
    return frozenset(("asset", S.units[j]) for j in bits(mask))


# ----------------------------------------------------------------------------- instances

def gen_instance(seed, struct, topo, prop, cost):
    rng = random.Random(seed)
    S = Struct(struct)
    w = rng.randrange(S.nw)
    E = sum(1 << j for j in range(S.m) if rng.random() < P_E)
    c = [1 if cost == "unit" else rng.choice((1, 2)) for _ in range(S.m)]
    reg = value_dependent_registry(S, w)
    rel = {"A": 0, "B": 0, "C": 0}
    ctrl = S.allmask & ~E
    log = []
    for _ in range(N_REQ):
        r = rng.choice("ABC")
        cand = [j for j in bits(ctrl & ~rel[r])]
        if not cand:
            continue
        j = rng.choice(cand)
        know = {a: _refs(S, m) for a, m in rel.items()}
        ok = check_release(reg, r, _refs(S, 1 << j), know, 1).safe          # unchanged kernel, k = 1
        log.append((r, j, bool(ok)))
        if ok:
            rel[r] |= 1 << j
    atype = rng.choice(("greedy", "random"))
    p_ext, p_rel = PROPS[prop]
    inst = {"seed": seed, "struct": struct, "topo": topo, "prop": prop, "cost": cost, "w": w, "E": E, "c": c,
            "RA": rel["A"], "RB": rel["B"], "RC": rel["C"], "p_ext": p_ext, "p_rel": p_rel, "log": log,
            "atype": atype}
    # hidden burn-in (not observed by the governor): T0 external steps from empty knowledge
    A, bud = 0, B_TOT
    for _ in range(T0):
        A, bud = ext_step_sample(S, inst, A, bud, atype, rng)
    inst["hidden"], inst["bud0"] = A, bud
    inst["label_rng"] = rng.getrandbits(32)
    return inst


def affordable(S, inst, A, bud):
    return [j for j in bits(inst["E"] & ~A) if inst["c"][j] <= bud]


def greedy_pick(S, inst, A, opts):
    cell = S.cell(A, inst["w"])
    return max(opts, key=lambda j: (S.exp_V1_after(cell, j), -inst["c"][j], -j))


def ext_step_sample(S, inst, A, bud, atype, rng):
    if rng.random() < inst["p_ext"]:
        opts = affordable(S, inst, A, bud)
        if opts:
            j = greedy_pick(S, inst, A, opts) if atype == "greedy" else rng.choice(opts)
            return A | 1 << j, bud - inst["c"][j]
    return A, bud


def edges(topo):
    return [("B", "A"), ("C", "A")] if topo == "star" else [("C", "B"), ("B", "A")]


def relay_dist(inst, st):
    """Distribution over relay outcomes. st = dict holdings; returns list of (p, new dict)."""
    out = [(1.0, dict(st))]
    for a, b in edges(inst["topo"]):
        nxt = []
        for p, s in out:
            cand = list(bits(s[a] & ~s[b]))
            if not cand or inst["p_rel"] <= 0:
                nxt.append((p, s))
                continue
            if inst["p_rel"] < 1:
                nxt.append((p * (1 - inst["p_rel"]), s))
            for j in cand:
                s2 = dict(s)
                s2[b] |= 1 << j
                nxt.append((p * inst["p_rel"] / len(cand), s2))
        out = nxt
    return out


def ext_dist(S, inst, A, bud, atype):
    """Distribution over external outcomes for a strategy type (frozen attacker model)."""
    out = []
    opts = affordable(S, inst, A, bud)
    pe = inst["p_ext"]
    if not opts or pe <= 0:
        return [(1.0, A, bud)]
    if pe < 1:
        out.append((1 - pe, A, bud))
    if atype == "greedy":
        j = greedy_pick(S, inst, A, opts)
        out.append((pe, A | 1 << j, bud - inst["c"][j]))
    else:
        for j in opts:
            out.append((pe / len(opts), A | 1 << j, bud - inst["c"][j]))
    return out


def p_cross(S, inst, A, B, C, bud, atype, h):
    """Exact probability that A's knowledge crosses at some time in [0, h] (absorbing)."""
    w = inst["w"]
    memo = {}

    def rec(A, B, C, bud, s):
        if S.cross[A, w]:
            return 1.0
        if s == 0:
            return 0.0
        key = (A, B, C, bud, s)
        if key in memo:
            return memo[key]
        v = 0.0
        for pe, A2, b2 in ext_dist(S, inst, A, bud, atype):
            if S.cross[A2, w]:
                v += pe
                continue
            for pr, st in relay_dist(inst, {"A": A2, "B": B, "C": C}):
                v += pe * pr * rec(st["A"], st["B"], st["C"], b2, s - 1)
        memo[key] = v
        return v

    return rec(A, B, C, bud, h)


def sample_cross(S, inst, h):
    """One realization of the future from the true hidden state (label)."""
    rng = random.Random(inst["label_rng"])
    w = inst["w"]
    A, B, C, bud = inst["RA"] | inst["hidden"], inst["RB"], inst["RC"], inst["bud0"]
    if S.cross[A, w]:
        return True, 0
    for t in range(1, h + 1):
        A, bud = ext_step_sample(S, inst, A, bud, inst["atype"], rng)
        if not S.cross[A, w]:
            st = {"A": A, "B": B, "C": C}
            for a, b in edges(inst["topo"]):
                cand = list(bits(st[a] & ~st[b]))
                if cand and rng.random() < inst["p_rel"]:
                    st[b] |= 1 << rng.choice(cand)
            A, B, C = st["A"], st["B"], st["C"]
        if S.cross[A, w]:
            return True, t
    return False, None


def belief(S, inst):
    """Governor's exact belief over (attacker type, hidden external holdings, remaining budget)."""
    out = {}
    for atype in ("greedy", "random"):
        dist = [(0.5, 0, B_TOT)]
        for _ in range(T0):
            nd = []
            for p, A, b in dist:
                for q, A2, b2 in ext_dist(S, inst, A, b, atype):
                    nd.append((p * q, A2, b2))
            dist = nd
        for p, A, b in dist:
            out[(atype, A, b)] = out.get((atype, A, b), 0.0) + p
    return out


# ----------------------------------------------------------------------------- attacker-side adaptive leakage

def adaptive(S, inst, A, cell, B, C, bud, h, measure):
    """sup over attacker strategies (choice of external unit each step; nature = p_ext, relays) of the expected
    terminal objective. measure 'H': minimize E[H(S|final cell)]; 'V': maximize E[V1(S|final cell)].
    Returns the optimal expected terminal value."""
    memo = {}
    better = min if measure == "H" else max
    term = S.Hc if measure == "H" else S.V1c

    def relay_then(A, cell, B, C, bud, s):
        v = 0.0
        for pr, st in relay_dist(inst, {"A": A, "B": B, "C": C}):
            new = st["A"] & ~A
            cells = [(1.0, cell)]
            for j in bits(new):
                cells = [(p * q, c2) for p, c in cells for q, c2 in S.split(c, j)]
            for p, c in cells:
                v += pr * p * rec(st["A"], c, st["B"], st["C"], bud, s - 1)
        return v

    def rec(A, cell, B, C, bud, s):
        if s == 0:
            return term(cell)
        key = (A, cell, B, C, bud, s)
        if key in memo:
            return memo[key]
        opts = [j for j in bits(inst["E"] & ~A) if inst["c"][j] <= bud]
        pe = inst["p_ext"]
        base = relay_then(A, cell, B, C, bud, s)
        if not opts or pe <= 0:
            v = base
        else:
            vals = []
            for j in opts:
                got = sum(q * relay_then(A | 1 << j, c2, B, C, bud - inst["c"][j], s) for q, c2 in S.split(cell, j))
                vals.append(pe * got + (1 - pe) * base)
            v = better(vals)
        memo[key] = v
        return v

    return rec(A, cell, B, C, bud, h)


def H2_state(S, inst, A, bud, h=H):
    cell = S.cell(A, inst["w"])
    return S.Hc(cell) - adaptive(S, inst, A, cell, inst["RB"], inst["RC"], bud, h, "H")


def KBmin_state(S, inst, A, bud, h=H):
    cell = S.cell(A, inst["w"])
    return math.log2(adaptive(S, inst, A, cell, inst["RB"], inst["RC"], bud, h, "V") / S.V1c(cell))


# ----------------------------------------------------------------------------- predictors

def coalition_size(S, inst, ders):
    src = [inst["RA"], inst["RB"], inst["RC"], inst["E"]]
    best = 9
    for r in range(1, 5):
        for comb in itertools.combinations(range(4), r):
            u = 0
            for i in comb:
                u |= src[i]
            if any(d & ~u == 0 for d in ders):
                best = min(best, r)
        if best < 9:
            break
    return best


def features(inst, h=H):
    S = Struct(inst["struct"])
    w, RA = inst["w"], inst["RA"]
    ders = S.derivations(w)
    reach = RA | inst["RB"] | inst["RC"] | inst["E"]
    cellA = S.cell(RA, w)
    d_capd = min((popcount(d & ~RA) for d in ders), default=99)
    racc = [popcount(d & ~RA) for d in ders if d & ~reach == 0]
    f = {"V1_obs": float(S.Vc[RA, w]), "H1_obs": S.Hc(cellA), "d_capd": min(d_capd, h + 3),
         "d_acc": min(min(racc, default=99), h + 3), "coalition": coalition_size(S, inst, ders),
         "n_wit_h": sum(1 for r in racc if r <= h), "wsum": sum(2.0 ** -r for r in racc)}
    bel = belief(S, inst)
    bv = bc = h2 = kb = rstar = rcross = 0.0
    for (atype, Ah, bud), p in bel.items():
        A = RA | Ah
        bv += p * float(S.Vc[A, w])
        bc += p * float(S.cross[A, w])
        h2 += p * H2_state(S, inst, A, bud, h)
        kb += p * KBmin_state(S, inst, A, bud, h)
        pt = p_cross(S, inst, A, inst["RB"], inst["RC"], bud, atype, h)
        pref = p_cross(S, inst, Ah, 0, 0, bud, atype, h)
        rcross += p * pt
        rstar += p * pt * (pref == 0.0)
    f.update({"belief_V1": bv, "belief_cross_now": bc, "KB_min": kb, "H2": h2})
    # H2 on the observed controlled view only (no hidden holdings, full budget)
    f["H2_obs"] = H2_state(S, inst, RA, B_TOT, h)
    f["R_cross"] = rcross        # exact model-based P(cross within h)  (deployable: frozen model + belief)
    f["R_star"] = rstar          # exact model-based P(avoidable cross)  = Bayes predictor of the label
    # label
    crossed, t = sample_cross(S, inst, h)
    pref_true = p_cross(S, inst, inst["hidden"], 0, 0, inst["bud0"], inst["atype"], h)
    f["y_cross"] = int(crossed)
    f["ext_capable"] = int(pref_true > 0)
    f["y"] = int(crossed and pref_true == 0.0)
    f["t_cross"] = t
    return f
