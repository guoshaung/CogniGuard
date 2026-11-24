"""Contract checks that Codex (provider) and Grok (consumer) run on their own branches.

Provider:  python -m cogniguard.provenance.contract provider observations.jsonl [--formal]
Consumer:  from cogniguard.provenance.contract import check_consumer
           failures = check_consumer(make_state, make_policy)   # [] means compatible

Passing the contract shows interface compatibility only. It says nothing about
detection quality or security benefit (the fixtures are mock data).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from cogniguard.provenance.interfaces import Artifact
from cogniguard.provenance.mock import observation, signed_credential, signed_event
from cogniguard.provenance.schema import (
    UNKNOWN,
    DisclosureRequest,
    EvidenceType,
    Observation,
    Presence,
    SchemaError,
)
from cogniguard.provenance.verify import RuleVerifier

PROVIDER_TYPES = {EvidenceType.FINGERPRINT, EvidenceType.RETRIEVAL, EvidenceType.WATERMARK,
                  EvidenceType.JOINT, EvidenceType.KNOWLEDGE_BOUND_WATERMARK,
                  EvidenceType.SIGNED_CREDENTIAL, EvidenceType.TRUSTED_LOG}


@dataclass
class ProviderReport:
    rows: int = 0
    errors: list[str] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_provider_rows(rows: Iterable[dict], formal: bool = False) -> ProviderReport:
    rep, seen = ProviderReport(), set()
    for i, row in enumerate(rows):
        rep.rows += 1
        try:
            obs = Observation.from_dict(row)
        except SchemaError as exc:
            rep.errors.append(f"row {i}: {exc}")
            continue
        if obs.observation_id in seen:
            rep.errors.append(f"row {i}: duplicate observation_id {obs.observation_id}")
        seen.add(obs.observation_id)
        if obs.evidence_type not in PROVIDER_TYPES and (formal or obs.evidence_type is EvidenceType.IDEAL):
            rep.errors.append(f"row {i}: providers may not emit {obs.evidence_type.value}")
        if formal and (obs.method_version.startswith("mock") or obs.extra.get("mock")):
            rep.errors.append(f"row {i}: mock record in formal mode")
        rep.by_type[obs.evidence_type.value] = rep.by_type.get(obs.evidence_type.value, 0) + 1
    return rep


# ----------------------------------------------------------------------------- consumer

LOG_KEY, CRED_KEY = b"contract-log-key", b"contract-credential-key"
U1, U2, U3 = ("exam", "u1"), ("exam", "u2"), ("exam", "u3")


def fixture():
    """Teacher T owns 'exam' with one witness {u1, u2, u3}; students A, B, C may read it."""
    targets = TargetRegistry([ProtectedTarget("exam", "T", "school", (frozenset({U1, U2, U3}),))])
    access = AccessRegistry(
        [AssetOwnership("exam", "T", "school")],
        [Membership(p, "school", "student") for p in "ABC"] + [Membership("T", "school", "teacher")],
        [AccessGrant(p, "exam", "study", 1) for p in "AB"],  # C has no grant
    )
    receipts = {"A": frozenset({U1})}
    texts = {U1: ("the exam covers fraction multiplication",), U2: ("the answer is three eighths",),
             U3: ("question seven uses a number line",)}
    return targets, access, receipts, texts


def _req(principal, unit, rid="r"):
    return DisclosureRequest(rid, principal, "study", "school", (unit,), 0.0)


def check_consumer(
    make_state: Callable[[dict, int | None], object],
    make_policy: Callable[[object, object, int, int, str], object],
    modes: tuple[str, ...] = ("static", "dyn_knowledge", "dyn_full", "dyn_conservative"),
) -> list[str]:
    """make_state(receipts, enforced_budget_f) -> StateUpdater;
    make_policy(access_registry, target_registry, k, f, mode) -> DisclosurePolicy."""
    from cogniguard.provenance.verify import TextUnitChecker
    targets, access, receipts, texts = fixture()
    failures: list[str] = []
    art_b = Artifact("art-b", "B", "Note: the answer is three eighths.", 1.0)
    art_x = Artifact("art-x", UNKNOWN, "the answer is three eighths.", 1.0)
    verifier = RuleVerifier(LOG_KEY, CRED_KEY, TextUnitChecker(texts), allow_mock=True)

    def fresh(f=0):
        return make_state(dict(receipts), f)

    for mode in modes:
        # C1 evidence never authorizes: C has no grant.
        s = fresh()
        for t in (EvidenceType.WATERMARK, EvidenceType.KNOWLEDGE_BOUND_WATERMARK):
            s.apply(verifier.verify(observation(f"c1-{t.value}", "art-b", "C", evidence_type=t,
                                                units=(U3,), issuance_ids=("iss-C",)), art_b))
        s.apply(verifier.verify(observation("c1-cred", "art-b", "C",
                                            evidence_type=EvidenceType.SIGNED_CREDENTIAL,
                                            credential=signed_credential(CRED_KEY, "iss-C")), art_b))
        if make_policy(access, targets, 2, 0, mode).decide(_req("C", U3), s).allowed:
            failures.append(f"[{mode}] C1: evidence authorized an ungranted principal")

        # C2 unverified claims never reach the confirmed layer.
        s = fresh()
        s.apply(verifier.verify(observation("c2", "art-b", "B", evidence_type=EvidenceType.WATERMARK,
                                            units=(U3,)), art_b))  # U3 is not in the text -> conflict
        s.apply(verifier.verify(observation("c2b", "art-x", UNKNOWN, evidence_type=EvidenceType.WATERMARK,
                                            units=(U2,)), art_x))   # holder UNKNOWN -> suspected only
        if any(U3 in v or U2 in v for v in s.knowledge("confirmed").values()):
            failures.append(f"[{mode}] C2: unverified or conflicting claim entered the confirmed layer")

        # C3 only trusted logs earn budget credits; C4 duplicates count once.
        s = fresh(f=2)
        for t in (EvidenceType.WATERMARK, EvidenceType.JOINT, EvidenceType.FINGERPRINT):
            s.apply(verifier.verify(observation(f"c3-{t.value}", "art-b", "B", evidence_type=t,
                                                units=(U2,)), art_b))
        s.apply(verifier.verify(observation("c3-cred", "art-b", "B", evidence_type=EvidenceType.SIGNED_CREDENTIAL,
                                            credential=signed_credential(CRED_KEY, "iss-B")), art_b))
        if s.trusted_event_credits() != 0:
            failures.append(f"[{mode}] C3: non-log evidence produced budget credit")
        ev = signed_event(LOG_KEY, "evt-1", "A", "B")
        for oid in ("c4-a", "c4-b"):
            s.apply(verifier.verify(observation(oid, "art-b", "B", evidence_type=EvidenceType.TRUSTED_LOG,
                                                event=ev), art_b))
        s.apply(verifier.verify(observation("c4-c", "art-b", "B", evidence_type=EvidenceType.TRUSTED_LOG,
                                            event=signed_event(LOG_KEY, "evt-1", "C", "B")), art_b))
        # Interface §8: duplicates / conflicts / forgeries count once or not at all.
        # A consumer that never credits (more conservative) passes.
        credited = s.trusted_event_credits()
        if credited > 1:
            failures.append(f"[{mode}] C4: duplicate / conflicting event counted more than once ({credited})")
        forged = observation("c4-forged", "art-b", "B", evidence_type=EvidenceType.TRUSTED_LOG,
                             event=signed_event(b"wrong-key", "evt-9", "A", "B"))
        s.apply(verifier.verify(forged, art_b))
        if s.trusted_event_credits() > credited:
            failures.append(f"[{mode}] C4: forged log signature was credited")

        # C5 content evidence only tightens: confirmed B-holds-U2 must turn allow into deny for A+B+u3 at k=3.
        s0, s1 = fresh(), fresh()
        s1.apply(verifier.verify(observation("c5", "art-b", "B", evidence_type=EvidenceType.WATERMARK,
                                             units=(U2,)), art_b))
        p = make_policy(access, targets, 3, 0, mode)
        before, after = p.decide(_req("B", U3), s0).allowed, p.decide(_req("B", U3), s1).allowed
        if after and not before:
            failures.append(f"[{mode}] C5: content evidence relaxed a decision")
        if mode != "static" and after:
            failures.append(f"[{mode}] C5: a verified holding was ignored by a dynamic mode")

        # C6 detector errors and UNKNOWN change nothing.
        s = fresh()
        s.apply(verifier.verify(observation("c6", "art-b", "B", error=True), art_b))
        if s.knowledge("confirmed+suspected") != fresh().knowledge("confirmed+suspected"):
            failures.append(f"[{mode}] C6: an error observation changed state")
    return failures


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "provider":
        with open(argv[1]) as h:
            rows = [json.loads(line) for line in h if line.strip()]
        rep = check_provider_rows(rows, formal="--formal" in argv)
        print(json.dumps({"rows": rep.rows, "by_type": rep.by_type, "errors": rep.errors[:50],
                          "ok": rep.ok}, ensure_ascii=False, indent=2))
        return 0 if rep.ok else 1
    if argv[:1] == ["consumer-reference"]:
        from cogniguard.provenance.decision import CapdPolicy
        from cogniguard.provenance.state import SecurityState
        fails = check_consumer(lambda r, f: SecurityState(r, f),
                               lambda a, t, k, f, m: CapdPolicy(a, t, k, f, m))
        print(json.dumps({"failures": fails, "ok": not fails}, ensure_ascii=False, indent=2))
        return 0 if not fails else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
