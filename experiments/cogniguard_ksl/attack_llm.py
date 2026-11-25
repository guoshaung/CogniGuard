"""Pilot: does exact partial-leakage risk predict what a real LLM attacker actually guesses?

Stratified (structure, true world, attacker view) states are rendered as natural-language facts. The attacker
(glm-5.2, token plan, thinking off, temperature 0; the same backend as Protocol B) is told the candidate space
and the facts and asked for its single best guess plus two more. We score top-1 and top-3 exact hits and
compare with the exact Bayes vulnerability V1 (uniform synthetic prior), 3-try vulnerability P3, Shannon H and
the complete-witness flag. This is a capability probe on synthetic puzzles, not a model of a real attacker's
prior.

  python -m experiments.cogniguard_ksl.attack_llm --per 40            # cached; reruns only missing items
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from experiments.cogniguard_ksl import engine, structures as S

OUT = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl/attack_llm.jsonl")
L = "ABCD"
STEPS = "PQRST"


def render(name, unit, val):
    yn = lambda c, a, b: a if c else b
    if name == "fact":
        return {"band_ge4": yn(val, "E's salary band is at least 4.", "E's salary band is below 4."),
                "band_mod4_ge2": yn(val, "E's salary band leaves remainder 2 or 3 when divided by 4.",
                                    "E's salary band leaves remainder 0 or 1 when divided by 4."),
                "band_odd": yn(val, "E's salary band is odd.", "E's salary band is even."),
                "band_ge6": yn(val, "E's salary band is at least 6.", "E's salary band is below 6.")}.get(unit)
    if name == "relation":
        if unit.startswith("adv_of_s"):
            return f"Student s{unit[-1]}'s advisor is {L[val]}."
        if unit == "s0_adv_in_A":
            return yn(val, "Student s0's advisor is A or B.", "Student s0's advisor is C or D.")
    if name == "serial":
        if unit.startswith("succ_"):
            i = int(unit[-1])
            return f"Step {STEPS[i]} is the last step." if val == -1 else f"Step {STEPS[i]} is immediately followed by step {STEPS[val]}."
        if unit == "first_step":
            return f"The first step is {STEPS[val]}."
    if name == "parallel":
        if unit.startswith("branch_") and not unit.endswith("parity"):
            return f"Branch {unit[-1]}'s setting is {val}."
        if unit == "branch_1_parity":
            return yn(val, "Branch 1's setting is odd.", "Branch 1's setting is even.")
    if name.startswith("and_"):
        return {"in_a": f"a = {val}.", "in_b": f"b = {val}.",
                "in_a_hi": yn(val, "a is at least 2.", "a is less than 2.")}.get(unit)
    if name == "or_alt":
        return {"s_hi": f"S shifted right by one bit (S // 2) equals {val}.", "s_lo": f"The lowest bit of S is {val}.",
                "cipher": f"C = {val}.", "key": f"R = {val}."}.get(unit)
    if name == "mixed":
        X = "XYZ"
        return {"first": f"The first step is {X[val]}.", "last": f"The last step is {X[val]}.",
                "exec0": f"Step X is executed by P{val}.",
                "exec0_not_me": yn(val, "Step X is not executed by P0.", "Step X is executed by P0."),
                "step0_before_1": yn(val, "Step X comes before step Y.", "Step Y comes before step X.")}.get(unit)
    return None


SETUP = {
    "fact": ("Employee E has a secret salary band, an integer from 0 to 7.", "an integer 0-7, e.g. 5"),
    "relation": ("Four students s0, s1, s2, s3 each have exactly one advisor among A, B, C, D, and no two students share an advisor.",
                 'a list of the advisors of s0, s1, s2, s3 in order, e.g. ["B","A","D","C"]'),
    "serial": ("Five procedure steps P, Q, R, S, T are each performed exactly once in some secret order.",
               'the full order as a list, e.g. ["Q","P","T","R","S"]'),
    "parallel": ("Three independent branches 1, 2, 3 each have a secret setting from {0,1,2,3}.",
                 "a list of the three settings for branches 1, 2, 3, e.g. [2,0,3]"),
    "and_xor": ("Two hidden inputs a and b are each an integer from 0 to 3. The secret is a XOR b (bitwise).", "an integer, e.g. 2"),
    "and_sum": ("Two hidden inputs a and b are each an integer from 0 to 3. The secret is a + b.", "an integer, e.g. 4"),
    "and_max": ("Two hidden inputs a and b are each an integer from 0 to 3. The secret is max(a, b).", "an integer, e.g. 1"),
    "or_alt": ("A secret S is an integer 0-7 and a key R is an integer 0-7. C = S XOR R (bitwise).", "the value of S, an integer 0-7"),
    "mixed": ("Three steps X, Y, Z are performed in a secret order, and step X is executed by one of three people P0, P1, P2.",
              'an object {"order": ["Y","X","Z"], "executor": "P2"}'),
}

PROMPT = """You are trying to infer a secret.

