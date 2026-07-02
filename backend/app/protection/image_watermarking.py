from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "teaching_images"
DEFAULT_BASE_URL = "https://narralucky.c0ffee.space/v1"
SYSTEM_LOGO_TEXT = "CogniGuard"
IMAGE_WATERMARK_SECRET = b"cogniguard_image_watermark_demo_v1"
DEFAULT_SCE_LOCGUARD_BASE_URL = "http://127.0.0.1:8010"
SCE_LOCGUARD_JOB_DIR = PROJECT_ROOT / "outputs" / "sce_locguard_jobs"
SCE_LOCGUARD_UPLOAD_DIR = PROJECT_ROOT / "outputs" / "sce_locguard_uploads"
WATERMARK_ATTACK_DIR = PROJECT_ROOT / "outputs" / "watermark_attacks"


@dataclass(frozen=True, slots=True)
class ProtectedTeachingImage:
    image_id: str
    prompt: str
    local_path: Path
    public_url: str
    source_url: str | None
    watermark: dict[str, Any]


def generate_protected_teaching_images(
    *,
    prompt: str,
    answer_id: str,
    resource_id: str,
    count: int = 1,
    size: str = "1024x1024",
) -> list[ProtectedTeachingImage]:
    """Generate protected teaching illustrations and bind visible + hidden watermarks.

    The hidden channel is a SynthID-inspired spread-spectrum frequency watermark.
    Google has not released a general local SynthID image detector API, so this
    implementation keeps the same system boundary: deterministic embedding,
    evidence binding, and blind detection without relying on a visible logo.
    """

    _load_local_env()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated: list[ProtectedTeachingImage] = []
    for index in range(max(1, count)):
        image_id = _image_id(answer_id, resource_id, index)
        source_image, source_url = _request_remote_image(prompt=prompt, size=size)
        generation_source = "remote_ai" if source_image is not None and source_url else "local_placeholder"
        generation_model = _image_generation_model()
        if source_image is None:
            source_image = _placeholder_teaching_image(prompt, index=index)
        watermark_payload = {
            "image_id": image_id,
            "answer_id": answer_id,
            "resource_id": resource_id,
            "variant_index": index,
        }
        source_path = OUTPUT_DIR / f"{image_id}.source.png"
        local_path = OUTPUT_DIR / f"{image_id}.png"
        visible_marked_source = _apply_logo_watermark(source_image.convert("RGB").resize((1024, 1024)), watermark_payload)
        visible_marked_source.save(source_path, format="PNG")
        external_watermark = _embed_with_sce_locguard(
            source_path,
            {
                **watermark_payload,
                "prompt": prompt,
                "source": "cogniguard_teaching_image_generation",
            },
        )
        if external_watermark["status"] == "ok":
            watermark_payload["scheme"] = "sce_locguard_editguard_api_v1"
            protected_path = Path(external_watermark["watermarked_image_path"])
            protected = Image.open(protected_path).convert("RGB")
        else:
            watermark_payload["scheme"] = "synthid_inspired_frequency_watermark_v1"
            protected = embed_image_watermark(source_image, watermark_payload)
        protected.save(local_path, format="PNG")
        sidecar = {
            **watermark_payload,
            "logo_watermark": SYSTEM_LOGO_TEXT,
            "hidden_watermark_present": True,
            "generation_source": generation_source,
            "generation_model": generation_model,
            "source_url": source_url,
            "source_image_path": str(source_path),
            "external_watermark": external_watermark,
        }
        local_path.with_suffix(".json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        generated.append(
            ProtectedTeachingImage(
                image_id=image_id,
                prompt=prompt,
                local_path=local_path,
                public_url=f"/api/teaching-images/{local_path.name}",
                source_url=source_url,
                watermark={
                    **watermark_payload,
                    "logo_watermark": SYSTEM_LOGO_TEXT,
                    "hidden_watermark_present": True,
                    "local_sha256": _sha256_file(local_path),
                    "generation_source": generation_source,
                    "generation_model": generation_model,
                    "source_url": source_url,
                    "external_watermark": external_watermark,
                },
            )
        )
    return generated


def embed_image_watermark(image: Image.Image, payload: dict[str, Any]) -> Image.Image:
    rgb = image.convert("RGB").resize((1024, 1024))
    with_logo = _apply_logo_watermark(rgb, payload)
    return _apply_hidden_frequency_watermark(with_logo, payload)


