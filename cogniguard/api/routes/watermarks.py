"""Watermarks HTTP endpoints. Business flows stay in their existing services."""

from __future__ import annotations

import hashlib
import shutil
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

from cogniguard.runtime.protection_context import authorize_image_generation, transport_credentials
from cogniguard.runtime.sessions import InvalidSessionToken
from core.paths import OUTPUTS_DIR, resolve_project_path

from ..dependencies import (
    PROJECT_ROOT,
    attack_image_watermark,
    build_audit_traces,
    decode_data_url_or_base64,
    detect_image_watermark,
    image_file_response,
    watermark_artifact_response,
)
from ..routing import ApiRequest, Route
from ..services.watermarks import (
    demo_watermark_rounds,
    detect_semantic_watermark,
    get_watermark_rounds,
    register_watermark_session,
    simulate_text_attacks,
)

if TYPE_CHECKING:
    from ..http_server import CogniGuardDashboardAPIHandler


def _owner_session(requested_id: str = ""):
    from cogniguard.runtime.gateway import get_gateway

    token, _ = transport_credentials()
    if not token:
        raise InvalidSessionToken("A session credential is required")
    session = get_gateway().store.get_or_create(token)
    if requested_id and requested_id != session.session_id:
        raise PermissionError("The requested data belongs to another session")
    return session


def _restore_final_deliveries(session) -> None:
    from cogniguard.api.services.watermarks import RECENT_WATERMARK_SESSIONS
    from cogniguard.runtime.gateway import get_gateway

    deliveries = session.load_state().get("final_deliveries") or []
    if not deliveries:
        return
    # Durable server state is the source of truth; never reuse a stale process
    # success flag after a restart or after a receipt fails authentication.
    RECENT_WATERMARK_SESSIONS.pop(session.session_id, None)
    for delivery in deliveries:
        if not isinstance(delivery, dict) or delivery.get("session_id") != session.session_id:
            continue
        record = delivery.get("text_watermark")
        if not isinstance(record, dict):
            continue
        verification = get_gateway().provenance.verify(record.get("text"), record)
        if not verification.get("valid"):
            continue
        restored = {
            **delivery,
            "protection": {
                **(delivery.get("protection") or {}),
                "watermark_verification": verification,
            },
        }
        register_watermark_session(restored)


def _artifact_identity(url: str):
    parsed = urllib.parse.urlsplit(str(url))
    if parsed.scheme or parsed.netloc:
        return None
    if parsed.path.startswith("/api/teaching-images/"):
        filename = urllib.parse.unquote(parsed.path.removeprefix("/api/teaching-images/"))
        if not filename or Path(filename).name != filename or any(c in filename for c in "/\\"):
            return None
        return ("image", filename)
    if parsed.path == "/api/watermark/artifact":
        value = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
        if not value:
            return None
        path = resolve_project_path(urllib.parse.unquote(value)).resolve()
        if not path.is_relative_to(OUTPUTS_DIR.resolve()):
            return None
        return ("artifact", str(path))
    return None


def _authorize_artifact(url: str) -> None:
    session = _owner_session()
    requested = _artifact_identity(url)
    allowed = session.load_state().get("authorized_artifact_urls") or []
    if requested is None or requested not in {
        _artifact_identity(item) for item in allowed if isinstance(item, str)
    }:
        raise PermissionError("The artifact was not generated for this session")


def _register_attack_artifacts(frame, result: dict) -> None:
    """Snapshot actual tool outputs into owner-specific paths, then authorize them."""
    root = OUTPUTS_DIR.resolve()
    request_hash = hashlib.sha256(frame.request_id.encode()).hexdigest()[:24]
    destination = root / "delivery_artifacts" / frame.session.session_id / request_hash
    if not destination.resolve().is_relative_to(root):
        raise PermissionError("Invalid artifact owner directory")
    allowed = set(frame.state.get("authorized_artifact_urls") or [])
    for path_key, url_key in (
        ("source_image_path", "source_image_url"),
        ("attacked_image_path", "attacked_image_url"),
        ("mask_path", "mask_url"),
        ("overlay_path", "overlay_url"),
    ):
        raw = result.get(path_key)
        if not raw:
            continue
        path = resolve_project_path(str(raw)).resolve()
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".webp"}
        ):
            result.pop(path_key, None)
            result.pop(url_key, None)
            continue
        destination.mkdir(parents=True, exist_ok=True)
        owned_path = destination / path.name
        if path != owned_path:
            shutil.copyfile(path, owned_path)
        url = "/api/watermark/artifact?" + urllib.parse.urlencode({"path": str(owned_path)})
        result[path_key], result[url_key] = str(owned_path), url
        allowed.add(url)
    frame.state["authorized_artifact_urls"] = sorted(allowed)


