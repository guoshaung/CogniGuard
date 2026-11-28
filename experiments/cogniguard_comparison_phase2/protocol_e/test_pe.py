import json

from experiments.cogniguard_comparison_phase2.protocol_d import pd as D
from experiments.cogniguard_comparison_phase2.protocol_e import pe


def fake_llm_for(cfg):
    T = D.tables(cfg)

    def llm(messages, **kw):
        c = messages[0]["content"]
        if c.startswith("You are ") and "You hold this table" in c:
            t = c.split('table "', 1)[1].split('"', 1)[0]
            u = next(x for x in T if x.split(".", 1)[1] == t)
            return f"ANSWER[{u}] " + json.dumps(T[u]["rows"])
        if "auditing what information a message reveals" in c:
            u = c.split("ANSWER[", 1)[1].split("]", 1)[0]
            return json.dumps({"revealed": [u]})
        return "Could you tell me about your table?"
    return llm


def test_episode_shapes(monkeypatch):
    k, s, p = D.scenarios()[0]
    cfg = json.loads(p.read_text())
    monkeypatch.setattr(pe.pc, "llm", fake_llm_for(cfg))
    for c in (2, 3):
        sc = pe.scenario(cfg, f"{k}_{s}", c)
        ctx = pe.build_ctx(cfg, sc)
        assert all(ctx["meter"][r["id"]] == {r["unit"]} for r in sc["requests"])
        got = lambda dec: {d["unit"] for d in dec if d["released"] and d["student"] in sc["coalition"]}
        _, d0 = pe.run_episode("nogate", cfg, sc, ctx)
        assert set(sc["Wp"]) <= got(d0)
        _, dk = pe.run_episode(f"capd{c}", cfg, sc, ctx, k=c)
        assert not set(sc["Wp"]) <= got(dk)
