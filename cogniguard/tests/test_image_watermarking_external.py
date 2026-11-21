from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cogniguard.protection import image_watermarking as image_wm


def _png_bytes(color: tuple[int, int, int] = (64, 128, 192)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _capabilities(**overrides: Any) -> dict[str, Any]:
    payload = {
        "supports_single_image": True,
        "embed_real_pipeline_available": True,
        "verify_real_pipeline_available": True,
        "attack_real_pipeline_available": False,
        "supports_64bit_capsule": True,
        "supports_vlm": False,
        "notes": [],
    }
    payload.update(overrides)
    return payload


def test_generate_protected_image_uses_sce_locguard_embed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    source = Image.new("RGB", (128, 128), (20, 90, 140))
    service_image = tmp_path / "service_watermarked.png"
    Image.new("RGB", (128, 128), (22, 92, 142)).save(service_image, format="PNG")

    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "auto")
    monkeypatch.setenv("SCE_LOCGUARD_OUTPUT_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(image_wm, "OUTPUT_DIR", tmp_path / "teaching_images")
    monkeypatch.setattr(image_wm, "_request_remote_image", lambda **_: (source, None))
    def fake_capabilities() -> dict[str, Any]:
        calls.append("capabilities")
        return _capabilities()

    monkeypatch.setattr(image_wm, "_sce_locguard_capabilities", fake_capabilities)

    def fake_post(path: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        calls.append(path)
        assert path == "/api/v1/watermark/embed"
        assert Path(payload["image_path"]).exists()
        assert payload["semantic_metadata"]["source"] == "cogniguard_teaching_image_generation"
        return {
            "status": "ok",
            "job_id": "embed_test",
            "implementation_level": "real_pipeline",
            "watermarked_image_path": str(service_image),
            "payload_id": "payload_test",
            "capsule_bits": "0" * 64,
            "auth_hash": "auth_test",
            "source_registry_registered": True,
            "auth_level": "hmac_registry",
            "capsule_schema": "hmac_source_capsule_v1",
            "psnr": 38.5,
            "message": "ok",
        }

    monkeypatch.setattr(image_wm, "_sce_locguard_post", fake_post)

    [item] = image_wm.generate_protected_teaching_images(
        prompt="draw a coordinate diagram",
        answer_id="ans_test",
        resource_id="res_test",
        count=1,
    )

    assert calls == ["capabilities", "/api/v1/watermark/embed"]
    assert item.watermark["scheme"] == "sce_locguard_editguard_api_v1"
    assert item.watermark["external_watermark"]["job_id"] == "embed_test"
    assert "capsule_bits" not in item.watermark["external_watermark"]
    assert "auth_hash" not in item.watermark["external_watermark"]
    sidecar = json.loads(Path(item.local_path).with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar["external_watermark"]["status"] == "ok"


def test_detect_image_watermark_uses_sce_locguard_blind_verify(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    image_bytes = _png_bytes()

    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "auto")
    monkeypatch.setenv("SCE_LOCGUARD_OUTPUT_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(image_wm, "SCE_LOCGUARD_UPLOAD_DIR", tmp_path / "uploads")
    def fake_capabilities() -> dict[str, Any]:
        calls.append("capabilities")
        return _capabilities()

    monkeypatch.setattr(image_wm, "_sce_locguard_capabilities", fake_capabilities)

    def fake_post(path: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        calls.append(path)
        assert path == "/api/v1/watermark/verify"
        assert Path(payload["image_path"]).exists()
        return {
            "status": "ok",
            "job_id": "verify_test",
            "implementation_level": "real_pipeline",
            "auth_status": "registered_source",
            "integrity_check_passed": True,
            "source_registry_match": True,
            "exact_registry_match": True,
            "registered_owner_id": "res_test",
            "payload_recovered": True,
            "capsule_recovered": True,
            "bit_accuracy": 0.97,
            "attack_regime": "clean_candidate",
            "reports": [],
            "message": "ok",
        }

    monkeypatch.setattr(image_wm, "_sce_locguard_post", fake_post)

    result = image_wm.detect_image_watermark(
        image_bytes,
        {"image_id": "cg_img_test", "resource_id": "res_test"},
    )

    assert calls == ["capabilities", "/api/v1/watermark/verify"]
    assert result["detection_method"] == "sce_locguard_blind_verify_api"
    assert result["watermark_detected"] is True
    assert result["source_authenticated"] is True
    assert result["detection_confidence"] == 0.97
    assert result["external_watermark"]["job_id"] == "verify_test"


def test_corrected_registry_match_is_labeled_and_not_reported_as_exact_auth(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "auto")
    monkeypatch.setenv("SCE_LOCGUARD_OUTPUT_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(image_wm, "SCE_LOCGUARD_UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(image_wm, "_sce_locguard_capabilities", lambda: _capabilities())

    def fake_post(path: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        assert path == "/api/v1/watermark/verify"
        return {
            "status": "ok",
            "job_id": "verify_corrected",
            "implementation_level": "real_pipeline",
            "auth_status": "registered_source_corrected",
            "integrity_check_passed": False,
            "source_registry_match": True,
            "exact_registry_match": False,
            "correction_applied": True,
            "registry_hamming_distance": 1,
            "correction_radius": 1,
            "correction_candidate_count": 1,
            "correction_ambiguous": False,
            "registered_owner_id": "res_corrected",
            "registered_payload_id": "payload_corrected",
            "payload_recovered": True,
            "capsule_recovered": True,
            "reports": [],
            "message": "ok",
        }

    monkeypatch.setattr(image_wm, "_sce_locguard_post", fake_post)

    result = image_wm.detect_image_watermark(
        _png_bytes(),
        {"image_id": "cg_img_corrected", "resource_id": "res_corrected"},
    )

    assert result["watermark_detected"] is True
    assert result["source_authenticated"] is False
    assert result["corrected_source_authenticated"] is True
    assert result["source_authentication_type"] == "corrected_registry"
    assert result["exact_registry_match"] is False
    assert result["system_resource"] is False
    assert result["registry_hamming_distance"] == 1


def test_paper_mode_rejects_embed_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "paper")
    monkeypatch.setattr(image_wm, "OUTPUT_DIR", tmp_path / "teaching_images")
    monkeypatch.setattr(
        image_wm,
        "_request_remote_image",
        lambda **_: (Image.new("RGB", (128, 128), (12, 34, 56)), None),
    )
    monkeypatch.setattr(
        image_wm,
        "_embed_with_sce_locguard",
        lambda *_args, **_kwargs: {
            "provider": "sce_locguard",
            "status": "unavailable",
            "message": "test service unavailable",
        },
    )

    with pytest.raises(RuntimeError, match="requires real SCE-LocGuard embed"):
        image_wm.generate_protected_teaching_images(
            prompt="draw a triangle",
            answer_id="ans_strict",
            resource_id="res_strict",
        )


def test_auto_mode_marks_embed_fallback_as_not_paper_eligible(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "auto")
    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_STRICT", "false")
    monkeypatch.setattr(image_wm, "OUTPUT_DIR", tmp_path / "teaching_images")
    monkeypatch.setattr(
        image_wm,
        "_request_remote_image",
        lambda **_: (Image.new("RGB", (128, 128), (12, 34, 56)), None),
    )
    monkeypatch.setattr(
        image_wm,
        "_embed_with_sce_locguard",
        lambda *_args, **_kwargs: {
            "provider": "sce_locguard",
            "status": "unavailable",
            "message": "test service unavailable",
        },
    )

    [item] = image_wm.generate_protected_teaching_images(
        prompt="draw a triangle",
        answer_id="ans_auto",
        resource_id="res_auto",
    )

    assert item.watermark["implementation_level"] == "local_frequency_fallback"
    assert item.watermark["paper_eligible"] is False


def test_paper_mode_rejects_verify_and_attack_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "paper")
    monkeypatch.setattr(image_wm, "WATERMARK_ATTACK_DIR", tmp_path / "attacks")
    monkeypatch.setattr(
        image_wm,
        "_verify_with_sce_locguard",
        lambda *_args, **_kwargs: {
            "provider": "sce_locguard",
            "status": "unavailable",
            "message": "test verify unavailable",
        },
    )
    monkeypatch.setattr(
        image_wm,
        "_attack_with_sce_locguard",
        lambda *_args, **_kwargs: {
            "provider": "sce_locguard",
            "status": "unavailable",
            "message": "test attack unavailable",
        },
    )

    with pytest.raises(RuntimeError, match="requires real SCE-LocGuard verify"):
        image_wm.detect_image_watermark(_png_bytes())
    with pytest.raises(RuntimeError, match="requires real SCE-LocGuard attack"):
        image_wm.attack_image_watermark(_png_bytes())


def test_narra_image_request_omits_model_when_unconfigured(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    image_bytes = _png_bytes()

    monkeypatch.setenv("NARRA_IMAGE_BASE_URL", "https://narralucky.example/v1")
    monkeypatch.setenv("NARRA_IMAGE_API_KEY", "narra_sk_test")
    monkeypatch.delenv("NARRA_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_IMAGE_MODEL", raising=False)

    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._body

    def fake_urlopen(request: urllib.request.Request | str, timeout: float) -> FakeResponse:
        if isinstance(request, urllib.request.Request):
            if request.full_url.endswith("/images/generations"):
                payload = json.loads(request.data.decode("utf-8"))
                calls.append(payload)
                return FakeResponse(json.dumps({"data": [{"url": "https://image.example/out.png"}]}).encode("utf-8"))
            assert request.full_url == "https://image.example/out.png"
            assert request.get_header("User-agent") == "CogniGuard/1.0"
            return FakeResponse(image_bytes)
        return FakeResponse(image_bytes)

    monkeypatch.setattr(image_wm.urllib.request, "urlopen", fake_urlopen)

    image, source_url = image_wm._request_remote_image(prompt="draw vertex form", size="1024x1024")

    assert image is not None
    assert source_url == "https://image.example/out.png"
    assert calls == [{"prompt": "draw vertex form", "size": "1024x1024", "response_format": "url"}]