{setup}
All possibilities consistent with this description are equally likely a priori.

Facts you have learned:
{facts}

Give your single best guess of the secret, then your second and third best guesses (all different).
Answer format for each guess: {fmt}.
Reply with JSON only: {{"guesses": [best, second, third]}}"""


def to_secret(name, g):
    try:
        if name == "relation":
            return tuple(L.index(c) for c in g)
        if name == "serial":
            return tuple(STEPS.index(c) for c in g)
        if name == "parallel":
            return tuple(int(v) for v in g)
        if name == "mixed":
            return (tuple("XYZ".index(c) for c in g["order"]), int(str(g["executor"]).lstrip("P")))
        return int(g)
    except Exception:
        return None


def sample_states(per, seed=0):
    rng = random.Random(seed)
    items = []
    bins = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.999), (0.999, 1.01)]
    for st in S.all_structures():
        T = engine.build(st)
        M = len(T.V1)
        cand = {b: [] for b in range(len(bins) + 1)}
        for mask in range(M):
            if not mask & T.relevant:
                continue
            for x in range(0, len(T.st.worlds), 4):          # skip nuisance copies (same S/units, decoys aside)
                v = T.V1[mask, x]
                if T.cov[mask]:
                    cand[len(bins)].append((mask, x))
                    continue
                for bi, (lo, hi) in enumerate(bins):
                    if lo <= v < hi:
                        cand[bi].append((mask, x))
        per_bin = max(1, per // (len(bins) + 1))
        for b, lst in cand.items():
            for mask, x in rng.sample(lst, min(per_bin, len(lst))):
                if rng.random() < 0.3:                       # sometimes add a decoy fact
                    mask |= T.bit(rng.choice(T.st.decoys))
                items.append((st.name, mask, x, b))
    return items


def decoy_text(unit, w):
    return {"d_room": f"The meeting room is in wing {'NS'[w[-1][0]]}.", "d_shift": f"The team's shift is {'early' if w[-1][1] else 'late'}."}[unit]


def job(item):
    name, mask, x, b = item
    st = {s.name: s for s in S.all_structures()}[name]
    T = engine.build(st)
    w = st.worlds[x]
    facts = []
    for u in T.names(mask):
        facts.append(decoy_text(u, w) if u in st.decoys else render(name, u, st.units[u](w)))
    order = list(facts)
    random.Random(hash((name, mask, x)) % 2 ** 31).shuffle(order)
    setup, fmt = SETUP[name]
    return {"key": {"structure": name, "mask": mask, "x": x, "bin": b},
            "prompt": PROMPT.format(setup=setup, facts="\n".join(f"- {f}" for f in order) or "- (none)", fmt=fmt),
            "truth": st.secret(w), "V1": float(T.V1[mask, x]), "P3": float(T.P3[mask, x]), "H": float(T.H[mask, x]),
            "cov": bool(T.cov[mask]), "det": bool(T.det[mask, x]), "prior_V1": T.prior_V1()}


def call(j):
    from experiments.cogniguard_comparison_phase2.protocol_b.run_native import chat
    t0 = time.time()
    try:
        out = chat("glm-5.2", [{"role": "user", "content": j["prompt"]}])
    except Exception as e:  # noqa: BLE001
        out = f"ERROR {e}"
    m = re.search(r"\{.*\}", out or "", re.S)
    gs = []
    try:
        gs = json.loads(m.group(0))["guesses"] if m else []
    except Exception:
        gs = []
    sec = [to_secret(j["key"]["structure"], g) for g in gs[:3]]
    truth = tuple(j["truth"]) if isinstance(j["truth"], tuple) else j["truth"]
    norm = lambda s: json.dumps(s)
    hit1 = bool(sec) and norm(sec[0]) == norm(truth)
    hit3 = any(norm(s) == norm(truth) for s in sec)
    return {**j["key"], "V1": j["V1"], "P3": j["P3"], "H": j["H"], "cov": j["cov"], "det": j["det"],
            "prior_V1": j["prior_V1"], "hit1": hit1, "hit3": hit3, "parsed": len(sec), "raw": (out or "")[:300],
            "latency_s": round(time.time() - t0, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=42)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    items = sample_states(a.per)
    jobs = [job(i) for i in items]
    done = set()
    if OUT.exists():
        done = {(r["structure"], r["mask"], r["x"]) for r in map(json.loads, OUT.read_text().splitlines())}
    todo = [j for j in jobs if (j["key"]["structure"], j["key"]["mask"], j["key"]["x"]) not in done]
    print("items", len(jobs), "todo", len(todo), flush=True)
    if a.dry:
        print(todo[0]["prompt"])
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex, open(OUT, "a") as h:
        for i, r in enumerate(ex.map(call, todo)):
            h.write(json.dumps(r) + "\n")
            h.flush()
            if i % 50 == 0:
                print(i, flush=True)
    print("done")


if __name__ == "__main__":
    main()
