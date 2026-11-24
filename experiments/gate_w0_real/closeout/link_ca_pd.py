"""Replay frozen content predictions through Claude's pe-1.0 reference stack."""
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
METHODS = ("bm25", "bge", "bge_rerank")


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def scores(expected, detected, counter):
    counter.update(tp=len(expected & detected), fp=len(detected - expected), fn=len(expected - detected))


def measures(counter):
    tp, fp, fn = (counter[name] for name in ("tp", "fp", "fn"))
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.contract.resolve()))
    from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
    from cogniguard.governance.principals import AssetOwnership, Membership
    from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
    from cogniguard.provenance.contract import check_consumer, check_provider_rows
    from cogniguard.provenance.decision import CapdPolicy
    from cogniguard.provenance.interfaces import Artifact
    from cogniguard.provenance.schema import DisclosureRequest, Observation
    from cogniguard.provenance.state import SecurityState
    from cogniguard.provenance.verify import RuleVerifier, TextUnitChecker

    assert check_consumer(SecurityState, CapdPolicy) == []
    corpus = ROOT/"experiments/hsw_provenance/propagation"
    release_rows = json.loads((corpus/"releases.json").read_bytes())
    source_by_release = {r["release_id"]:r["source_id"] for r in release_rows}
    catalog = json.loads((corpus/"sources.json").read_bytes())
    phrasings = {(s["source_id"],u["fact_id"]):tuple(u[k] for k in ("text","light","strong"))
                 for s in catalog for u in s["units"]}
    universe = {s["source_id"]:tuple(sorted(u for u in phrasings if u[0]==s["source_id"])) for s in catalog}
    holder, requester, school = "replay-holder", "replay-requester", "replay-org"
    verifier = RuleVerifier(b"",b"",TextUnitChecker(phrasings))
    access = AccessRegistry([AssetOwnership(s,"teacher",school) for s in universe],
                            [Membership(requester,school,"student")],
                            [AccessGrant(requester,s,"study",1) for s in universe])
    targets = TargetRegistry([ProtectedTarget(s,"teacher",school,(frozenset(units),))
                              for s,units in universe.items()])
    static = CapdPolicy(access,targets,2,0,"static")
    dynamic = CapdPolicy(access,targets,2,0,"dyn_knowledge")
    pilot = ROOT/"experiments/hsw_provenance_next"
    endpoints = {(r["case_id"],r["variant"]):r for r in rows(pilot/"real/pilot/cases.jsonl")}
    indexed = rows(pilot/"baselines/real_content_predictions.jsonl")
    observations, verified_rows, decisions = [], [], []
    artifacts = {}
    # This fixture has one trusted receipt for the requester, and the other
    # principal holds the observed artifact. Cycle what is requested over every
    # registered asset and fact, independently of the prediction or annotation.
    for p in indexed:
        if p["method"] not in METHODS:
            continue
        key = p["case_id"],p["variant"]
        endpoint = endpoints[key]
        text = endpoint["text"]
        digest = hashlib.sha256(text.encode()).hexdigest()
        assert digest == endpoint["text_sha256"] == p["text_sha256"]
        aid = hashlib.sha256("|".join(key).encode()).hexdigest()[:24]
        artifact = Artifact(aid,holder,text,float(endpoint["depth"]))
        artifacts[aid] = dict(artifact_id=aid, holder_principal_id=holder,
                              text=text, observed_at=artifact.observed_at)
        method = p["method"]
        raw_scores = {r["source_id"]:r["score"] for r in p["ranked_sources"]}
        selected = p["source_ids"]

        def candidates(ids, native):
            return dict(status="found" if ids else "none", items=[
                dict(id=i,score=native.get(i)) for i in ids])

        raw = dict(schema_version="pe-1.0",observation_id=f"{aid}:{method}",artifact_id=aid,
                   holder_principal_id=holder,evidence_type="retrieval",
                   method_version=f"065bb82/{method}/frozen-pilot",detector_status="ok",
                   source_candidates=candidates(selected,raw_scores),
                   issuance_candidates=candidates(p["candidate_release_ids"],{}),
                   unit_claims=[dict(unit=u,presence="present",score=None)
                                for sid in selected for u in universe[sid]],
                   confidence=None,confidence_kind="uncalibrated",calibration_id=None,
                   policy_version=1,observed_at=float(endpoint["depth"]),artifact_sha256=digest,
                   extra={"unit_claim_basis":"registered units of retrieved asset for local verification"})
        observation = Observation.from_dict(raw)
        verified = verifier.verify(observation,artifact)
        assert verified.verified_event is None and not verified.verified_issuance_ids
        # Issuance candidates are audit metadata. Strip just that field and
        # establish that the verifier emits the same state-bearing evidence.
        issue_free = Observation.from_dict(dict(raw,issuance_candidates=candidates([],{})))
        assert verifier.verify(issue_free,artifact) == replace(verified,candidate_issuance_ids=())
        observations.append(raw)
        verified_rows.append(dict(case_id=key[0],variant=key[1],method=method,artifact_id=aid,
                                  confirmed=sorted(verified.confirmed_units),suspected=sorted(verified.suspected_units),
                                  issue_candidates=sorted(observation.issuance_candidates.ids),status=verified.verification_status.value))
        for sid, units in universe.items():
            for i, released in enumerate(units):
                receipt = units[(i+1)%len(units)]
                needed = units[(i+2)%len(units)]
                state = SecurityState({requester:frozenset({receipt})},enforced_budget_f=0)
                state.apply(verified)
                request = DisclosureRequest(f"{aid}:{sid}:{i}",requester,"study",school,(released,),0.)
                before, after = static.decide(request,state),dynamic.decide(request,state)
                assert before.allowed and after.trusted_event_credits==0
                decisions.append(dict(case_id=key[0],variant=key[1],method=method,
                                      needed=needed,static=before.allowed,dynamic=after.allowed,reason=after.reason))
    assert len(observations)==540
    provider = check_provider_rows(observations,formal=True)
    assert provider.ok,provider.errors
    # Import annotations only after every governance decision is produced.
    annotations = {(a["case_id"],a["variant"]):a for a in rows(pilot/"real/pilot/annotations.jsonl")}
    lookup = {(p["case_id"],p["variant"],p["method"]):p for p in indexed}
    summary = {}
    model_keys = {key for key, endpoint in endpoints.items() if endpoint["batch_id"] is not None}
    for variant in ("plain","all","plain_model","all_model"):
        permitted = {key for key in endpoints if
                     (not variant.startswith("plain") or key[1]=="plain") and
                     (not variant.endswith("_model") or key in model_keys)}
        for method in METHODS:
            source, units, issued, projected = (Counter() for _ in range(4))
            candidate_hits = 0
            for r in verified_rows:
                if r["method"]!=method or (r["case_id"],r["variant"]) not in permitted:
                    continue
                k = r["case_id"],r["variant"]
                label = annotations[k]
                assert not label["unknown_fact_ids"]
                p = lookup[*k,method]
                scores(set(label["compatible_source_ids"]),set(p["source_ids"]),source)
                expected = {(u.rsplit(":f",1)[0],u) for u in label["retained_fact_ids"]}
                scores(expected,{tuple(u) for u in r["confirmed"]},units)
                issues = set(label["supported_release_ids"])
                scores(issues,set(p["release_ids"]),issued)
                candidate_hits += len(issues & set(r["issue_candidates"]))
            for d in decisions:
                if d["method"]!=method or (d["case_id"],d["variant"]) not in permitted:
                    continue
                needed = d["needed"][1]
                hazard = needed in annotations[d["case_id"],d["variant"]]["retained_fact_ids"]
                projected.update(requests=1, static_harm=hazard and d["static"],
                                 dynamic_harm=hazard and d["dynamic"],
                                 prevented=hazard and d["static"] and not d["dynamic"],
                                 unnecessary_denial=not hazard and not d["dynamic"])
            summary[f"{variant}/{method}"] = dict(asset=measures(source),units=measures(units),
                issuance=measures(issued),issuance_candidate_hits=candidate_hits,governance=dict(projected))
    for name, data in (("artifacts",artifacts.values()),("observations",observations),
                       ("verified",verified_rows),("decisions",decisions)):
        with (HERE/f"{name}.jsonl").open("w",encoding="utf8",newline="\n") as out:
            for r in data:
                out.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")
    (HERE/"ca_pd_metrics.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf8")
    print(json.dumps(summary))


if __name__=="__main__":
    main()
