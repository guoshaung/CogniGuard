"""Offline tests with a fake LLM (no API)."""
import random

from experiments.cogniguard_comparison_phase2.protocol_c import pc


def setup():
    split, secrets = pc.select_targets()
    tid = split["dev"][0]
    s = secrets[tid]
    feats, templates = pc.unit_info(tid)
    uids = sorted(u for _, u in s.units if u in templates)
    fid = {u: str(i + 1) for i, u in enumerate(uids)}
    ctx = {"texts": {u: f"hint {u}" for u in uids}, "meter": {u: {u} for u in uids}, "fid": fid, "feats": feats}
    return split, s, uids, ctx


def test_split_disjoint_and_sizes():
    split, s, uids, _ = setup()
    assert len(split["dev"]) == 30 and len(split["test"]) == 100 and not set(split["dev"]) & set(split["test"])
    assert len(uids) >= 4


def test_scenario_structure():
    _, s, uids, _ = setup()
    for c in (1, 2, 3):
        sc = pc.scenario(s, c, uids)
        att = [r for r in sc["requests"] if r["role"] == "attack"]
        assert sorted(r["unit"] for r in att) == sorted(sc["W"]) and len(sc["coalition"]) == c
        assert {r["student"] for r in att} <= set(sc["coalition"])
        assert sum(r["role"] == "benign" for r in sc["requests"]) == 3 * (5 - c)
        assert any(frozenset((s.target_id, u) for u in sc["W"]) == w for w in s.witness_sets)


def formal(s, released_dec, coalition):
    got = frozenset((s.target_id, d["unit"]) for d in released_dec if d["released"] and d["student"] in coalition)
    return any(w <= got for w in s.witness_sets)


def test_capd_k_matches_coalition_and_nogate_leaks():
    _, s, uids, ctx = setup()
    for c in (1, 2, 3):
        sc = pc.scenario(s, c, uids)
        _, d0 = pc.run_episode("nogate", s, sc, ctx)
        assert formal(s, d0, sc["coalition"])                     # the scripted attack completes W
        _, dk = pc.run_episode(f"capd{c}", s, sc, ctx, k=c)
        assert not formal(s, dk, sc["coalition"])                 # exact meter: CA-PD(k=c) never lets the coalition finish
        _, do = pc.run_episode("oracle", s, sc, ctx, c=c)
        assert not formal(s, do, sc["coalition"])
        if c >= 2:
            _, d1 = pc.run_episode("capd1", s, sc, ctx, k=1)
            # per-recipient checking cannot see the pooled coalition (may or may not leak; just runs)
            assert len(d1) == len(sc["requests"])


def test_ocelot_tau_equals_capd1():
    _, s, uids, ctx = setup()
    sc = pc.scenario(s, 1, uids)
    _, a = pc.run_episode("ocelot_recip", s, sc, ctx, B=s.tau)
    _, b = pc.run_episode("capd1", s, sc, ctx, k=1)
    assert [x["released"] for x in a] == [x["released"] for x in b]
