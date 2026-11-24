"""pe-1.0 interface tests. Mock data only: these check compatibility, not effectiveness."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cogniguard.provenance import contract as C
from cogniguard.provenance.decision import CapdPolicy
from cogniguard.provenance.interfaces import Artifact, run_pipeline
from cogniguard.provenance.mock import MockDetector, Planted, observation, signed_credential, signed_event
from cogniguard.provenance.schema import (
    UNKNOWN,
    EvidenceType,
    GoldLeakError,
    Observation,
    SchemaError,
    VerificationStatus,
)
from cogniguard.provenance.state import SecurityState
from cogniguard.provenance.verify import RuleVerifier, TextUnitChecker

SCHEMAS = Path(__file__).resolve().parents[1] / "provenance" / "schemas" / "pe-1.0"


def _ref_state(r, f):
    return SecurityState(r, f)


def _ref_policy(a, t, k, f, m):
    return CapdPolicy(a, t, k, f, m)


def _examples():
    log = signed_event(C.LOG_KEY, "evt-1", "A", "B")
    return [
        observation("o1", "art", "B", evidence_type=EvidenceType.WATERMARK, units=(C.U2,), issuance_ids=("i1",)),
        observation("o2", "art", UNKNOWN, evidence_type=EvidenceType.RETRIEVAL, source_ids=("s1",)),
        observation("o3", "art", "B", evidence_type=EvidenceType.TRUSTED_LOG, event=log),
        observation("o4", "art", "B", evidence_type=EvidenceType.SIGNED_CREDENTIAL,
                    credential=signed_credential(C.CRED_KEY, "i1")),
        observation("o5", "art", "B", evidence_type=EvidenceType.JOINT, error=True),
    ]


def test_round_trip():
    for obs in _examples():
        assert Observation.from_dict(json.loads(json.dumps(obs.to_dict()))) == obs


def test_json_schema_agrees_with_python():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMAS / "observation.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    for obs in _examples():
        assert not list(validator.iter_errors(obs.to_dict())), obs.observation_id
    bad = _examples()[0].to_dict() | {"confidence": 0.7}  # uncalibrated with a confidence
    assert list(validator.iter_errors(bad))
    with pytest.raises(SchemaError):
        Observation.from_dict(bad)
    leak = _examples()[0].to_dict()
    leak["extra"] = {"gold_release": ["i1"]}
    assert list(validator.iter_errors(leak))
    with pytest.raises(GoldLeakError):
        Observation.from_dict(leak)


@pytest.mark.parametrize("mutate", [
    lambda d: d | {"gold_release": ["x"]},
    lambda d: d | {"schema_version": "pe-0.1"},
    lambda d: d | {"evidence_type": "watermark", "event_claim": {"event_id": "e", "sender_principal_id": "A",
                                                                 "receiver_principal_id": "B"}},
    lambda d: d | {"issuance_candidates": {"status": "found", "items": []}},
    lambda d: d | {"confidence_kind": "calibrated", "confidence": 0.9, "calibration_id": None},
    lambda d: d | {"holder_principal_id": ""},
    lambda d: d | {"policy_version": "1"},
])
def test_schema_rejects(mutate):
    with pytest.raises(SchemaError):
        Observation.from_dict(mutate(_examples()[0].to_dict()))


def test_provider_contract_flags_mock_and_ideal_in_formal():
    rows = [o.to_dict() for o in _examples()]
    assert C.check_provider_rows(rows).ok
    mock = observation("m", "art", "B", units=(C.U1,)).to_dict()
    assert not C.check_provider_rows([mock], formal=True).ok
    ideal = observation("i", "art", "B", evidence_type=EvidenceType.IDEAL, units=(C.U1,)).to_dict()
    assert not C.check_provider_rows([ideal]).ok
    assert not C.check_provider_rows(rows + rows).ok  # duplicate ids


def test_reference_consumer_passes_contract():
    assert C.check_consumer(_ref_state, _ref_policy) == []


def test_contract_catches_a_consumer_that_trusts_watermarks():
    class Leaky(SecurityState):
        def apply(self, ev):
            if ev.evidence_type is EvidenceType.WATERMARK and ev.holder_principal_id != UNKNOWN:
                ev = replace(ev, verification_status=VerificationStatus.VERIFIED,
                             confirmed_units=ev.confirmed_units | ev.suspected_units | ev.conflicting_units,
                             suspected_units=frozenset(), conflicting_units=frozenset())
            return super().apply(ev)
    fails = C.check_consumer(lambda r, f: Leaky(r, f), _ref_policy)
    assert any("C2" in f for f in fails)


def test_contract_catches_a_policy_that_lets_evidence_authorize():
    class Permissive(CapdPolicy):
        def decide(self, request, state):
            out = super().decide(request, state)
            return replace(out, allowed=True, reason="allow") if out.reason == "unauthorized" else out
    fails = C.check_consumer(_ref_state, lambda a, t, k, f, m: Permissive(a, t, k, f, m))
    assert any("C1" in f for f in fails)


def test_contract_catches_credit_from_non_log_evidence():
    class Generous(SecurityState):
        def trusted_event_credits(self):
            return len(self._observations) if self.enforced_budget_f else 0
    fails = C.check_consumer(lambda r, f: Generous(r, f), _ref_policy)
    assert any("C3" in f or "C4" in f for f in fails)


def test_state_layers_and_worst_case_event():
    targets, access, receipts, texts = C.fixture()
    v = RuleVerifier(C.LOG_KEY, C.CRED_KEY, TextUnitChecker(texts))
    s = SecurityState(receipts, enforced_budget_f=1)
    art = Artifact("a", "B", "x", 0.0)
    s.apply(v.verify(observation("e", "a", "B", evidence_type=EvidenceType.TRUSTED_LOG,
                                 event=signed_event(C.LOG_KEY, "evt", "A", "B")), art))
    assert C.U1 in s.knowledge("confirmed")["B"]          # B charged with A's holdings
    assert C.U1 not in s.knowledge("receipts").get("B", frozenset())
    assert s.trusted_event_credits() == 1
    p = CapdPolicy(access, targets, k=1, f=1, governance_mode="dyn_full")
    assert p.decide(C._req("B", C.U2), s).coalition_k_effective == 1


def test_mock_detector_pipeline_runs():
    targets, access, receipts, texts = C.fixture()
    det = MockDetector({"a": Planted(units=(C.U2,))})
    art = Artifact("a", "B", "the answer is three eighths", 0.0)
    v = RuleVerifier(C.LOG_KEY, C.CRED_KEY, TextUnitChecker(texts), allow_mock=True)
    s = SecurityState(receipts)
    run_pipeline([art], det.detect(art), v, s)
    assert C.U2 in s.knowledge("confirmed")["B"]
    assert det.detect(art)[0].extra["mock"] is True
