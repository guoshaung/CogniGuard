from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from protection.supporting.image_watermark.api.service import SCELocGuardService
from protection.supporting.image_watermark.api.schemas import EmbedRequest


def _service(
    tmp_path, secret: str = "paper-secret-for-tests-at-least-32-characters"
) -> SCELocGuardService:
    with patch.dict("os.environ", {"SCE_LOCGUARD_REGISTRY_SECRET": secret}, clear=False):
        return SCELocGuardService(str(tmp_path))


def _valid_capsule(service: SCELocGuardService, copyright_id: int) -> list[int]:
    prefix = [
        (int(copyright_id) >> shift) & 1
        for shift in range(15, -1, -1)
    ] + [0] * 40
    return prefix + service._checksum_bits(prefix, 8)


def _source_capsule(
    service: SCELocGuardService, payload_id: str, nonce: int = 0
) -> tuple[int, list[int]]:
    copyright_id, binding_tag = service._source_capsule_identity(payload_id, nonce)
    prefix = (
        service._int_to_bits(copyright_id, 16)
        + service._int_to_bits(binding_tag, 32)
        + service._int_to_bits(nonce, 8)
    )
    return copyright_id, prefix + service._checksum_bits(prefix, 8)


def _register_source(
    service: SCELocGuardService,
    payload_id: str,
    *,
    owner_id: str = "teacher_resource",
    nonce: int = 0,
) -> tuple[int, list[int]]:
    copyright_id, bits = _source_capsule(service, payload_id, nonce)
    service._register_payload(
        copyright_id=copyright_id,
        owner_id=owner_id,
        semantic_metadata={"resource_id": owner_id},
        payload_id=payload_id,
        payload_seed=20260624 + nonce,
        capsule_bits=service._bits_to_string(bits),
        auth_hash=service._payload_auth_hash(bits, payload_id),
        embed_job_id=f"embed_{payload_id}",
    )
    return copyright_id, bits


def test_checksum_valid_payload_is_not_authenticated_without_registry(tmp_path) -> None:
    service = _service(tmp_path)
    decoded = service._decode_p2_payload(_valid_capsule(service, 321))
    bound = service._bind_decoded_payload_to_registry(decoded)

    assert bound["integrity_check_passed"] is True
    assert bound["capsule_recovered"] is True
    assert bound["source_registry_match"] is False
    assert bound["auth_status"] == "checksum_valid_unregistered"


