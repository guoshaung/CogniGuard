"""Read-only, single-case structural audit of previously generated state.

Counts schema-level formula presence; does not infer semantic correctness.
No source text or student identifiers are output. Requires local historical file.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "var/results/c2rag_openstax_real_source_dev_20261101_01/states/P06.json"


def main():
    raw = PATH.read_bytes()
    state = json.loads(raw)["state"]
    facts = state["facts"]
    # This is a literal marker audit, not a semantic parser or proof of leakage.
    marker = "C_1"
    turn6 = [fact for fact in facts if fact.get("source_turn") == 6]
    in_spans = sum(marker in fact.get("source_span", "") for fact in turn6)
    in_structured = sum(marker in str(fact.get(key, "")) for fact in turn6
                        for key in ("subject", "relation", "object", "scope", "time"))
    result = {"source_sha256": hashlib.sha256(raw).hexdigest(), "facts": len(facts),
              "rules": len(state["rules"]), "unresolved": len(state["unresolved"]),
              "turn6_facts": len(turn6), "literal_C1_in_source_spans": in_spans,
              "literal_C1_in_structured_fields": in_structured,
              "interpretation": "literal-schema-diagnostic-only; source spans remain available"}
    assert in_spans > 0 and in_structured == 0 and result["rules"] == 0
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
