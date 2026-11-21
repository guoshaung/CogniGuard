"""Frozen FEEDBACK_PROTOCOL.md synthetic feedback-only mechanism probe.

No dependencies, GPU, real student data, model calls, network or file writes.
Prints aggregate JSON for all prespecified conditions.
"""
from collections import defaultdict
import json
import random

SEEDS = 100
ROUNDS = 200
RATES = (0.0, 0.1, 0.3, 0.6, 1.0)
ACTIONS = ("minimal", "extra")


def run(mastery, mask, rate, arm):
    # Entries are success and failure pseudo-counts, one pair per action.
    posterior = {name: [1, 1] for name in ACTIONS}
    rows = []
    for i, value in enumerate(mastery):
        if arm == "frozen":
            action = "minimal"
        elif (i + 1) % 10 == 0:
            action = ACTIONS[((i + 1) // 10 - 1) % 2]
        else:
            def objective(name):
                successes, failures = posterior[name]
                return successes / (successes + failures) - (0.10 if name == "extra" else 0)
            action = max(ACTIONS, key=objective)

        # Receiver can see mastery under either action; the extra value is not
        # read. Judge recomputes independently from the original task input.
        response = "review" if value < 0.5 else "advance"
        truth = "advance" if value >= 0.5 else "review"
        correct = response == truth
        eligible = bool(mask[i] < rate and action == "minimal" and correct)
        reported = correct and not eligible
        feedback = correct if arm == "verified" else reported
        if arm != "frozen":
            posterior[action][0 if feedback else 1] += 1
        rows.append({"action": action, "correct": correct,
                     "corrupted": eligible, "report": reported})
    return rows


def main():
    summary = []
    for rate in RATES:
        aggregates = {arm: defaultdict(int) for arm in ("frozen", "verified", "untrusted")}
        per_seed = {arm: [] for arm in aggregates}
        blocks = {arm: [0] * 5 for arm in aggregates}
        for seed in range(SEEDS):
            rng = random.Random(seed)
            mastery = [rng.random() for _ in range(ROUNDS)]
            mask = [rng.random() for _ in range(ROUNDS)]
            runs = {arm: run(mastery, mask, rate, arm) for arm in aggregates}
            assert all(item["correct"] for rows in runs.values() for item in rows)
            assert all(item["action"] == "minimal" for item in runs["frozen"])
            if rate == 0:
                assert [r["action"] for r in runs["verified"]] == [r["action"] for r in runs["untrusted"]]
            for arm, rows in runs.items():
                stats = aggregates[arm]
                extra = sum(r["action"] == "extra" for r in rows)
                per_seed[arm].append(extra)
                stats["rounds"] += len(rows)
                stats["extra_releases"] += extra
                stats["fields_released"] += len(rows) + extra
                stats["correct"] += sum(r["correct"] for r in rows)
                # Count applied reports only for the untrusted learner; frozen
                # and verified policies receive no attacker-modified feedback.
                stats["corrupted_updates"] += sum(r["corrupted"] for r in rows) if arm == "untrusted" else 0
                stats["minimal_actions"] += len(rows) - extra
                for i, row in enumerate(rows):
                    blocks[arm][i // 40] += row["action"] == "extra"
        result = {"rate": rate, "arms": {}}
        for arm in aggregates:
            values = dict(aggregates[arm])
            values["extra_per_seed_min"] = min(per_seed[arm])
            values["extra_per_seed_max"] = max(per_seed[arm])
            values["extra_by_40_round_block"] = blocks[arm]
            result["arms"][arm] = values
        summary.append(result)
    print(json.dumps({"classification": "SYNTHETIC_FEEDBACK_MECHANISM_NOT_DEPLOYED_ATTACK",
                      "seeds": SEEDS, "rounds_per_seed": ROUNDS,
                      "conditions": summary}, indent=2))


if __name__ == "__main__":
    main()