def test_registered_payload_binds_owner_and_payload_id(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _source_capsule(service, "payload_001")
    service._register_payload(
        copyright_id=copyright_id,
        owner_id="teacher_resource_001",
        semantic_metadata={"resource_id": "resource_001"},
        payload_id="payload_001",
        payload_seed=20260624,
        capsule_bits=service._bits_to_string(bits),
        auth_hash=service._payload_auth_hash(bits, "payload_001"),
        embed_job_id="embed_test_001",
    )

    bound = service._bind_decoded_payload_to_registry(service._decode_p2_payload(bits))

    assert bound["auth_status"] == "registered_source"
    assert bound["auth_success"] is True
    assert bound["source_registry_match"] is True
    assert bound["registered_owner_id"] == "teacher_resource_001"
    assert bound["registered_payload_id"] == "payload_001"
    assert bound["registry_auth_level"] == "hmac_registry"


def test_all_64_single_bit_errors_are_uniquely_corrected_without_overwriting_raw_bits(
    tmp_path,
) -> None:
    service = _service(tmp_path)
    _, registered_bits = _register_source(
        service,
        "payload_single_bit",
        owner_id="teacher_single_bit",
    )

    for bit_index in range(64):
        corrupted = list(registered_bits)
        corrupted[bit_index] ^= 1
        raw_bits = service._bits_to_string(corrupted)

        bound = service._bind_decoded_payload_to_registry(
            service._decode_p2_payload(corrupted)
        )

        assert bound["auth_status"] == "registered_source_corrected", bit_index
        assert bound["auth_success"] is True, bit_index
        assert bound["source_registry_match"] is True, bit_index
        assert bound["exact_registry_match"] is False, bit_index
        assert bound["correction_applied"] is True, bit_index
        assert bound["registry_hamming_distance"] == 1, bit_index
        assert bound["correction_radius"] == 1, bit_index
        assert bound["correction_candidate_count"] == 1, bit_index
        assert bound["correction_ambiguous"] is False, bit_index
        assert bound["corrected_integrity_check_passed"] is True, bit_index
        assert bound["capsule_bits"] == raw_bits, bit_index
        assert bound["registered_owner_id"] == "teacher_single_bit", bit_index


def test_all_two_bit_errors_are_rejected_by_radius_one(tmp_path) -> None:
    service = _service(tmp_path)
    _, registered_bits = _register_source(service, "payload_two_bit")

    for first in range(64):
        for second in range(first + 1, 64):
            corrupted = list(registered_bits)
            corrupted[first] ^= 1
            corrupted[second] ^= 1

            bound = service._bind_decoded_payload_to_registry(
                service._decode_p2_payload(corrupted)
            )

            assert bound["source_registry_match"] is False, (first, second)
            assert bound["exact_registry_match"] is False, (first, second)
            assert bound["correction_applied"] is False, (first, second)
            assert bound["correction_candidate_count"] == 0, (first, second)


def test_copyright_id_bit_error_uses_full_codeword_lookup(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, registered_bits = _register_source(
        service,
        "payload_id_bit",
        owner_id="teacher_id_bit",
    )
    corrupted = list(registered_bits)
    corrupted[3] ^= 1
    corrupted_id = service._bits_to_int(corrupted[:16])
    assert corrupted_id != copyright_id
    assert service._read_payload_registry(corrupted_id) is None

    bound = service._bind_decoded_payload_to_registry(
        service._decode_p2_payload(corrupted)
    )

    assert bound["auth_status"] == "registered_source_corrected"
    assert bound["registry_record_found"] is True
    assert bound["registered_owner_id"] == "teacher_id_bit"
    assert bound["registry_hamming_distance"] == 1


def test_invalid_checksum_never_matches_registry(tmp_path) -> None:
    service = _service(tmp_path)
    bits = _valid_capsule(service, 777)
    bits[-1] ^= 1

    bound = service._bind_decoded_payload_to_registry(service._decode_p2_payload(bits))

    assert bound["integrity_check_passed"] is False
    assert bound["source_registry_match"] is False
    assert bound["auth_status"] == "invalid"


def test_same_registered_id_with_different_valid_capsule_is_rejected(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, registered_bits = _source_capsule(service, "payload_888")
    service._register_payload(
        copyright_id=copyright_id,
        owner_id="teacher_resource_888",
        semantic_metadata={"resource_id": "resource_888"},
        payload_id="payload_888",
        payload_seed=20260624,
        capsule_bits=service._bits_to_string(registered_bits),
        auth_hash=service._payload_auth_hash(registered_bits, "payload_888"),
        embed_job_id="embed_test_888",
    )
    forged_prefix = registered_bits[:16] + [registered_bits[16] ^ 1] + registered_bits[17:56]
    forged_bits = forged_prefix + service._checksum_bits(forged_prefix, 8)

    bound = service._bind_decoded_payload_to_registry(service._decode_p2_payload(forged_bits))

    assert bound["integrity_check_passed"] is True
    assert bound["registry_record_found"] is True
    assert bound["exact_registry_match"] is False
    assert bound["source_registry_match"] is False
    assert bound["auth_status"] == "registry_payload_mismatch"


def test_wrong_secret_fails_closed_without_returning_registered_identity(tmp_path) -> None:
    writer = _service(tmp_path, "paper-secret-a-for-tests-at-least-32-characters")
    _, bits = _register_source(
        writer,
        "payload_wrong_secret",
        owner_id="private_teacher_identity",
    )
    reader = _service(tmp_path, "paper-secret-b-for-tests-at-least-32-characters")

    bound = reader._bind_decoded_payload_to_registry(reader._decode_p2_payload(bits))

    assert bound["source_registry_match"] is False
    assert bound["exact_registry_match"] is False
    assert bound["correction_applied"] is False
    assert "registered_owner_id" not in bound
    assert "registered_payload_id" not in bound


def test_corrupted_registry_record_fails_closed(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _register_source(
        service,
        "payload_corrupt_record",
        owner_id="private_corrupt_owner",
    )
    path = service._registry_path(copyright_id)
    assert path is not None
    record = json.loads(path.read_text(encoding="utf-8"))
    record["auth_hash"] = "0" * 16
    path.write_text(json.dumps(record), encoding="utf-8")

    corrupted = list(bits)
    corrupted[-1] ^= 1
    bound = service._bind_decoded_payload_to_registry(
        service._decode_p2_payload(corrupted)
    )

    assert bound["source_registry_match"] is False
    assert bound["correction_applied"] is False
    assert bound["correction_candidate_count"] == 0
    assert "registered_owner_id" not in bound
    assert "registered_payload_id" not in bound


def test_deleted_registry_file_invalidates_same_service_cache(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _register_source(
        service,
        "payload_deleted_record",
        owner_id="private_deleted_owner",
    )
    assert len(service._get_registry_codebook()) == 1
    path = service._registry_path(copyright_id)
    assert path is not None
    path.unlink()

    corrupted = list(bits)
    corrupted[-1] ^= 1
    bound = service._bind_decoded_payload_to_registry(
        service._decode_p2_payload(corrupted)
    )

    assert bound["source_registry_match"] is False
    assert bound["correction_applied"] is False
    assert bound["correction_candidate_count"] == 0
    assert "registered_owner_id" not in bound
    assert len(service._get_registry_codebook()) == 0


def test_added_corrupt_registry_file_invalidates_same_service_cache(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _register_source(
        service,
        "payload_added_corrupt_record",
        owner_id="private_added_owner",
    )
    assert len(service._get_registry_codebook()) == 1
    unused_id = next(value for value in range(65536) if value != copyright_id)
    added_path = service._registry_path(unused_id)
    assert added_path is not None
    added_path.write_text("{}", encoding="utf-8")

    corrupted = list(bits)
    corrupted[-1] ^= 1
    bound = service._bind_decoded_payload_to_registry(
        service._decode_p2_payload(corrupted)
    )

    assert bound["source_registry_match"] is False
    assert bound["correction_applied"] is False
    assert bound["correction_candidate_count"] == 0
    assert "registered_owner_id" not in bound
    with pytest.raises(RuntimeError, match="codebook validation"):
        service._get_registry_codebook()


def test_ambiguous_correction_fails_closed_without_candidate_identity(
    tmp_path, monkeypatch
) -> None:
    service = _service(tmp_path)
    raw_bits = "0" * 64
    raw_value = int(raw_bits, 2)
    fake_entries = (
        {
            "capsule_int": raw_value ^ 1,
            "record": {"owner_id": "private_owner_a", "payload_id": "private_a"},
        },
        {
            "capsule_int": raw_value ^ 2,
            "record": {"owner_id": "private_owner_b", "payload_id": "private_b"},
        },
    )
    monkeypatch.setattr(service, "_get_registry_codebook", lambda: fake_entries)

    bound = service._bind_decoded_payload_to_registry(
        service._decode_p2_payload([0] * 64)
    )

    assert bound["source_registry_match"] is False
    assert bound["correction_applied"] is False
    assert bound["correction_candidate_count"] == 2
    assert bound["correction_ambiguous"] is True
    assert "registered_owner_id" not in bound
    assert "registered_payload_id" not in bound


def test_legacy_v2_record_without_nonce_is_reconstructed_for_correction(tmp_path) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _register_source(
        service,
        "payload_legacy_nonce",
        owner_id="teacher_legacy_nonce",
        nonce=7,
    )
    path = service._registry_path(copyright_id)
    assert path is not None
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record.pop("nonce") == 7
    path.write_text(json.dumps(record), encoding="utf-8")
    fresh_service = _service(tmp_path)
    corrupted = list(bits)
    corrupted[55] ^= 1

    bound = fresh_service._bind_decoded_payload_to_registry(
        fresh_service._decode_p2_payload(corrupted)
    )

    assert bound["auth_status"] == "registered_source_corrected"
    assert bound["registered_owner_id"] == "teacher_legacy_nonce"


def test_registration_rejects_codeword_below_minimum_distance(
    tmp_path, monkeypatch
) -> None:
    service = _service(tmp_path)
    copyright_id, bits = _source_capsule(service, "payload_min_distance")
    capsule_int = int(service._bits_to_string(bits), 2)
    fake_entry = {
        "copyright_id": (copyright_id + 1) % 65536,
        "payload_id": "existing_close_payload",
        "capsule_bits": format(capsule_int ^ 1, "064b"),
        "capsule_int": capsule_int ^ 1,
        "record": {},
    }
    monkeypatch.setattr(service, "_get_registry_codebook", lambda: (fake_entry,))

    with pytest.raises(RuntimeError, match="minimum distance"):
        service._register_payload(
            copyright_id=copyright_id,
            owner_id="teacher_min_distance",
            semantic_metadata={},
            payload_id="payload_min_distance",
            payload_seed=20260624,
            capsule_bits=service._bits_to_string(bits),
            auth_hash=service._payload_auth_hash(bits, "payload_min_distance"),
            embed_job_id="embed_min_distance",
        )


def test_concurrent_registration_keeps_cache_and_files_consistent(tmp_path) -> None:
    service = _service(tmp_path)
    registrations = []
    for index in range(12):
        payload_id = f"payload_concurrent_{index:02d}"
        payload, payload_seed = service._build_unique_registered_payload(
            payload_id=payload_id
        )
        registrations.append((payload_id, payload, payload_seed))

    def register(item) -> None:
        payload_id, payload, payload_seed = item
        bits = payload["bits"]
        service._register_payload(
            copyright_id=int(payload["copyright_id"]),
            owner_id=f"owner_{payload_id}",
            semantic_metadata={},
            payload_id=payload_id,
            payload_seed=payload_seed,
            capsule_bits=service._bits_to_string(bits),
            auth_hash=service._payload_auth_hash(bits, payload_id),
            embed_job_id=f"embed_{payload_id}",
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(register, registrations))

    codebook = service._get_registry_codebook()
    assert len(codebook) == len(registrations)
    assert len(list(service.payload_registry_dir.glob("*.json"))) == len(registrations)
    for _, payload, _ in registrations:
        bound = service._bind_decoded_payload_to_registry(
            service._decode_p2_payload(payload["bits"])
        )
        assert bound["auth_status"] == "registered_source"
        assert bound["exact_registry_match"] is True


def test_binding_id_is_deterministic_and_secret_scoped(tmp_path) -> None:
    first = _service(tmp_path / "a", "secret-a")
    second = _service(tmp_path / "b", "secret-b")
    metadata = {"resource_id": "r1", "answer_id": "a1"}

    binding_a1 = first._payload_binding_id("owner", metadata)
    binding_a2 = first._payload_binding_id("owner", metadata)
    binding_b = second._payload_binding_id("owner", metadata)

    assert binding_a1 == binding_a2
    assert binding_a1 != binding_b
    assert len(binding_a1) == 64


def test_job_report_request_redacts_owner_and_metadata_values(tmp_path) -> None:
    service = _service(tmp_path)
    sanitized = service._sanitize_request_for_report(
        EmbedRequest(
            image_path="input.png",
            owner_id="teacher-real-name",
            semantic_metadata={"student_question": "private question", "resource_id": "r1"},
        )
    )

    serialized = str(sanitized)
    assert "teacher-real-name" not in serialized
    assert "private question" not in serialized
    assert sanitized["semantic_metadata_keys"] == ["resource_id", "student_question"]
