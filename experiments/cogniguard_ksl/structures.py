"""Small structured assets whose secret candidate space can be enumerated exactly.

Every structure is a finite set of latent worlds Omega (uniform synthetic prior unless stated), a secret
S = sigma(world), and knowledge units. A unit is a deterministic observation of the world: an attacker who
holds unit u learns f_u(world*). Decoy units observe nuisance variables that are independent of S, so
requests for them are benign under every target.

The candidate spaces and priors are SYNTHETIC. They are a test bed for the decision rules, not a model of a
real attacker's prior (see THEORY_V2.md section 1.4).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Structure:
    name: str
    kind: str                         # fact / relation / serial / parallel / and_* / or / mixed
    worlds: list                      # latent worlds (tuples)
    secret: Callable                  # world -> hashable secret value
    units: dict                       # unit name -> world -> observation value
    decoys: tuple                     # unit names that observe nuisance only
    gain: Callable                    # (guess secret, true secret) -> [0, 1] partial-credit gain
    describe: dict = field(default_factory=dict)   # natural-language rendering hints (LLM pilot)

    @property
    def unit_names(self):
        return list(self.units)


NUIS = list(itertools.product(range(2), range(2)))      # two nuisance bits shared by all structures


def _decoys():
    return {"d_room": lambda w: w[-1][0], "d_shift": lambda w: w[-1][1]}


def _frac(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def fact():
    # S = salary band 0..7 (3 bits); units reveal individual bits / coarse ranges.
    worlds = [(b, n) for b in range(8) for n in NUIS]
    u = {"band_ge4": lambda w: int(w[0] >= 4), "band_mod4_ge2": lambda w: int(w[0] % 4 >= 2),
         "band_odd": lambda w: w[0] % 2, "band_ge6": lambda w: int(w[0] >= 6), **_decoys()}
    return Structure("fact", "fact", worlds, lambda w: w[0], u, ("d_room", "d_shift"),
                     lambda g, s: 1.0 if g == s else (0.5 if abs(g - s) == 1 else 0.0))


def relation():
    # S = private advisor matching of 4 students to 4 advisors (a bijection).
    worlds = [(p, n) for p in itertools.permutations(range(4)) for n in NUIS]
    u = {f"adv_of_s{i}": (lambda i: lambda w: w[0][i])(i) for i in range(4)}
    u["s0_adv_in_A"] = lambda w: int(w[0][0] in (0, 1))
    u.update(_decoys())
    return Structure("relation", "relation", worlds, lambda w: w[0], u, ("d_room", "d_shift"), _frac)


def serial():
    # S = order of 5 procedure steps; units reveal "the step after step i" (or END).
    worlds = [(p, n) for p in itertools.permutations(range(5)) for n in NUIS]

    def succ(i):
        def f(w):
            p = w[0]
            j = p.index(i)
            return p[j + 1] if j + 1 < len(p) else -1
        return f
    u = {f"succ_{i}": succ(i) for i in range(5)}
    u["first_step"] = lambda w: w[0][0]
    u.update(_decoys())
    return Structure("serial", "serial", worlds, lambda w: w[0], u, ("d_room", "d_shift"), _frac)


def parallel():
    # S = three independent branches, each 0..3; witness needs all three.
    worlds = [((a, b, c), n) for a in range(4) for b in range(4) for c in range(4) for n in NUIS]
    u = {"branch_1": lambda w: w[0][0], "branch_2": lambda w: w[0][1], "branch_3": lambda w: w[0][2],
         "branch_1_parity": lambda w: w[0][0] % 2, **_decoys()}
    return Structure("parallel", "parallel", worlds, lambda w: w[0], u, ("d_room", "d_shift"), _frac)


def and_join(op):
    # S = op(a, b): both inputs are needed in general (AND convergence). xor = perfect sharing,
    # sum = partial leak, max = value-dependent early determination.
    f = {"xor": lambda a, b: a ^ b, "sum": lambda a, b: a + b, "max": max}[op]
    worlds = [((a, b), n) for a in range(4) for b in range(4) for n in NUIS]
    u = {"in_a": lambda w: w[0][0], "in_b": lambda w: w[0][1], "in_a_hi": lambda w: int(w[0][0] >= 2), **_decoys()}
    g = (lambda x, y: float(x == y)) if op == "xor" else (lambda x, y: 1.0 if x == y else (0.5 if abs(x - y) == 1 else 0.0))
    return Structure(f"and_{op}", f"and_{op}", worlds, lambda w: f(*w[0]), u, ("d_room", "d_shift"), g)


def or_alt():
    # S in 0..7 reachable by either route {s_hi, s_lo} or {cipher, key}, cipher = S xor key.
    worlds = [((s, r), n) for s in range(8) for r in range(8) for n in NUIS]
    u = {"s_hi": lambda w: w[0][0] >> 1, "s_lo": lambda w: w[0][0] & 1,
         "cipher": lambda w: w[0][0] ^ w[0][1], "key": lambda w: w[0][1], **_decoys()}
    bits = lambda x: (x >> 2 & 1, x >> 1 & 1, x & 1)
    return Structure("or_alt", "or", worlds, lambda w: w[0][0], u, ("d_room", "d_shift"),
                     lambda g, s: _frac(bits(g), bits(s)))


def mixed():
    # S = (order of 3 steps, who executes step 0 in {0,1,2}): serial + relation + fact.
    worlds = [((p, e), n) for p in itertools.permutations(range(3)) for e in range(3) for n in NUIS]
    u = {"first": lambda w: w[0][0][0], "last": lambda w: w[0][0][2], "exec0": lambda w: w[0][1],
         "exec0_not_me": lambda w: int(w[0][1] != 0), "step0_before_1": lambda w: int(w[0][0].index(0) < w[0][0].index(1)),
         **_decoys()}
    return Structure("mixed", "mixed", worlds, lambda w: w[0], u, ("d_room", "d_shift"),
                     lambda g, s: 0.5 * _frac(g[0], s[0]) + 0.5 * float(g[1] == s[1]))


def all_structures():
    return [fact(), relation(), serial(), parallel(), and_join("xor"), and_join("sum"), and_join("max"), or_alt(), mixed()]
