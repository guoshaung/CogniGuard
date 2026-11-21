import json
from fractions import Fraction

# Frozen source facts and contract: see REAL_TASK_SUFFICIENCY_PROTOCOL.md.
source_answer = Fraction(15, 4)
calculated_answer = Fraction(1, 2) * 30 * Fraction(1, 2) ** 2
assert calculated_answer == source_answer
cases = [("correct", Fraction(15, 4)), ("incorrect", Fraction(19, 4))]
marker = "SYNTHETIC_PRIVATE_FLAG"
results = []
for name, answer in cases:
    truth = "ADVANCE" if answer == calculated_answer else "REVIEW"
    profile = {"answer_joules": str(answer), "irrelevant_marker": marker}
    bit = answer == calculated_answer
    payloads = {
        "full_profile": (profile, "ADVANCE" if Fraction(profile["answer_joules"]) == source_answer else "REVIEW"),
        "local_correctness_bit": (bit, "ADVANCE" if bit else "REVIEW"),
        "local_action": (truth, truth),
        "no_message_default_review": (None, "REVIEW"),
    }
    for method, (payload, action) in payloads.items():
        serialized = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        results.append({"case": name, "method": method, "action": action,
                        "matches_contract": action == truth,
                        "marker_directly_transmitted": marker.encode() in serialized,
                        "payload_bytes": len(serialized)})
assert sum(r["matches_contract"] for r in results if r["method"] == "no_message_default_review") == 1
assert all(r["matches_contract"] for r in results if r["method"] != "no_message_default_review")
print(json.dumps({"source_answer_joules": str(source_answer), "results": results}, indent=2))