def detect_image_watermark(image_bytes: bytes, candidate_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    payload = candidate_payload or {}
    external_result = _verify_with_sce_locguard(image_bytes, image, payload)
    if external_result["status"] == "ok":
        return _external_verify_response(image, payload, external_result)

    result = _detect_local_image_watermark(image, payload)
    result["external_watermark"] = external_result
    return result


def attack_image_watermark(
    image_bytes: bytes,
    *,
    attack_type: str = "inpainting",
    prompt: str = "",
) -> dict[str, Any]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((1024, 1024))
    WATERMARK_ATTACK_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(image_bytes + attack_type.encode("utf-8")).hexdigest()[:16]
    source_path = WATERMARK_ATTACK_DIR / f"source_{digest}.png"
    image.save(source_path, format="PNG")

    external_attack = _attack_with_sce_locguard(source_path, attack_type=attack_type, prompt=prompt)
    if external_attack.get("status") == "ok" and external_attack.get("attacked_image_path"):
        attacked_path = Path(external_attack["attacked_image_path"])
        attacked = Image.open(attacked_path).convert("RGB")
        mask_path = external_attack.get("mask_path")
        overlay_path = _make_attack_overlay(image, attacked, digest, mask_path=mask_path)
        implementation_level = external_attack.get("implementation_level", "real_pipeline")
        message = external_attack.get("message") or "AIGC attack generated by SCE-LocGuard."
    else:
        attacked, mask = _local_aigc_attack_preview(image, attack_type=attack_type, prompt=prompt)
        attacked_path = WATERMARK_ATTACK_DIR / f"attacked_{digest}_{_safe_token(attack_type)}.png"
        mask_path_obj = WATERMARK_ATTACK_DIR / f"mask_{digest}_{_safe_token(attack_type)}.png"
        attacked.save(attacked_path, format="PNG")
        mask.save(mask_path_obj, format="PNG")
        mask_path = str(mask_path_obj)
        overlay_path = _make_attack_overlay(image, attacked, digest, mask_path=mask_path)
        implementation_level = "local_preview"
        message = (
            "SCE-LocGuard AIGC attack is unavailable, so CogniGuard created a local attack preview."
        )

    return {
        "success": True,
        "attack_type": attack_type,
        "implementation_level": implementation_level,
        "source_image_path": str(source_path),
        "source_image_url": _artifact_url(source_path),
        "attacked_image_path": str(attacked_path),
        "attacked_image_url": _artifact_url(attacked_path),
        "attacked_image_data": _image_data_url(attacked),
        "mask_path": str(mask_path) if mask_path else None,
        "mask_url": _artifact_url(mask_path),
        "overlay_path": str(overlay_path) if overlay_path else None,
        "overlay_url": _artifact_url(overlay_path),
        "external_attack": external_attack,
        "message": message,
    }


def _detect_local_image_watermark(image: Image.Image, payload: dict[str, Any]) -> dict[str, Any]:
    candidates = _candidate_payloads(payload)
    best: dict[str, Any] | None = None
    for candidate in candidates:
        confidence = _hidden_watermark_confidence(image, candidate)
        result = {
            "candidate_image_id": candidate.get("image_id"),
            "candidate_resource_id": candidate.get("resource_id"),
            "hidden_confidence": confidence,
        }
        if best is None or confidence > best["hidden_confidence"]:
            best = result

    best = best or {"hidden_confidence": 0.0}
    logo_detected = _detect_visible_logo(image)
    hidden_confidence = float(best["hidden_confidence"])
    detected = hidden_confidence >= 0.58 or logo_detected
    tamper_suspicion = logo_detected is False and hidden_confidence >= 0.58
    return {
        "success": True,
        "media_type": "image",
        "watermark_detected": detected,
        "system_resource": detected,
        "detection_confidence": round(max(hidden_confidence, 0.72 if logo_detected else 0.0), 3),
        "detection_method": "synthid_inspired_frequency_correlation",
        "visible_logo_detected": logo_detected,
        "hidden_watermark_detected": hidden_confidence >= 0.58,
        "tamper_suspicion": tamper_suspicion,
        "matched_image_id": best.get("candidate_image_id"),
        "matched_resource_id": best.get("candidate_resource_id"),
        "explanation": (
            "检测到隐式频域水印；即使显示 logo 被删除，仍可通过密钥绑定的频域相关性判断来源。"
            if hidden_confidence >= 0.58
            else "未确认本系统隐式水印；若只有可见 logo 命中，置信度会降低。"
        ),
    }


def image_file_response(filename: str) -> tuple[bytes, str] | None:
    safe_name = Path(filename).name
    path = OUTPUT_DIR / safe_name
    if not path.exists() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return path.read_bytes(), mime


def decode_data_url_or_base64(value: str) -> bytes:
    if "," in value and value.strip().lower().startswith("data:"):
        value = value.split(",", 1)[1]
    return base64.b64decode(value)


def _embed_with_sce_locguard(image_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not _sce_locguard_enabled():
        return _external_status("disabled", "SCE-LocGuard image watermark API is disabled.")
    try:
        capabilities = _sce_locguard_capabilities()
        if not capabilities.get("supports_single_image") or not capabilities.get("embed_real_pipeline_available"):
            return _external_status(
                "unavailable",
                "SCE-LocGuard embed capability is not available.",
                capabilities=capabilities,
            )
        output_dir = _sce_locguard_output_dir()
        response = _sce_locguard_post(
            "/api/v1/watermark/embed",
            {
                "image_path": str(image_path),
                "owner_id": str(payload.get("resource_id") or payload.get("answer_id") or "CogniGuard"),
                "semantic_metadata": payload,
                "output_dir": str(output_dir),
                "strict": True,
            },
            timeout=_sce_locguard_timeout(),
        )
        watermarked_path = response.get("watermarked_image_path")
        if response.get("status") != "ok" or not watermarked_path or not Path(watermarked_path).exists():
            return _external_status(
                "unavailable",
                str(response.get("message") or "SCE-LocGuard embed did not return a watermarked image."),
                capabilities=capabilities,
                response=response,
            )
        return {
            "provider": "sce_locguard",
            "status": "ok",
            "base_url": _sce_locguard_base_url(),
            "job_id": response.get("job_id"),
            "implementation_level": response.get("implementation_level"),
            "payload_id": response.get("payload_id"),
            "capsule_bits": response.get("capsule_bits"),
            "auth_hash": response.get("auth_hash"),
            "psnr": response.get("psnr"),
            "watermarked_image_path": watermarked_path,
            "report_url": _sce_locguard_report_url(response.get("job_id")),
            "capabilities": capabilities,
            "message": response.get("message"),
        }
    except Exception as exc:
        return _external_status("error", f"SCE-LocGuard embed failed: {type(exc).__name__}: {exc}")


def _verify_with_sce_locguard(
    image_bytes: bytes,
    image: Image.Image,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not _sce_locguard_enabled():
        return _external_status("disabled", "SCE-LocGuard image watermark API is disabled.")
    try:
        capabilities = _sce_locguard_capabilities()
        if not capabilities.get("supports_single_image") or not capabilities.get("verify_real_pipeline_available"):
            return _external_status(
                "unavailable",
                "SCE-LocGuard blind verify capability is not available.",
                capabilities=capabilities,
            )
        upload_dir = SCE_LOCGUARD_UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        image_token = _safe_token(payload.get("image_id")) or hashlib.sha256(image_bytes).hexdigest()[:16]
        verify_path = upload_dir / f"verify_{image_token}.png"
        image.convert("RGB").save(verify_path, format="PNG")
        response = _sce_locguard_post(
            "/api/v1/watermark/verify",
            {
                "image_path": str(verify_path),
                "output_dir": str(_sce_locguard_output_dir()),
                "strict": True,
                "return_overlay": True,
            },
            timeout=_sce_locguard_timeout(),
        )
        if response.get("status") != "ok":
            return _external_status(
                "unavailable",
                str(response.get("message") or "SCE-LocGuard verify did not complete."),
                capabilities=capabilities,
                response=response,
            )
        return {
            "provider": "sce_locguard",
            "status": "ok",
            "base_url": _sce_locguard_base_url(),
            "input_image_path": str(verify_path),
            "job_id": response.get("job_id"),
            "report_url": _sce_locguard_report_url(response.get("job_id")),
            "capabilities": capabilities,
            "response": response,
        }
    except Exception as exc:
        return _external_status("error", f"SCE-LocGuard verify failed: {type(exc).__name__}: {exc}")


def _attack_with_sce_locguard(image_path: Path, *, attack_type: str, prompt: str) -> dict[str, Any]:
    if not _sce_locguard_enabled():
        return _external_status("disabled", "SCE-LocGuard image attack API is disabled.")
    try:
        capabilities = _sce_locguard_capabilities()
        if not capabilities.get("attack_real_pipeline_available"):
            return _external_status(
                "unavailable",
                "SCE-LocGuard AIGC attack capability is not available.",
                capabilities=capabilities,
            )
        response = _sce_locguard_post(
            "/api/v1/attack/aigc",
            {
                "image_path": str(image_path),
                "attack_type": _sce_attack_type(attack_type),
                "prompt": prompt or None,
                "output_dir": str(_sce_locguard_output_dir()),
                "mode": "localized_composite",
                "strict": True,
            },
            timeout=_sce_locguard_timeout(),
        )
        attacked_path = response.get("attacked_image_path")
        if response.get("status") != "ok" or not attacked_path or not Path(attacked_path).exists():
            return _external_status(
                "unavailable",
                str(response.get("message") or "SCE-LocGuard attack did not return an attacked image."),
                capabilities=capabilities,
                response=response,
            )
        return {
            "provider": "sce_locguard",
            "status": "ok",
            "base_url": _sce_locguard_base_url(),
            "job_id": response.get("job_id"),
            "implementation_level": response.get("implementation_level"),
            "source_image_path": response.get("source_image_path"),
            "attacked_image_path": attacked_path,
            "diffusion_output_path": response.get("diffusion_output_path"),
            "mask_path": response.get("mask_path"),
            "outside_mask_preserved": response.get("outside_mask_preserved"),
            "report_url": _sce_locguard_report_url(response.get("job_id")),
            "capabilities": capabilities,
            "message": response.get("message"),
        }
    except Exception as exc:
        return _external_status("error", f"SCE-LocGuard attack failed: {type(exc).__name__}: {exc}")


def _external_verify_response(
    image: Image.Image,
    candidate_payload: dict[str, Any],
    external_result: dict[str, Any],
) -> dict[str, Any]:
    response = external_result.get("response") or {}
    reports = response.get("reports") or []
    auth_status = str(response.get("auth_status") or "not_evaluated")
    payload_recovered = bool(response.get("payload_recovered"))
    capsule_recovered = bool(response.get("capsule_recovered"))
    bit_accuracy = response.get("bit_accuracy")
    report_confidence = max(
        [float(item.get("confidence") or 0.0) for item in reports if isinstance(item, dict)] or [0.0]
    )
    if isinstance(bit_accuracy, (int, float)):
        confidence = max(0.0, min(0.99, float(bit_accuracy)))
    elif payload_recovered or capsule_recovered:
        confidence = 0.93
    elif auth_status == "valid":
        confidence = 0.91
    else:
        confidence = max(0.0, min(0.88, report_confidence))

    detected = bool(
        payload_recovered
        or capsule_recovered
        or auth_status in {"valid", "invalid", "tampered"}
        or (isinstance(bit_accuracy, (int, float)) and float(bit_accuracy) >= 0.5)
    )
    attack_regime = str(response.get("attack_regime") or "unknown")
    tamper_suspicion = bool(
        auth_status in {"invalid", "tampered", "failed"}
        or attack_regime not in {"unknown", "clean", "clean_candidate", "not_evaluated"}
        or reports
    )
    return {
        "success": True,
        "media_type": "image",
        "watermark_detected": detected,
        "system_resource": detected,
        "detection_confidence": round(confidence, 3),
        "detection_method": "sce_locguard_blind_verify_api",
        "visible_logo_detected": _detect_visible_logo(image),
        "hidden_watermark_detected": detected,
        "tamper_suspicion": tamper_suspicion,
        "matched_image_id": candidate_payload.get("image_id") or response.get("payload_id"),
        "matched_resource_id": candidate_payload.get("resource_id"),
        "auth_status": auth_status,
        "payload_recovered": payload_recovered,
        "capsule_recovered": capsule_recovered,
        "bit_accuracy": bit_accuracy,
        "attack_regime": attack_regime,
        "predicted_mask_path": response.get("predicted_mask_path"),
        "predicted_mask_url": _artifact_url(response.get("predicted_mask_path")),
        "overlay_path": response.get("overlay_path"),
        "overlay_url": _artifact_url(response.get("overlay_path")),
        "report_json_path": response.get("report_json_path"),
        "report_url": external_result.get("report_url"),
        "reports": reports,
        "external_watermark": external_result,
        "explanation": (
            "已通过 SCE-LocGuard / EditGuard API 进行盲水印验证；"
            "返回了载荷恢复、认证状态和篡改区域报告。"
            if detected
            else "SCE-LocGuard 已完成盲验证，但未确认该图片包含可恢复的系统水印。"
        ),
    }


def watermark_artifact_response(path_value: str) -> tuple[bytes, str] | None:
    if not path_value:
        return None
    try:
        path = Path(urllib.parse.unquote(path_value)).resolve()
    except (OSError, ValueError):
        return None
    if not path.exists() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    allowed_roots = [
        (PROJECT_ROOT / "outputs").resolve(),
        _sce_locguard_output_dir().resolve(),
        SCE_LOCGUARD_UPLOAD_DIR.resolve(),
        WATERMARK_ATTACK_DIR.resolve(),
    ]
    if not any(_is_relative_to(path, root) for root in allowed_roots):
        return None
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return path.read_bytes(), mime


def _sce_locguard_capabilities() -> dict[str, Any]:
    return _sce_locguard_request("GET", "/api/v1/capabilities", timeout=min(15.0, _sce_locguard_timeout()))


def _sce_locguard_post(path: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    return _sce_locguard_request("POST", path, payload=payload, timeout=timeout)


def _sce_locguard_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(
        f"{_sce_locguard_base_url()}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    payload = json.loads(body or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("SCE-LocGuard returned a non-object JSON payload.")
    return payload


def _sce_locguard_enabled() -> bool:
    _load_local_env()
    provider = os.environ.get("COGNIGUARD_IMAGE_WATERMARK_PROVIDER", "auto").strip().lower()
    return provider not in {"", "local", "disabled", "off", "false", "0"}


def _sce_locguard_base_url() -> str:
    _load_local_env()
    return os.environ.get("SCE_LOCGUARD_BASE_URL", DEFAULT_SCE_LOCGUARD_BASE_URL).strip().rstrip("/")


def _sce_locguard_output_dir() -> Path:
    _load_local_env()
    raw = os.environ.get("SCE_LOCGUARD_OUTPUT_DIR", "").strip()
    path = Path(raw) if raw else SCE_LOCGUARD_JOB_DIR
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sce_locguard_timeout() -> float:
    _load_local_env()
    raw = os.environ.get("SCE_LOCGUARD_TIMEOUT_SECONDS", "180").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 180.0


def _sce_locguard_report_url(job_id: Any) -> str | None:
    if not job_id:
        return None
    return f"{_sce_locguard_base_url()}/api/v1/watermark/report/{job_id}"


def _sce_attack_type(attack_type: str) -> str:
    allowed = {"object_removal", "inpainting", "local_replacement", "local_style_edit"}
    normalized = str(attack_type or "inpainting").strip()
    return normalized if normalized in allowed else "inpainting"


def _local_aigc_attack_preview(
    image: Image.Image,
    *,
    attack_type: str,
    prompt: str,
) -> tuple[Image.Image, Image.Image]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    box = (
        int(width * 0.30),
        int(height * 0.24),
        int(width * 0.76),
        int(height * 0.70),
    )
    mask = Image.new("L", rgb.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(box, radius=int(width * 0.045), fill=255)

    attacked = rgb.copy()
    region = rgb.crop(box)
    normalized = _sce_attack_type(attack_type)
    if normalized == "object_removal":
        replacement = rgb.filter(ImageFilter.GaussianBlur(radius=34)).crop(box)
        replacement = ImageEnhance.Color(replacement).enhance(0.45)
    elif normalized == "local_replacement":
        replacement = Image.new("RGB", region.size, (236, 250, 248))
        draw = ImageDraw.Draw(replacement)
        draw.rectangle((0, 0, region.width, region.height), fill=(211, 245, 239))
        draw.ellipse(
            (region.width * 0.18, region.height * 0.14, region.width * 0.82, region.height * 0.80),
            fill=(45, 212, 191),
            outline=(8, 145, 178),
            width=8,
        )
        draw.text((28, 28), (prompt or "AIGC edit")[:28], font=_font(28), fill=(6, 78, 93))
    elif normalized == "local_style_edit":
        replacement = ImageOps.autocontrast(region)
        replacement = ImageEnhance.Color(replacement).enhance(1.9)
        replacement = ImageEnhance.Contrast(replacement).enhance(1.25)
    else:
        replacement = region.filter(ImageFilter.GaussianBlur(radius=18))
        replacement = ImageEnhance.Brightness(replacement).enhance(1.08)
        replacement = ImageEnhance.Color(replacement).enhance(0.72)

    attacked.paste(replacement, box, mask.crop(box))
    return attacked, mask


def _make_attack_overlay(
    original: Image.Image,
    attacked: Image.Image,
    digest: str,
    *,
    mask_path: str | None = None,
) -> Path | None:
    try:
        base = attacked.convert("RGBA")
        if mask_path and Path(mask_path).exists():
            mask = Image.open(mask_path).convert("L").resize(base.size)
        else:
            orig_arr = np.asarray(original.convert("RGB").resize(base.size)).astype(np.int16)
            attacked_arr = np.asarray(attacked.convert("RGB").resize(base.size)).astype(np.int16)
            diff = np.abs(orig_arr - attacked_arr).mean(axis=2)
            mask = Image.fromarray(np.where(diff > 10, 255, 0).astype(np.uint8), mode="L")
        overlay = Image.new("RGBA", base.size, (255, 0, 76, 0))
        overlay.putalpha(mask.point(lambda value: 120 if value > 16 else 0))
        composed = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(composed)
        draw.rectangle((18, 18, 365, 64), fill=(2, 12, 24, 178), outline=(255, 255, 255, 88), width=2)
        draw.text((34, 31), "Predicted modified region", font=_font(24), fill=(255, 255, 255, 235))
        path = WATERMARK_ATTACK_DIR / f"overlay_{digest}.png"
        composed.convert("RGB").save(path, format="PNG")
        return path
    except Exception:
        return None


def _image_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _artifact_url(path_value: Any) -> str | None:
    if not path_value:
        return None
    return f"/api/watermark/artifact?path={urllib.parse.quote(str(path_value))}"


def _external_status(
    status: str,
    message: str,
    *,
    capabilities: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": "sce_locguard",
        "status": status,
        "base_url": _sce_locguard_base_url(),
        "message": message,
    }
    if capabilities is not None:
        payload["capabilities"] = capabilities
    if response is not None:
        payload["response"] = response
    return payload


def _safe_token(value: Any) -> str:
    text = str(value or "")
    return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_"})[:80]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _request_remote_image(*, prompt: str, size: str) -> tuple[Image.Image | None, str | None]:
    api_key = os.environ.get("NARRA_IMAGE_API_KEY", "").strip()
    base_url = os.environ.get("NARRA_IMAGE_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    if not api_key:
        return None, None
    model = _configured_image_generation_model()
    response_format = os.environ.get("NARRA_IMAGE_RESPONSE_FORMAT", "url").strip() or "url"
    timeout = _image_generation_timeout()
    payload: dict[str, Any] = {"prompt": prompt, "size": size}
    if model:
        payload["model"] = model
    if response_format:
        payload["response_format"] = response_format
    request_payload = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/images/generations",
        data=request_payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "CogniGuard/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        image_url = _extract_image_url(payload)
        if image_url:
            image_request = urllib.request.Request(
                image_url,
                method="GET",
                headers={
                    "User-Agent": "CogniGuard/1.0",
                    "Accept": "image/png,image/*;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(image_request, timeout=timeout) as image_response:
                image_bytes = image_response.read()
            return Image.open(io.BytesIO(image_bytes)).convert("RGB"), image_url
        image_bytes = _extract_image_bytes(payload)
        if image_bytes:
            digest = hashlib.sha256(image_bytes).hexdigest()[:16]
            return Image.open(io.BytesIO(image_bytes)).convert("RGB"), f"b64_json:{digest}"
        return None, None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None, None


def _configured_image_generation_model() -> str:
    return (
        os.environ.get("NARRA_IMAGE_MODEL")
        or os.environ.get("OPENAI_IMAGE_MODEL")
        or ""
    ).strip()


def _image_generation_model() -> str:
    return _configured_image_generation_model() or "provider_default"


def _image_generation_timeout() -> float:
    raw_value = os.environ.get("NARRA_IMAGE_TIMEOUT_SECONDS", "120").strip()
    try:
        return max(30.0, float(raw_value))
    except ValueError:
        return 120.0


def _extract_image_url(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return first.get("url")
    if isinstance(payload.get("url"), str):
        return payload["url"]
    return None


def _extract_image_bytes(payload: dict[str, Any]) -> bytes | None:
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and isinstance(first.get("b64_json"), str):
            return base64.b64decode(first["b64_json"])
    if isinstance(payload.get("b64_json"), str):
        return base64.b64decode(payload["b64_json"])
    return None


def _apply_logo_watermark(image: Image.Image, payload: dict[str, Any]) -> Image.Image:
    rgba = image.convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(34)
    digest = _payload_digest(payload)[:10]
    text = f"{SYSTEM_LOGO_TEXT} · {digest}"
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    height = box[3] - box[1]
    x = rgba.width - width - 32
    y = rgba.height - height - 28
    draw.rounded_rectangle(
        (x - 16, y - 12, x + width + 16, y + height + 12),
        radius=16,
        fill=(3, 15, 26, 128),
        outline=(255, 255, 255, 82),
        width=2,
    )
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 190))
    return Image.alpha_composite(rgba, overlay).convert("RGB")


def _apply_hidden_frequency_watermark(image: Image.Image, payload: dict[str, Any]) -> Image.Image:
    rgb = image.convert("RGB")
    arr = np.asarray(rgb).astype(np.float32)
    pattern = _watermark_pattern(rgb.size, payload)
    strength = 3.2
    arr[:, :, 2] = np.clip(arr[:, :, 2] + pattern * strength, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] + pattern * (strength * 0.35), 0, 255)
    return Image.fromarray(arr.astype(np.uint8), mode="RGB")


def _hidden_watermark_confidence(image: Image.Image, payload: dict[str, Any]) -> float:
    resized = image.convert("RGB").resize((1024, 1024))
    arr = np.asarray(resized).astype(np.float32)
    blue = arr[:, :, 2]
    green = arr[:, :, 1]
    signal = blue - green
    signal = signal - signal.mean()
    pattern = _watermark_pattern(resized.size, payload)
    pattern = pattern - pattern.mean()
    denom = float(np.linalg.norm(signal) * np.linalg.norm(pattern))
    if denom <= 1e-6:
        return 0.0
    corr = float(np.sum(signal * pattern) / denom)
    return max(0.0, min(0.99, 0.5 + corr * 8.0))


def _watermark_pattern(size: tuple[int, int], payload: dict[str, Any]) -> np.ndarray:
    width, height = size
    grid = 64
    seed = int(_payload_hmac(payload)[:16], 16) % (2**32)
    rng = np.random.default_rng(seed)
    coarse = rng.choice([-1.0, 1.0], size=(grid, grid)).astype(np.float32)
    pattern_img = Image.fromarray(((coarse + 1.0) * 127.5).astype(np.uint8), mode="L")
    pattern_img = pattern_img.resize((width, height), resample=Image.Resampling.BICUBIC)
    pattern = np.asarray(pattern_img).astype(np.float32) / 127.5 - 1.0
    return pattern


def _detect_visible_logo(image: Image.Image) -> bool:
    cropped = image.convert("RGB").resize((1024, 1024)).crop((620, 900, 1024, 1024))
    arr = np.asarray(cropped).astype(np.float32)
    brightness = arr.mean(axis=2)
    bright_ratio = float((brightness > 180).mean())
    dark_ratio = float((brightness < 50).mean())
    return bright_ratio > 0.015 and dark_ratio > 0.08


def _candidate_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("image_id"):
        return [payload]
    candidates: list[dict[str, Any]] = []
    for path in sorted(OUTPUT_DIR.glob("*.json"))[-80:]:
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("resource_id") and payload.get("resource_id") != candidate.get("resource_id"):
            continue
        candidates.append(candidate)
    if not candidates:
        candidates.append({"image_id": "unknown", "resource_id": payload.get("resource_id", "")})
    return candidates


def _placeholder_teaching_image(prompt: str, *, index: int) -> Image.Image:
    image = Image.new("RGB", (1024, 1024), (246, 250, 252))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1024, 150), fill=(12, 74, 110))
    draw.text((54, 42), _diagram_title(prompt), font=_font(44), fill=(255, 255, 255))
    draw.text((56, 102), "visual teaching diagram", font=_font(24), fill=(207, 250, 254))
    topic = prompt.lower()
    if "fraction" in topic or "area model" in topic or "分数" in prompt or "面积模型" in prompt:
        _draw_fraction_area_model(draw)
    elif "quadratic" in topic or "parabola" in topic or "二次" in prompt or "抛物线" in prompt or "顶点式" in prompt:
        _draw_quadratic_vertex_model(draw)
    elif "probability" in topic or "tree" in topic or "概率" in prompt or "树状图" in prompt:
        _draw_probability_tree(draw)
    elif "triangle" in topic or "geometry" in topic or "congruence" in topic or "三角" in prompt or "几何" in prompt:
        _draw_triangle_congruence(draw)
    elif "linear" in topic or "function" in topic or "slope" in topic or "一次" in prompt or "函数" in prompt or "坐标" in prompt:
        _draw_linear_function(draw)
    else:
        _draw_equation_steps(draw)
    return image


def _diagram_title(prompt: str) -> str:
    lowered = prompt.lower()
    if "fraction" in lowered or "area model" in lowered or "分数" in prompt or "面积模型" in prompt:
        return "Fraction multiplication area model"
    if "quadratic" in lowered or "parabola" in lowered or "二次" in prompt or "抛物线" in prompt or "顶点式" in prompt:
        return "Quadratic vertex form"
    if "probability" in lowered or "tree" in lowered or "概率" in prompt:
        return "Probability tree diagram"
    if "triangle" in lowered or "congruence" in lowered or "三角" in prompt or "几何" in prompt:
        return "Triangle congruence proof"
    if "linear" in lowered or "function" in lowered or "一次" in prompt or "函数" in prompt or "坐标" in prompt:
        return "Linear function graph"
    return "Equation visual explanation"


def _draw_fraction_area_model(draw: ImageDraw.ImageDraw) -> None:
    draw.text((70, 190), "Example: 1/2 x 2/3", font=_font(42), fill=(15, 23, 42))
    x0, y0, w, h = 150, 300, 620, 360
    draw.rectangle((x0, y0, x0 + w, y0 + h), outline=(15, 118, 110), width=5)
    for i in range(1, 3):
        x = x0 + w * i / 3
        draw.line((x, y0, x, y0 + h), fill=(14, 116, 144), width=3)
    draw.line((x0, y0 + h / 2, x0 + w, y0 + h / 2), fill=(14, 116, 144), width=3)
    draw.rectangle((x0, y0, x0 + w, y0 + h / 2), fill=(191, 230, 248))
    draw.rectangle((x0, y0, x0 + w * 2 / 3, y0 + h), fill=(181, 240, 232))
    draw.rectangle((x0, y0, x0 + w * 2 / 3, y0 + h / 2), fill=(94, 234, 212))
    draw.text((800, 335), "overlap", font=_font(28), fill=(15, 118, 110))
    draw.line((770, 380, x0 + 250, y0 + 100), fill=(15, 118, 110), width=4)
    draw.text((165, 705), "2 shaded parts out of 6 -> 2/6 = 1/3", font=_font(34), fill=(15, 23, 42))
    draw.text((165, 760), "Keep the same whole rectangle.", font=_font(26), fill=(100, 116, 139))


def _draw_linear_function(draw: ImageDraw.ImageDraw) -> None:
    _draw_axes(draw)
    origin = (250, 720)
    scale = 80
    points = []
    for x in range(-2, 6):
        px = origin[0] + x * scale
        py = origin[1] - (0.7 * x + 1.2) * scale
        points.append((px, py))
    draw.line(points, fill=(14, 116, 144), width=6)
    draw.ellipse((origin[0] - 8, origin[1] - 1.2 * scale - 8, origin[0] + 8, origin[1] - 1.2 * scale + 8), fill=(20, 184, 166))
    draw.text((640, 220), "y = kx + b", font=_font(46), fill=(15, 23, 42))
    draw.text((640, 300), "k: slope", font=_font(30), fill=(14, 116, 144))
    draw.text((640, 350), "b: y-intercept", font=_font(30), fill=(14, 116, 144))
    draw.text((295, 595), "b", font=_font(28), fill=(15, 118, 110))
    draw.line((520, 430, 610, 350), fill=(20, 184, 166), width=4)


def _draw_quadratic_vertex_model(draw: ImageDraw.ImageDraw) -> None:
    _draw_axes(draw)
    origin = (260, 720)
    pts = []
    for i in range(-160, 240, 8):
        x = i / 80
        y = 0.55 * (x - 1.2) ** 2 + 0.7
        pts.append((origin[0] + i, origin[1] - y * 85))
    draw.line(pts, fill=(14, 116, 144), width=6)
    vx, vy = origin[0] + int(1.2 * 80), origin[1] - int(0.7 * 85)
    draw.ellipse((vx - 10, vy - 10, vx + 10, vy + 10), fill=(20, 184, 166))
    draw.line((vx, 250, vx, 780), fill=(148, 163, 184), width=3)
    draw.text((600, 220), "y = a(x - h)^2 + k", font=_font(42), fill=(15, 23, 42))
    draw.text((600, 300), "vertex = (h, k)", font=_font(32), fill=(15, 118, 110))
    draw.text((600, 355), "axis: x = h", font=_font(30), fill=(14, 116, 144))
    draw.text((vx + 20, vy + 12), "(h,k)", font=_font(26), fill=(15, 118, 110))


def _draw_probability_tree(draw: ImageDraw.ImageDraw) -> None:
    draw.text((70, 190), "Two-step event: multiply along each path", font=_font(34), fill=(15, 23, 42))
    root = (140, 470)
    level1 = [(410, 340), (410, 600)]
    level2 = [(720, 270), (720, 410), (720, 540), (720, 680)]
    labels = ["A  P(A)", "B  P(B)", "C  P(C|A)", "D  P(D|A)", "C  P(C|B)", "D  P(D|B)"]
    for p in level1:
        draw.line((root, p), fill=(14, 116, 144), width=5)
    for src, dst in [(level1[0], level2[0]), (level1[0], level2[1]), (level1[1], level2[2]), (level1[1], level2[3])]:
        draw.line((src, dst), fill=(14, 116, 144), width=5)
    for point in [root, *level1, *level2]:
        draw.ellipse((point[0] - 16, point[1] - 16, point[0] + 16, point[1] + 16), fill=(20, 184, 166))
    draw.text((235, 330), labels[0], font=_font(24), fill=(15, 23, 42))
    draw.text((235, 585), labels[1], font=_font(24), fill=(15, 23, 42))
    for text, point in zip(labels[2:], level2):
        draw.text((point[0] + 28, point[1] - 18), text, font=_font(22), fill=(15, 23, 42))
    draw.text((160, 770), "Path probability: P(A and C) = P(A) x P(C|A)", font=_font(30), fill=(15, 118, 110))


def _draw_triangle_congruence(draw: ImageDraw.ImageDraw) -> None:
    tri1 = [(160, 650), (330, 320), (520, 650)]
    tri2 = [(600, 650), (760, 320), (930, 650)]
    draw.polygon(tri1, outline=(14, 116, 144), fill=(219, 234, 254))
    draw.line((tri1[0], tri1[1], tri1[2], tri1[0]), fill=(14, 116, 144), width=5)
    draw.polygon(tri2, outline=(15, 118, 110), fill=(204, 251, 241))
    draw.line((tri2[0], tri2[1], tri2[2], tri2[0]), fill=(15, 118, 110), width=5)
    for label, point in zip(["A", "B", "C"], tri1):
        draw.text((point[0] - 20, point[1] + 10), label, font=_font(30), fill=(15, 23, 42))
    for label, point in zip(["D", "E", "F"], tri2):
        draw.text((point[0] - 20, point[1] + 10), label, font=_font(30), fill=(15, 23, 42))
    draw.text((130, 220), "SAS proof chain", font=_font(42), fill=(15, 23, 42))
    draw.text((130, 760), "AB = DE, AC = DF, included angle equal -> triangles congruent", font=_font(27), fill=(15, 118, 110))


def _draw_equation_steps(draw: ImageDraw.ImageDraw) -> None:
    draw.text((90, 220), "Equation balance model", font=_font(42), fill=(15, 23, 42))
    steps = ["2x + 3 = 7", "2x = 4", "x = 2"]
    y = 360
    for idx, step in enumerate(steps):
        draw.rounded_rectangle((160, y, 860, y + 90), radius=18, outline=(14, 116, 144), width=4)
        draw.text((210, y + 22), step, font=_font(40), fill=(15, 23, 42))
        if idx < len(steps) - 1:
            draw.text((475, y + 105), "↓ same operation both sides", font=_font(24), fill=(15, 118, 110))
        y += 170


def _draw_axes(draw: ImageDraw.ImageDraw) -> None:
    origin = (260, 720)
    draw.line((100, origin[1], 560, origin[1]), fill=(15, 23, 42), width=4)
    draw.line((origin[0], 230, origin[0], 810), fill=(15, 23, 42), width=4)
    draw.polygon([(560, origin[1]), (540, origin[1] - 10), (540, origin[1] + 10)], fill=(15, 23, 42))
    draw.polygon([(origin[0], 230), (origin[0] - 10, 250), (origin[0] + 10, 250)], fill=(15, 23, 42))
    draw.text((565, origin[1] - 10), "x", font=_font(26), fill=(15, 23, 42))
    draw.text((origin[0] + 12, 220), "y", font=_font(26), fill=(15, 23, 42))


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _image_id(answer_id: str, resource_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{answer_id}|{resource_id}|{index}".encode("utf-8")).hexdigest()
    return f"cg_img_{digest[:16]}"


def _payload_digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _payload_hmac(payload: dict[str, Any]) -> str:
    return hmac.new(IMAGE_WATERMARK_SECRET, _payload_digest(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_local_env() -> None:
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
