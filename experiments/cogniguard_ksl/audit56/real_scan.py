"""Real-data scan for "witness not covered but secret determined / attack succeeded".

Eedi (real questions, sampled secret): re-verify Lemma 1 from the stored unit supports (true-value
predicates): for every subset A of the retained universe, L*(A) > tau  <=>  A contains a stored witness.
Report the scope gaps the generator documents (direct identifiers excluded, universe truncated to 12).

Sum Leaks (119 official scenarios): owner-policy target vs computed E7 witnesses vs Alice's initial tables;
scenarios with no target; secrets the generator dropped because a single table already determines them;
E7 witnesses already inside Alice's own tables. Reads stored files only (secrets_private.jsonl unread).
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from experiments.cogniguard_comparison_phase2.protocol_b2.diagnose import target_sets
from experiments.datasets.sumleaks import generate as SLG

DATA = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data")
RAW = Path("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data")
OUT = Path(__file__).parent


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def eedi():
    targets = {r["target_id"]: r for r in jl(DATA / "eedi_exam/targets.jsonl")}
    units = defaultdict(dict)
    for u in jl(DATA / "eedi_exam/units.jsonl"):
        units[u["target_id"]][u["unit_id"]] = set(u["satisfied_by"])
    wit = {w["target_id"]: w for w in jl(DATA / "eedi_exam/witness_sets.jsonl")}
    mism, checked, n_sub = 0, 0, 0
    for tid, t in targets.items():
        uni = wit[tid]["universe"]
        sets = [set(s) for s in wit[tid]["sets"]]
        tau, K = wit[tid]["tau_bits"], t["K"]
        dom = set(t["domain"])
        star = {}
        for mask in range(1 << len(uni)):
            A = [uni[i] for i in range(len(uni)) if mask >> i & 1]
            sup = set(dom)
            for u in A:
                sup &= units[tid][u]
            L = math.log2(K / len(sup)) if sup else math.inf
            prev = max((star[mask ^ (1 << i)] for i in range(len(uni)) if mask >> i & 1), default=0.0)
            star[mask] = max(L, prev)
            covered = any(s <= set(A) for s in sets)
            mism += (star[mask] > tau) != covered
            n_sub += 1
        checked += 1
    man = json.loads((DATA / "eedi_exam/MANIFEST.json").read_text())
    return {"targets_checked": checked, "subsets_checked": n_sub, "lemma1_mismatches": mism,
            "scope": man.get("scope"), "max_units": 12,
            "units_per_target": dict(Counter(len(v) for v in units.values()))}


def sumleaks():
    st = {r["target_id"]: r for r in jl(DATA / "sumleaks/targets.jsonl")}
    rows = []
    single_table_drop = 0
    for p in sorted(RAW.glob("experiment_*_def_adv_both.json"), key=lambda p: int(p.name.split("_")[1])):
        sid = int(p.name.split("_")[1])
        cfg = json.loads(p.read_text())
        names = sorted(f"{a}.{t}" for a, s in cfg["data_distribution"].items() for t in s.get("table", {}))
        alice = {n for n in names if n.startswith("Alice.")}
        pol = target_sets(cfg, sid, "policy")
        e7 = target_sets(cfg, sid, "e7")
        has_e7 = f"sl.{sid}" in st
        # generator view: does any candidate secret in this scene leak from a single table?
        scene = SLG.load_scene(p)
        cands = list(SLG.candidates(scene))
        single = 0
        tables = scene["tables"]
        ids = SLG.join_columns(tables, ids_only=True)
        for c in cands[:60]:
            L = SLG.leakage_table(tables, ids, (c["anchor_col"], c["anchor_val"]), (c["target_table"], c["target_col"]), set(c["domain"]))
            tau = max(math.log2(c["K"]) - 1, 0.5)
            w = SLG.minimal_witnesses(L, len(tables), tau)
            single += bool(w) and min(bin(m).count("1") for m in w) < 2
        single_table_drop += single > 0
        e7_sets = [set(w) for w in (e7 or [])] if has_e7 else []
        pol_sets = [set(w) for w in (pol or [])]
        rows.append({"scenario": sid, "has_policy_target": bool(pol_sets), "has_e7": has_e7,
                     "policy_inside_alice": any(w <= alice for w in pol_sets),
                     "e7_inside_alice": any(w <= alice for w in e7_sets),
                     "e7_strictly_smaller_than_policy": any(e < pw for e in e7_sets for pw in pol_sets),
                     "e7_not_subset_of_policy": bool(e7_sets) and bool(pol_sets) and not any(e <= pw for e in e7_sets for pw in pol_sets),
                     "candidates_with_single_table_witness": single, "candidates_examined": min(len(cands), 60)})
    agg = {k: sum(r[k] for r in rows) for k in ("has_policy_target", "has_e7", "policy_inside_alice", "e7_inside_alice",
                                                 "e7_strictly_smaller_than_policy", "e7_not_subset_of_policy")}
    agg["n_scenarios"] = len(rows)
    agg["scenarios_with_a_single_table_leaking_candidate"] = single_table_drop
    return {"summary": agg, "rows": rows}


def main():
    res = {"eedi": eedi(), "sumleaks": sumleaks()}
    (OUT / "real_scan.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(res["eedi"], indent=1))
    print(json.dumps(res["sumleaks"]["summary"], indent=1))


if __name__ == "__main__":
    main()
