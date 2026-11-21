"""Dialogue HTTP endpoints. Business flows stay in their existing services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..dependencies import PROJECT_ROOT, run_classroom_turn, run_free_chat
from ..routing import ApiRequest, Route
from ..services.watermarks import register_watermark_session

if TYPE_CHECKING:
    from ..http_server import CogniGuardDashboardAPIHandler


def free_chat(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    if run_free_chat is None:
        raise RuntimeError("free chat engine is not importable")
    result = run_free_chat(
        message=str(payload.get("message", "")),
        history=list(payload.get("history") or []),
        existing_image_count=int(payload.get("teaching_image_count", 0) or 0),
    )
    register_watermark_session(result)
    handler._send_json(result, status=200 if result.get("success") else 503)


def next_round(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    if run_classroom_turn is None:
        raise RuntimeError("classroom session engine is not importable")
    result = run_classroom_turn(
        data_root=PROJECT_ROOT / "data",
        case_index=int(payload.get("case_index", 0)),
        turn_kind=str(payload.get("turn_kind", "learning")),
        round_number=int(payload.get("round_number", 1)),
        student_message=str(payload.get("student_message", "")),
        attack_type=payload.get("attack_type"),
        attack_prompt=str(payload.get("attack_prompt", "")),
        session_state=payload.get("session_state"),
        target_mastery=float(payload.get("target_mastery", 0.85)),
        episode_id=payload.get("episode_id"),
        cg_ablation=payload.get("cg_ablation"),
        dialogue_mode=payload.get("dialogue_mode"),
    )
    register_watermark_session(result)
    handler._send_json(result)


ROUTES = (
    Route("POST", "/api/dialogue/free-chat", free_chat),
    Route("POST", "/api/dialogue/next-round", next_round),
)
