"""Export and verify Issue #16 judgments from saved predictions, without model calls."""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import sys

from compare import CLOSE, HERE, PILOT, ROOT, rows, sha, write

RESULTS = HERE / "results"
JUDGMENTS = RESULTS / "judgments.jsonl"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def export():
    lock = json.loads((RESULTS / "threshold_lock.json").read_bytes())
    threshold = lock["thresholds"]["nli"]
    weights = lock["models"]["nli"]["weights_sha256"]
    version = f"deberta-v3-base-mnli-fever-anli@sha256-{weights}/max-window-v1"
    artifacts = {row["artifact_id"]: row for row in rows(CLOSE / "artifacts.jsonl")}
    observations = {
        row["artifact_id"]: row
        for row in rows(CLOSE / "observations.jsonl")
        if row["method_version"] == "065bb82/bge/frozen-pilot"
    }
    predictions = {
        row["artifact_id"]: row
        for row in rows(RESULTS / "verified.jsonl")
        if row["method"] == "nli"
    }
    scores = {
        (row["artifact_id"], tuple(row["unit"])): row["diagnostic"]["score"]
        for row in rows(RESULTS / "errors.jsonl")
        if row["method"] == "nli"
    }
    judgments = {}
    candidate_count = 0

    def record(text_sha, unit, confirmed, score, split):
        if score is not None:
            assert (score >= threshold) == confirmed, (text_sha, unit)
        key = text_sha, unit
        value = dict(artifact_sha256=text_sha, unit=unit,
                     judgment="entailment" if confirmed else "neutral", score=score,
                     method_version=version, split=split)
        if key in judgments:
            previous = judgments[key]
            assert previous["judgment"] == value["judgment"] and previous["split"] == split, key
            saved = previous["score"]
            if saved is not None:
                assert score is None or score == saved, key
                return
        judgments[key] = value

    assert observations.keys() == predictions.keys() == artifacts.keys()
    for aid, prediction in predictions.items():
        observation = observations[aid]
        text_sha = digest(artifacts[aid]["text"])
        assert text_sha == observation["artifact_sha256"]
        confirmed = set(map(tuple, prediction["confirmed"]))
        suspected = set(map(tuple, prediction["suspected"]))
        candidates = {tuple(claim["unit"]) for claim in observation["unit_claims"]}
        assert confirmed.isdisjoint(suspected) and confirmed | suspected == candidates
        for unit in sorted(candidates):
            record(text_sha, unit, unit in confirmed, scores.get((aid, unit)), "test")
        candidate_count += len(candidates)

    dev = rows(RESULTS / "dev_scores.jsonl")
    calibration = rows(RESULTS / "development.jsonl")
    assert [{k: v for k, v in row.items() if k != "scores"} for row in dev] == calibration
    negative_scores = [row["scores"]["nli"]["score"] for row in dev if not row["present"]]
    assert math.nextafter(max(negative_scores), math.inf) == threshold
    for row in dev:
        score = row["scores"]["nli"]["score"]
        unit = row["source"], f'{row["source"]}:f1'
        record(digest(row["text"]), unit, score is not None and score >= threshold, score, "calibration")

    return list(judgments.values()), candidate_count, observations, predictions, artifacts


