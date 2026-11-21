"""Case manifests and a shared case execution service for all transports."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .. import dependencies
from ..demo_data import FALLBACK_CASES
from ..routing import ApiRequest, Route
from ..services.case_execution import execute_case, parse_bool

if TYPE_CHECKING:
    from ..http_server import CogniGuardDashboardAPIHandler


def list_cases(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    manifest = dependencies.build_cases_manifest
    handler._send_json(manifest() if manifest is not None else {"rows": FALLBACK_CASES})


def run_case_get(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    query = request.query
    handler._send_json(
        execute_case(
            request.case_index,
            episode_id=query.get("episode_id", [None])[0],
            runtime_mode=query.get("runtime_mode", ["guarded_llm"])[0],
            enable_nemo=parse_bool(query.get("enable_nemo", ["true"])[0]),
        )
    )


def run_case_post(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    handler._send_json(
        execute_case(
            int(payload.get("case_index", 0)),
            episode_id=payload.get("episode_id"),
            runtime_mode=str(payload.get("runtime_mode", "guarded_llm")),
            enable_nemo=parse_bool(payload.get("enable_nemo", True)),
        )
    )


def run_case_stream(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    payload = handler._read_json()
    case_index = int(payload.get("case_index", 0))
    runtime_mode = str(payload.get("runtime_mode", "guarded_llm"))
    enable_nemo = parse_bool(payload.get("enable_nemo", True))
    # Validate and bind before opening a 200 stream or forwarding any event.
    # Session failures can therefore still return a meaningful JSON status.
    result = execute_case(
        case_index,
        episode_id=payload.get("episode_id"),
        runtime_mode=runtime_mode,
        enable_nemo=enable_nemo,
        event_sink=None,
    )
    if "error" in result:
        handler._send_json({"success": False, "error": "Case execution failed"}, status=503)
        return
    handler._prepare_stream_response()
    handler._send_ndjson_event(
        {
            "type": "stream_opened",
            "case_index": case_index,
            "session_id": result.get("session_id"),
            "request_id": (result.get("protection") or {}).get("request_id"),
            "timestamp": datetime.now().isoformat(),
        }
    )
    handler._send_ndjson_event(
        {
            "type": "run_started",
            "round_id": result.get("round_id"),
            "delivery_validated": True,
            "timestamp": datetime.now().isoformat(),
        }
    )
    # Compatibility progress events are projections of already validated output;
    # prompt bodies, model deltas and unreviewed diagnostic text are never sent.
    metadata_fields = (
        "step_id",
        "step_name",
        "layer",
        "cg_decision",
        "nemo_decision",
        "risk_score",
        "timestamp",
    )
    for step in result.get("workflow_steps", []):
        if isinstance(step, dict):
            handler._send_ndjson_event(
                {
                    "type": "workflow_step",
                    "step": {key: step[key] for key in metadata_fields if key in step},
                    "delivery_validated": True,
                }
            )
    handler._send_ndjson_event(
        {
            "type": "run_completed",
            "round_id": result.get("round_id"),
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
    )


ROUTES = (
    Route("GET", "/api/cases", list_cases),
    Route("GET", "/api/run-case", run_case_get),
    Route("POST", "/api/run-case", run_case_post),
    Route("POST", "/api/run-case/stream", run_case_stream),
)
