import json

from experiments.cogniguard_comparison_phase2.protocol_d import pd
from experiments.cogniguard_comparison_phase2.protocol_d.analyze_d import frontier_value


def test_scenarios_selection():
    j = pd.scenarios()
    assert all(len(pd.wprime(json.loads(p.read_text()))) >= 3 for _, _, p in j)
    assert not any(k == "old" and s in pd.PILOT for k, s, _ in j)
    assert sum(k == "new" for k, _, _ in j) == 55


def ctx_exact(cfg):
    units = [u for u in pd.tables(cfg) if not u.startswith("Alice.")]
    return {"text": {u: f"text {u}" for u in units}, "meter": {u: {u} for u in units}}


def test_capd_between_ledgers():
    k, s, p = pd.scenarios()[0]
    cfg = json.loads(p.read_text())
    ctx = ctx_exact(cfg)
    for c in (2, 3):
        sc = pd.scenario(cfg, f"{k}_{s}", c)
        got = lambda dec: {d["unit"] for d in dec if d["released"] and d["student"] in sc["coalition"]}
        _, d0 = pd.run_episode("nogate", cfg, sc, ctx)
        assert set(sc["Wp"]) <= got(d0)
        _, dk = pd.run_episode(f"capd{c}", cfg, sc, ctx, k=c)
        assert not set(sc["Wp"]) <= got(dk)
        _, dg = pd.run_episode("ocelot_global", cfg, sc, ctx, B=0.99)
        ben = lambda dec: sum(d["released"] for d in dec if d["role"] == "benign")
        assert ben(dk) >= ben(dg)                # CA-PD(k) never refuses more benign than the global ledger at B<1


def test_frontier_interp():
    pts = [(0.1, 0.2), (0.5, 0.6), (0.3, 0.1)]
    assert abs(frontier_value(pts, 0.3) - 0.4) < 1e-9 and frontier_value(pts, 0.05) == 0.2 and frontier_value(pts, 0.9) == 0.6


def test_recon_scoring(monkeypatch):
    k, s, p = pd.scenarios()[0]
    cfg = json.loads(p.read_text())
    Wp = pd.wprime(cfg)
    T = pd.tables(cfg)
    full = {u: T[u]["rows"][:1] for u in Wp}
    monkeypatch.setattr(pd.pc, "llm", lambda *a, **kw: json.dumps(full))
    assert pd.recon_leak(cfg, ["x"], Wp)[0]
    part = {u: T[u]["rows"][:1] for u in Wp[:-1]}
    monkeypatch.setattr(pd.pc, "llm", lambda *a, **kw: json.dumps(part))
    assert not pd.recon_leak(cfg, ["x"], Wp)[0]
    assert not pd.recon_leak(cfg, [], Wp)[0]


def test_frontier_ties():
    pts = [(0.0, 0.44), (0.0, 0.89), (0.3, 0.95)]
    assert frontier_value(pts, 0.0) == 0.89 and frontier_value(pts, -0.1) == 0.89