def verify(contract, candidate_count, observations, predictions, artifacts):
    sys.path.insert(0, str(contract.resolve()))
    from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
    from cogniguard.governance.principals import AssetOwnership, Membership
    from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
    from cogniguard.provenance.decision import CapdPolicy
    from cogniguard.provenance.interfaces import Artifact
    from cogniguard.provenance.schema import DisclosureRequest, Observation
    from cogniguard.provenance.state import SecurityState
    from cogniguard.provenance.verify import RuleVerifier
    from experiments.x3_e2e_integration.checkers import NliReplayChecker

    checker = NliReplayChecker(JUDGMENTS, "test")
    verifier = RuleVerifier(b"", b"", checker)
    catalog = json.loads((ROOT / "experiments/hsw_provenance/propagation/sources.json").read_bytes())
    universe = {source["source_id"]: [(source["source_id"], unit["fact_id"])
                                     for unit in source["units"]] for source in catalog}
    universe = {source: sorted(units) for source, units in universe.items()}
    requester, school = "replay-requester", "replay-org"
    access = AccessRegistry([AssetOwnership(source, "teacher", school) for source in universe],
                            [Membership(requester, school, "student")],
                            [AccessGrant(requester, source, "study", 1) for source in universe])
    target = TargetRegistry([ProtectedTarget(source, "teacher", school, (frozenset(units),))
                             for source, units in universe.items()])
    policy = CapdPolicy(access, target, 2, 0, "dyn_knowledge")
    requests = defaultdict(list)
    for row in rows(RESULTS / "decisions.jsonl"):
        if row["method"] == "nli":
            requests[row["case_id"], row["variant"]].append(row)

    replay = []
    for aid, prediction in predictions.items():
        key = prediction["case_id"], prediction["variant"]
        verified = verifier.verify(Observation.from_dict(observations[aid]), Artifact(**artifacts[aid]))
        confirmed = set(verified.confirmed_units)
        assert confirmed == set(map(tuple, prediction["confirmed"])), key
        assert set(verified.suspected_units) == set(map(tuple, prediction["suspected"])), key
        assert verified.verified_event is None and not verified.verified_issuance_ids
        saved_requests = iter(requests[key])
        decisions = []
        for source, units in universe.items():
            for index, released in enumerate(units):
                state = SecurityState({requester: frozenset({units[(index + 1) % 3]})},
                                      enforced_budget_f=0)
                state.apply(verified)
                request = DisclosureRequest(f"{aid}:{source}:{index}", requester, "study", school, (released,), 0.)
                decision = policy.decide(request, state)
                needed = units[(index + 2) % 3]
                original = next(saved_requests)
                assert tuple(original["needed"]) == needed
                assert (decision.allowed, decision.reason, decision.trusted_event_credits) == (
                    original["dynamic"], original["reason"], 0), (key, needed)
                decisions.append((needed, decision.allowed))
        assert next(saved_requests, None) is None
        replay.append((key, confirmed, decisions))

    # Scoring references are opened after policy replay and never passed to the checker.
    endpoints = rows(PILOT / "real/pilot/cases.jsonl")
    plain = {(row["case_id"], row["variant"]) for row in endpoints
             if row["variant"] == "plain" and row["batch_id"] is not None}
    annotations = {(row["case_id"], row["variant"]): row
                   for row in rows(PILOT / "real/pilot/annotations.jsonl")}
    metrics = Counter()
    for key, confirmed, decisions in replay:
        if key not in plain:
            continue
        annotation = annotations[key]
        assert not annotation["unknown_fact_ids"]
        retained = {(fact.rsplit(":f", 1)[0], fact) for fact in annotation["retained_fact_ids"]}
        metrics.update(tp=len(confirmed & retained), fp=len(confirmed - retained), fn=len(retained - confirmed))
        for needed, allowed in decisions:
            hazard = needed in retained
            metrics.update(hazard=hazard, safe=not hazard, dangerous_allow=hazard and allowed,
                           over_refusal=not hazard and not allowed)

    summary = json.loads((RESULTS / "summary.json").read_bytes())["comparison"]["plain_model/nli"]
    units, governance = summary["units"], summary["governance"]
    assert all(metrics[key] == units[key] for key in ("tp", "fp", "fn"))
    assert all(metrics[key] == governance[key] for key in ("hazard", "safe", "dangerous_allow", "over_refusal"))
    f1 = 2 * metrics["tp"] / (2 * metrics["tp"] + metrics["fp"] + metrics["fn"])
    assert f1 == units["f1"]
    assert candidate_count == 1254 and len(replay) == 180
    print(f'180 endpoints, {candidate_count} endpoint-unit predictions, '
          f'{sum(len(decisions) for _, _, decisions in replay)} policy decisions matched. '
          f'Plain model: {metrics["tp"]}/{metrics["tp"] + metrics["fn"]}, F1={f1:.3f}, '
          f'dangerous allow {metrics["dangerous_allow"]}/{metrics["hazard"]}, '
          f'over-refusal {metrics["over_refusal"]}/{metrics["safe"]}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True, help="integration checkout at b23c42c")
    parser.add_argument("--export", action="store_true", help="write the judgment and split files")
    args = parser.parse_args()
    values, candidate_count, observations, predictions, artifacts = export()
    if args.export:
        with JUDGMENTS.open("w", encoding="utf-8", newline="\r\n") as stream:
            for row in values:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        development = rows(RESULTS / "development.jsonl")
        stress = [row for row in rows(RESULTS / "stress.jsonl") if row["method"] == "nli"]
        pilot = rows(PILOT / "real/pilot/cases.jsonl")
        chains = lambda records: sorted({row["chain_id"] for row in records})
        assert set(chains(development)).isdisjoint(chains(stress) + chains(pilot))
        assert set(chains(stress)).isdisjoint(chains(pilot))
        write(RESULTS / "splits.json", {
            "calibration_chains": chains(development), "stress_chains": chains(stress),
            "pilot_test_chains": chains(pilot),
            "plain_model_test_chains": chains([row for row in pilot if row["variant"] == "plain"
                                               and row["batch_id"] is not None]),
            "endpoint_candidate_decisions": candidate_count,
            "judgment_rows": dict(Counter(row["split"] for row in values)),
            "null_scores": dict(Counter(row["split"] for row in values if row["score"] is None)),
            "judgments_sha256": sha(JUDGMENTS),
        })
    manifest = json.loads((RESULTS / "splits.json").read_bytes())
    assert sha(JUDGMENTS) == manifest["judgments_sha256"]
    # Normalize exported tuples the same way JSONL does when comparing the file to source data.
    assert rows(JUDGMENTS) == json.loads(json.dumps(values))
    verify(args.contract, candidate_count, observations, predictions, artifacts)


if __name__ == "__main__":
    main()
