"""Re-ask the 56 cases with a short stated derivation, to compare the attacker's path with the minimal
instantiated derivation set. Same backend (glm-5.2, token plan, thinking off, temperature 0)."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiments.cogniguard_ksl import engine, structures as S
from experiments.cogniguard_ksl.attack_llm import job, to_secret

D = Path("/Users/MBP/Exp/CogniGuard/cogniguard_data/ksl")
OUT = Path(__file__).parent

SUFFIX = """

Before the JSON, write at most three short lines: which facts you used and the deduction steps.
Then on the last line give JSON only: {"guesses": [best, second, third]}"""


def call(item):
    from experiments.cogniguard_comparison_phase2.protocol_b.run_native import chat
    j = job(item)
    out = chat("glm-5.2", [{"role": "user", "content": j["prompt"].replace(
        "Reply with JSON only: {\"guesses\": [best, second, third]}", "") + SUFFIX}])
    m = re.findall(r"\{.*\}", out or "", re.S)
    try:
        g = json.loads(m[-1])["guesses"][0]
        hit = json.dumps(to_secret(item[0], g)) == json.dumps(tuple(j["truth"]) if isinstance(j["truth"], tuple) else j["truth"])
    except Exception:
        hit = None
    return {"structure": item[0], "mask": item[1], "x": item[2], "hit1": hit, "text": (out or "")[:900]}


def main():
    cases = json.loads((OUT / "cases56.json").read_text())["cases"]
    rows = [json.loads(l) for l in (D / "attack_llm.jsonl").read_text().splitlines()]
    sel = [(r["structure"], r["mask"], r["x"], r["bin"]) for r in rows if not r["cov"] and r["det"] and r["hit1"]]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(call, sel))
    sts = {s.name: s for s in S.all_structures()}
    # does the stated derivation mention the units of some minimal derivation? (keyword check per unit)
    kw = {"band_ge4": ["4"], "band_ge6": ["6"], "band_odd": ["odd", "even"], "band_mod4_ge2": ["remainder", "mod"],
          "adv_of_s0": ["s0"], "adv_of_s1": ["s1"], "adv_of_s2": ["s2"], "adv_of_s3": ["s3"], "s0_adv_in_A": ["s0"],
          "in_a": ["a ="], "in_b": ["b ="], "in_a_hi": ["a is", "a <", "a ≥", "a >=", "at least 2", "less than 2"],
          "first": ["first"], "last": ["last"], "exec0": ["P"], "exec0_not_me": ["P0"], "step0_before_1": ["before"]}
    for r, c in zip(res, cases):
        t = r["text"].lower()
        r["mentions_a_minimal_derivation"] = any(
            all(any(k.lower() in t for k in kw[u.split("=")[0]]) for u in B) for B in c["minimal_derivations"])
        r["minimal_derivations"] = c["minimal_derivations"]
    summ = {"n": len(res), "hit1": sum(bool(r["hit1"]) for r in res),
            "stated_path_mentions_minimal_derivation": sum(r["mentions_a_minimal_derivation"] for r in res)}
    (OUT / "reasoning56.json").write_text(json.dumps({"summary": summ, "rows": res}, indent=1, ensure_ascii=False) + "\n")
    print(summ)


def reparse():
    """Offline re-parse of the saved replies: take the JSON object that starts with {"guesses" (set notation
    such as s0∈{C,D} in the reasoning broke the first parser), and use compact keyword patterns."""
    from experiments.cogniguard_ksl.attack_llm import job as _job
    d = json.loads((OUT / "reasoning56.json").read_text())
    rows = [json.loads(l) for l in (D / "attack_llm.jsonl").read_text().splitlines()]
    sel = [(r["structure"], r["mask"], r["x"], r["bin"]) for r in rows if not r["cov"] and r["det"] and r["hit1"]]
    for r, item in zip(d["rows"], sel):
        j = _job(item)
        m = re.search(r'\{\s*"guesses".*', r["text"], re.S)
        hit = None
        if m:
            s = m.group(0)
            try:
                g = json.loads(s[: s.rfind("}") + 1])["guesses"][0]
            except Exception:
                g = None
                mm = re.search(r'"guesses"\s*:\s*\[\s*(\[[^\]]*\]|\{[^}]*\}|[^,\]]+)', s)
                if mm:
                    try:
                        g = json.loads(mm.group(1))
                    except Exception:
                        g = None
            if g is not None:
                truth = tuple(j["truth"]) if isinstance(j["truth"], tuple) else j["truth"]
                hit = json.dumps(to_secret(item[0], g)) == json.dumps(truth)
        r["hit1_reparsed"] = hit
    d["summary"]["hit1_reparsed"] = sum(bool(r["hit1_reparsed"]) for r in d["rows"])
    d["summary"]["unparsed_after_reparse"] = sum(r["hit1_reparsed"] is None for r in d["rows"])
    d["summary"]["wrong_after_reparse"] = [(r["structure"], r["text"][:240]) for r in d["rows"] if r["hit1_reparsed"] is False]
    (OUT / "reasoning56.json").write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")
    print({k: v for k, v in d["summary"].items()})


if __name__ == "__main__":
    import sys
    reparse() if "--reparse" in sys.argv else (main(), reparse())