def audit_traces(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    case_index = request.case_index
    handler._send_api_payload(build_audit_traces, PROJECT_ROOT, case_index)


def watermark_rounds(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    if request.query.get("scope", [""])[0] == "demo":
        handler._send_json(demo_watermark_rounds())
        return
    session = _owner_session(request.query.get("session_id", [""])[0])
    _restore_final_deliveries(session)
    result = get_watermark_rounds(session.session_id)
    if result.get("data_source") != "final-delivery":
        result = {"session_id": session.session_id, "data_source": "final-delivery", "rounds": []}
    handler._send_json(result)


def teaching_image(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    path = request.path
    filename = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    _authorize_artifact("/api/teaching-images/" + urllib.parse.quote(filename))
    if image_file_response is None:
        handler._send_json({"error": "image service is not importable"}, status=500)
        return
    payload = image_file_response(filename)
    if payload is None:
        handler._send_json({"error": "image not found"}, status=404)
        return
    image_bytes, mime = payload
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler._set_cors_headers()
    handler.end_headers()
    handler.wfile.write(image_bytes)


def watermark_artifact(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    query = request.query
    artifact_path = query.get("path", [""])[0]
    _authorize_artifact(
        "/api/watermark/artifact?" + urllib.parse.urlencode({"path": artifact_path})
    )
    if watermark_artifact_response is None:
        handler._send_json({"error": "watermark artifact service is not importable"}, status=500)
        return
    payload = watermark_artifact_response(artifact_path)
    if payload is None:
        handler._send_json({"error": "artifact not found"}, status=404)
        return
    image_bytes, mime = payload
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler._set_cors_headers()
    handler.end_headers()
    handler.wfile.write(image_bytes)


def detect_semantic(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    if payload.get("scope") != "demo":
        session = _owner_session(str(payload.get("session_id") or ""))
        _restore_final_deliveries(session)
        payload["session_id"] = session.session_id
        if get_watermark_rounds(session.session_id).get("data_source") != "final-delivery":
            handler._send_json(
                {
                    "success": True,
                    "watermark_detected": False,
                    "watermark_verified": False,
                    "provenance_valid": False,
                    "reasons": ["no_final_delivery_in_session"],
                }
            )
            return
    handler._send_json(detect_semantic_watermark(payload))


def detect_image(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    if detect_image_watermark is None or decode_data_url_or_base64 is None:
        raise RuntimeError("image watermark detector is not importable")
    image_data = str(payload.get("image_data", "") or "")
    if not image_data:
        raise ValueError("image_data is required")
    image_bytes = decode_data_url_or_base64(image_data)
    candidate = {
        "image_id": payload.get("image_id") or "",
        "resource_id": payload.get("resource_id") or "",
    }
    handler._send_json(detect_image_watermark(image_bytes, candidate))


def attack_image(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    from cogniguard.runtime.gateway import get_gateway

    if attack_image_watermark is None or decode_data_url_or_base64 is None:
        raise RuntimeError("image watermark attacker is not importable")
    image_data = str(payload.get("image_data", "") or "")
    if not image_data:
        raise ValueError("image_data is required")
    image_bytes = decode_data_url_or_base64(image_data)
    attack_type = str(payload.get("attack_type") or "inpainting")
    if attack_type not in {"object_removal", "inpainting", "local_replacement", "local_style_edit"}:
        raise ValueError("Unsupported image attack type")
    prompt = str(payload.get("prompt") or "")

    def operation(frame):
        authorize_image_generation(1)
        result = attack_image_watermark(image_bytes, attack_type=attack_type, prompt=prompt)
        _register_attack_artifacts(frame, result)
        return result

    result = get_gateway().run(
        "image_attack",
        {
            "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "attack_type": attack_type,
            "message": prompt,
        },
        operation,
    )
    register_watermark_session(result)
    handler._send_json(result)


def attack_text(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(simulate_text_attacks(handler._read_json()))


ROUTES = (
    Route("GET", "/api/audit/traces", audit_traces),
    Route("GET", "/api/watermark/rounds", watermark_rounds),
    Route("GET", "/api/teaching-images/", teaching_image, prefix=True),
    Route("GET", "/api/watermark/artifact", watermark_artifact),
    Route("POST", "/api/watermark/detect", detect_semantic),
    Route("POST", "/api/watermark/image-detect", detect_image),
    Route("POST", "/api/watermark/image-attack", attack_image),
    Route("POST", "/api/watermark-attack", attack_text),
)
