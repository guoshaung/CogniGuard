"""Trace the 56 KSL-V2 cases where the adapter's CA-PD said "safe (no witness)" but S was already determined
(V1 = 1) and the LLM attacker guessed it.

For each case: true secret, attacker's facts (unit = value), decoys, public background (the setup text),
minimal instantiated derivation sets (minimal subsets B of the observed TRUE literals with V1(B) = 1, i.e.
prime implicants of the realized observation), the value-independent witness family the adapter used, and
whether the formal CA-PD of docs/FORMAL_DEFINITION_v0.1.md (units = predicates true at s*, derivation sets
computed at s*, Lemma 1) would have contained a derivation set.
"""

from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

from experiments.cogniguard_ksl import engine, structures as S
from experiments.cogniguard_ksl.attack_llm import SETUP, decoy_text, render

D = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl")
OUT = Path(__file__).parent


def lit_text(st, u, w):
    return decoy_text(u, w) if u in st.decoys else render(st.name, u, st.units[u](w))


def prime_implicants(T, view_units, x):
    out = []
    for r in range(1, len(view_units) + 1):
        for B in itertools.combinations(view_units, r):
            if any(set(p) <= set(B) for p in out):
                continue
            if T.V1[T.mask(B), x] > 1 - 1e-12:
                out.append(B)
    return out


def symmetry_class(st, B, w):
    """Value pattern of the minimal derivation, up to relabeling of symmetric inputs/branches."""
    vals = tuple(sorted((u, st.units[u](w)) for u in B))
    if st.name == "and_max":            # a and b are symmetric; only "an input equals 3" matters
        return ("an input = 3",) if any(v == 3 for _, v in vals) else vals
    return tuple(u for u, _ in vals)


def main():
    rows = [json.loads(l) for l in (D / "attack_llm.jsonl").read_text().splitlines()]
    cases = [r for r in rows if not r["cov"] and r["det"] and r["hit1"]]
    assert len(cases) == 56, len(cases)
    sts = {s.name: s for s in S.all_structures()}
    Ts = {n: engine.build(s) for n, s in sts.items()}
    out = []
    for r in cases:
        st, T = sts[r["structure"]], Ts[r["structure"]]
        x, mask = r["x"], r["mask"]
        w = st.worlds[x]
        view = T.names(mask)
        rel = [u for u in view if u not in st.decoys]
        pis = prime_implicants(T, rel, x)
        # value-independent family used by the adapter vs formal (instantiated) derivation sets
        indep_cover = bool(T.cov[mask])
        formal_cover = bool(pis)
        # would every world agreeing on the UNIT IDENTITIES (not values) also be determined? (adapter's test)
        frac_worlds_det = float((T.det[T.mask(rel)] * T.prior).sum())
        out.append({
            "case": len(out) + 1, "structure": st.name, "secret": repr(st.secret(w)),
            "facts": [lit_text(st, u, w) for u in view], "decoys": [u for u in view if u in st.decoys],
            "public_background": SETUP[st.name][0],
            "minimal_derivations": [[f"{u}={st.units[u](w)}" for u in B] for B in pis],
            "minimal_derivation_text": [" & ".join(lit_text(st, u, w) for u in B) for B in pis],
            "adapter_value_independent_witnesses": [T.names(m) for m in T.witnesses],
            "adapter_covered": indep_cover, "formal_capd_covered": formal_cover,
            "share_of_worlds_with_same_units_determined": round(frac_worlds_det, 3),
            "pattern": [list(symmetry_class(st, B, w)) for B in pis],
            "instance_key": json.dumps([st.name, sorted(f"{u}={st.units[u](w)}" for u in rel)]),
        })
    inst = Counter(c["instance_key"] for c in out)
    pat = Counter(json.dumps([c["structure"], sorted(map(str, c["pattern"]))]) for c in out)
    summary = {
        "n_cases": len(out),
        "by_structure": dict(Counter(c["structure"] for c in out)),
        "formal_capd_would_cover": sum(c["formal_capd_covered"] for c in out),
        "adapter_covered": sum(c["adapter_covered"] for c in out),
        "distinct_instances_ignoring_decoys": len(inst),
        "distinct_logical_patterns": len(pat),
        "patterns": {k: v for k, v in pat.most_common()},
        "cases_with_decoys": sum(bool(c["decoys"]) for c in out),
    }
    (OUT / "cases56.json").write_text(json.dumps({"summary": summary, "cases": out}, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
