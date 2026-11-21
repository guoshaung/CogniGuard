"""Independent check of recorded policy/action pairs, not an external effect observer."""
import json
from pathlib import Path

path = Path(__file__).parent / "runs/fixture_01/observations.jsonl"
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
expected = {
    ("current_policy_reread", "ALLOW"): True,
    ("current_policy_reread", "DENY"): False,
    ("version_bound_gate_no_repair", "ALLOW"): False,
    ("version_bound_gate_no_repair", "DENY"): False,
    ("version_bound_gate_one_repair", "ALLOW"): True,
    ("version_bound_gate_one_repair", "DENY"): False,
}
assert len(rows) == 6 and len({(r["arm"], r["policy"]) for r in rows}) == 6
for row in rows:
    actual = row["committed_action"] is not None
    assert actual == expected[(row["arm"], row["policy"])]
    assert row["denied_use"] == (row["policy"] == "DENY" and actual)
    assert row["authorized_use"] == (row["policy"] == "ALLOW" and actual)
print("6/6 recorded decisions match independent presence/absence checks; external effects NOT_RUN")
