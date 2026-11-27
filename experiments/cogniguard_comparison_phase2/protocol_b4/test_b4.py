import json

from experiments.cogniguard_comparison_phase2.protocol_b4 import gates

CFG = json.load(open("/Users/MBP/Exp/CogniGuard/cogniguard_raw/sumleaks_repo/data/experiment_5_def_adv_both.json"))


class FakeMod:
    class Agent:
        def __init__(self, name):
            self.name = name

        def receive_query(self, from_agent, query):
            return f"answer from {self.name}"


def fake_chat(revealed):
    def chat(model, messages, **_):
        return json.dumps({"revealed": revealed.pop(0)})
    return chat


def test_policy_and_alice():
    W = gates.policy_units(CFG)
    assert W == sorted(["Alice.employee_role_map", "Alice.employee_access_levels", "Niks.employee_health_records",
                        "Hannah.employee_disciplinary_actions"])
    assert gates.alice_units(CFG) == {"Alice.employee_role_map", "Alice.employee_access_levels"}


def run(method, seq, B=None):
    mod = type("M", (), {"Agent": type("A", (FakeMod.Agent,), {})})
    st = gates.install(mod, CFG, method, fake_chat([list(x) for x in seq]), lambda m: None, B=B)
    alice = mod.Agent("Alice")
    outs = [mod.Agent(n).receive_query(alice, "q") for n in ("Niks", "Hannah", "Juan")]
    return outs, st


def test_capd_blocks_only_completion():
    outs, st = run("cg_llm", [["Niks.employee_health_records"], ["Hannah.employee_disciplinary_actions"], []])
    assert outs[0].startswith("answer") and outs[1] == gates.REFUSAL and outs[2].startswith("answer")
    assert st["blocked"] == 1


def test_ocelot_budget():
    seq = [["Niks.employee_health_records"], ["Hannah.employee_disciplinary_actions"], []]
    outs, _ = run("ocelot_r", seq, B=0.34)                 # W' has 2 tables -> first release costs 0.5 > 0.34
    assert outs[0] == gates.REFUSAL and outs[1] == gates.REFUSAL and outs[2].startswith("answer")
    outs, _ = run("ocelot_r", seq, B=0.99)                 # equals CA-PD here
    assert outs[0].startswith("answer") and outs[1] == gates.REFUSAL


def test_unparsable_meter_counts():
    mod = type("M", (), {"Agent": type("A", (FakeMod.Agent,), {})})
    st = gates.install(mod, CFG, "cg_llm", lambda *a, **k: "no json", lambda m: None)
    assert mod.Agent("Niks").receive_query(mod.Agent("Alice"), "q").startswith("answer")
    assert st["meter_unparsable"] == 1


def test_pflow_consult_is_block():
    replies = iter(['{"blocks": [], "recipient_knowledge": ""}', '{"new_inferences": []}',
                    '{"verdict": "consult", "residual_risk": "moderate", "utility": "medium"}'])
    out, rec = gates.pflow_decide(lambda *a, **k: next(replies), CFG, "Niks", "Alice", "q", "ans", [])
    assert out is None and rec["consult_as_block"]
