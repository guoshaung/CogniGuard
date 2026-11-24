"""X3-E2E governance runner. It never receives evaluation labels: there is no gold argument,
and scenario / observation loaders reject gold-like fields.

  replay:  python -m experiments.x3_e2e_integration.run --scenario S.json --observations O.jsonl \
               --keys K.json --arm F_STRONG --mode dyn_full --out OUT [--formal]
  online:  ... --detector package.module:DetectorClass   (called once per artifact, pe-1.0 SourceDetector)
  mock:    ... --arm MOCK                                 (engineering only; refused with --formal)
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import time
from pathlib import Path

from cogniguard.provenance.decision import CapdPolicy
from cogniguard.provenance.schema import SCHEMA_VERSION, EvidenceType, Observation
from cogniguard.provenance.state import SecurityState
from cogniguard.provenance.verify import RuleVerifier, TextUnitChecker
from experiments.x3_e2e_integration.arms import ARMS, MOCK_ARM, MODES
from experiments.x3_e2e_integration.scenario import load_scenario

HERE = Path(__file__).resolve().parent
CHECK_THRESHOLD = 0.95  # frozen in PREREG_X3E2E §4


class RefusedInput(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_observations(paths, arm, formal: bool) -> list[Observation]:
    out = []
    for path in paths:
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            obs = Observation.from_dict(json.loads(line))  # rejects gold fields
            is_mock = obs.evidence_type is EvidenceType.MOCK or obs.method_version.startswith("mock") \
                or bool(obs.extra.get("mock"))
            if formal and is_mock:
                raise RefusedInput(f"mock record {obs.observation_id} in a formal run")
            if obs.evidence_type in arm.evidence_types and (
                    not arm.method_prefixes or obs.method_version.startswith(arm.method_prefixes)):
                out.append(obs)
    return out


def make_checker(spec: str | None, phrasings):
    """'lexical' (default, frozen) or 'nli-replay:<judgments.jsonl>[:<split>]'."""
    if not spec or spec == "lexical":
        return TextUnitChecker(phrasings, CHECK_THRESHOLD), "lexical-containment-0.95"
    kind, _, rest = spec.partition(":")
    if kind != "nli-replay" or not rest:
        raise ValueError(spec)
    path, _, split = rest.partition(":")
    from experiments.x3_e2e_integration.checkers import NliReplayChecker
    checker = NliReplayChecker(Path(path), split or None)
    return checker, f"nli-replay:{','.join(sorted(checker.method_versions))}:{split or 'all'}"


def run(scenario_path, observation_paths, keys_path, arm_name, mode, formal=False, detector=None,
        unit_checker=None):
    def goldish(p) -> bool:
        p = Path(p)
        return p.name.lower().startswith("gold") or "gold" in (part.lower() for part in p.parent.parts)
    if goldish(scenario_path) or any(goldish(p) for p in observation_paths) or (keys_path and goldish(keys_path)):
        raise RefusedInput("governance inputs may not be gold files")
    arm = MOCK_ARM if arm_name == "MOCK" else ARMS[arm_name]
    if formal and arm is MOCK_ARM:
        raise RefusedInput("MOCK arm cannot run in formal mode")
    if mode not in MODES:
        raise ValueError(mode)
    sc = load_scenario(scenario_path)
    keys = json.loads(Path(keys_path).read_text()) if keys_path else {}
    checker, checker_name = make_checker(unit_checker, sc.phrasings)
    if unit_checker and "gold" in str(unit_checker).lower():
        raise RefusedInput("unit-checker inputs may not be gold files")
    verifier = RuleVerifier(keys.get("log_key", "").encode(), keys.get("credential_key", "").encode(),
                            checker, allow_ideal=arm.allow_ideal, allow_mock=arm is MOCK_ARM)
    state = SecurityState(sc.receipts, enforced_budget_f=sc.f if sc.f > 0 else None)
    policy = CapdPolicy(sc.access, sc.targets, sc.k, sc.f, mode)
    observations = load_observations(observation_paths, arm, formal)
    artifacts = {a.artifact_id: a for a in sc.artifacts}

    # Event order: artifacts (online detection) and observations at their time, then requests.
    events = [(o.observed_at, 0, "obs", o) for o in observations]
    if detector is not None:
        events += [(a.observed_at, 0, "art", a) for a in sc.artifacts]
    events += [(r.now, 1, "req", r) for r in sc.requests]
    events.sort(key=lambda e: (e[0], e[1], getattr(e[3], "observation_id", getattr(e[3], "request_id", ""))))

    decisions, deltas, verified_log = [], 0, []
    for _t, _p, kind, item in events:
        if kind == "art":
            for obs in detector.detect(item):
                if obs.evidence_type in arm.evidence_types:
                    state.apply(verifier.verify(obs, item))
                    deltas += 1
        elif kind == "obs":
            ev = verifier.verify(item, artifacts.get(item.artifact_id))
            state.apply(ev)
            verified_log.append({"artifact_id": item.artifact_id, "status": ev.verification_status.value,
                                 "confirmed": sorted(list(u) for u in ev.confirmed_units)})
            deltas += 1
        else:
            t0 = time.perf_counter()
            dec = policy.decide(item, state)
            seconds = time.perf_counter() - t0
            if dec.allowed:
                state.record_delivery(item.principal_id, item.release_units)
            decisions.append(dec.to_dict() | {"seconds": seconds})
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    manifest = {
        "interface": SCHEMA_VERSION, "scenario_id": sc.scenario_id, "arm": arm.name, "mode": mode,
        "upper_bound": arm.upper_bound, "mock": arm is MOCK_ARM, "formal": formal, "git_commit": commit,
        "scenario_sha256": _sha(scenario_path),
        "observations_sha256": {str(p): _sha(p) for p in observation_paths},
        "observations_used": len(observations), "evidence_applied": deltas,
        "state_conflicts": state.conflicts, "detector": getattr(detector, "method_version", None),
        "unit_checker": checker_name,
        "verified": verified_log,
    }
    return decisions, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, type=Path)
    ap.add_argument("--observations", nargs="*", default=[], type=Path)
    ap.add_argument("--keys", type=Path)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument("--detector", help="module:Class implementing SourceDetector (online mode)")
    ap.add_argument("--formal", action="store_true")
    ap.add_argument("--unit-checker", default="lexical", help="lexical | nli-replay:<judgments.jsonl>[:<split>]")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    detector = None
    if a.detector:
        mod, cls = a.detector.split(":")
        detector = getattr(importlib.import_module(mod), cls)()
    decisions, manifest = run(a.scenario, a.observations, a.keys, a.arm, a.mode, a.formal, detector,
                              a.unit_checker)
    tag = "" if a.unit_checker == "lexical" else "__nli"
    out = a.out / manifest["scenario_id"] / f"{a.arm}__{a.mode}{tag}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "decisions.jsonl").write_text("".join(json.dumps(d) + "\n" for d in decisions))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"out": str(out), "decisions": len(decisions), "allowed": sum(d["allowed"] for d in decisions)}))


if __name__ == "__main__":
    main()
