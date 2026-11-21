"""Final-output policy and actual local HSW-ST provenance without model calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from cogniguard.protection.output_validation import validate_output
from cogniguard.protection.text_provenance import TextProvenanceService, WatermarkUnavailableError

ORIGINAL = (
    "The private teacher manuscript explains a distinctive sequence of classroom observations "
    "and unpublished evaluation findings about carefully staged conceptual interventions. "
    "These original examples and exact instructor annotations must remain in the protected repository."
)


def test_private_values_are_rejected_without_echoing_them_in_diagnostics():
    private = "PRIVATE_ADDRESS_SENTINEL_582"
    result = validate_output("The address is " + private, private_values=[private])
    assert not result.allowed
    assert "private_profile_value_reproduced" in result.reasons
    assert private not in result.text
    assert private not in json.dumps(result.to_dict())
    assert not validate_output("姓名：王 明", private_values=["王明"]).allowed
    assert not validate_output("电话：13800138000", private_values=["13800138000"]).allowed
    assert validate_output("The result is 0.4.", private_values=["0.4"]).allowed


def test_exact_unapproved_original_is_blocked_but_short_public_knowledge_is_not():
    protected = [{"resource_id": "r1", "content": ORIGINAL}]
    assert not validate_output(ORIGINAL, protected_resources=protected).allowed
    assert validate_output("The solution is x=2.", protected_resources=protected).allowed
    assert validate_output("x=2", protected_resources=[{"content": "x=2"}]).allowed


def test_only_the_approved_quote_is_exempt_from_original_overlap_checks():
    protected = [{"resource_id": "r1", "content": ORIGINAL}]
    quote = ORIGINAL[:110]
    approved = [{"resource_id": "r1", "chunk_id": "c1", "content": quote, "return_mode": "quote"}]
    assert validate_output(quote, protected_resources=protected, approved_chunks=approved).allowed
    assert not validate_output(
        ORIGINAL, protected_resources=protected, approved_chunks=approved
    ).allowed


def test_resource_copy_detection_is_not_evaded_by_punctuation_or_case_changes():
    answer = " / ".join(ORIGINAL.upper().split())
    result = validate_output(answer, protected_resources=[{"content": ORIGINAL}])
    assert not result.allowed


def test_source_claims_must_reference_only_approved_ids():
    assert validate_output("[source:r1] A safe summary", approved_source_ids={"r1"}).allowed
    assert not validate_output("[source:forged] A safe summary", approved_source_ids={"r1"}).allowed
    assert not validate_output("Safe answer", claimed_source_ids={"forged"}).allowed
    assert not validate_output("[source:r1,forged]", approved_source_ids={"r1"}).allowed
    assert not validate_output('source_id="forged"', approved_source_ids={"r1"}).allowed
    assert not validate_output("来源：forged", approved_source_ids={"r1"}).allowed


def test_generic_output_checks_still_run_after_domain_approval():
    class Adapter:
        def check_output(self, text, context):
            return {"decision": "block"}

    result = validate_output("Approved subject matter", guardrail_adapter=Adapter())
    assert not result.allowed
    assert "generic_output_policy_rejected" in result.reasons


def test_local_semantic_watermark_and_final_source_binding_are_verified():
    service = TextProvenanceService(b"s" * 32, required=True)
    record = service.bind(
        "先移项，得到2x=4。因此x=2。",
        answer_id="a1",
        sources=[{"resource_id": "r1", "chunk_id": "c1", "content": "Approved summary"}],
    )
    assert record["text"] != "先移项，得到2x=4。因此x=2。"
    assert record["watermark_verified"] is True
    assert record["mode"] == "semantic"
    assert record["statistical_watermark"] is False
    assert service.verify(record["text"], record)["valid"] is True
    assert (
        service.policy.recover_source(record["watermark_id"])["answer_hash"]
        == record["content_hash"]
    )
    assert "content" not in record["sources"][0]
    assert service.audit.verify()


def test_binding_detects_changed_text_source_or_signature():
    service = TextProvenanceService(b"s" * 32, required=True)
    record = service.bind("A final answer.", answer_id="a1", sources=[{"resource_id": "r1"}])
    assert not service.verify(record["text"] + " changed", record)["valid"]
    forged = deepcopy(record)
    forged["sources"][0]["resource_id"] = "forged"
    assert not service.verify(record["text"], forged)["valid"]
    assert not TextProvenanceService(b"x" * 32).verify(record["text"], record)["valid"]
    assert TextProvenanceService(b"s" * 32).verify(record["text"], record)["valid"]


def test_required_statistical_mode_fails_closed_without_a_real_backend():
    service = TextProvenanceService(b"s" * 32, mode="statistical", required=True)
    with pytest.raises(WatermarkUnavailableError, match="statistical_backend_unavailable"):
        service.bind("Safe answer", answer_id="a1")


def test_optional_unavailable_statistical_mode_is_truthful_and_keeps_safe_text():
    service = TextProvenanceService(b"s" * 32, mode="statistical", required=False)
    record = service.bind("Safe answer", answer_id="a1")
    assert record["text"] == "Safe answer"
    assert record["mode"] == "provenance_only"
    assert record["fallback_reason"] == "statistical_backend_unavailable"
    assert record["watermark_verified"] is False
    assert record["statistical_watermark"] is False
    assert service.verify(record["text"], record)["valid"]


def test_refusal_is_bound_after_replacement_and_never_contains_the_rejected_candidate():
    private = "PRIVATE_ADDRESS_SENTINEL_582"
    checked = validate_output(private, private_values=[private])
    service = TextProvenanceService(b"s" * 32, required=True)
    record = service.bind(checked.text, answer_id="refused")
    assert private not in json.dumps(record)
    assert service.verify(record["text"], record)["valid"]


def test_semantic_detector_failure_respects_the_required_flag(monkeypatch):
    optional = TextProvenanceService(b"s" * 32, required=False)
    monkeypatch.setattr(optional.hybrid, "detect_hybrid", lambda text: {"has_semantic": False})
    record = optional.bind("Safe answer", answer_id="optional")
    assert record["text"] == "Safe answer"
    assert record["mode"] == "provenance_only"
    assert not record["watermark_verified"]
    required = TextProvenanceService(b"s" * 32, required=True)
    monkeypatch.setattr(required.hybrid, "detect_hybrid", lambda text: {"has_semantic": False})
    with pytest.raises(WatermarkUnavailableError):
        required.bind("Safe answer", answer_id="required")


def test_malformed_provenance_records_fail_without_invoking_a_backend():
    service = TextProvenanceService(b"s" * 32, required=True)
    for record in (None, [], {}, {"audit": []}):
        assert not service.verify("answer", record)["valid"]


def test_concurrent_binding_keeps_an_unbroken_audit_chain():
    service = TextProvenanceService(b"s" * 32, required=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(
            pool.map(lambda i: service.bind("Safe answer", answer_id=f"a{i}"), range(20))
        )
    assert len(service.audit.records) == 20
    assert service.audit.verify()
    assert all(service.verify(record["text"], record)["valid"] for record in records)
