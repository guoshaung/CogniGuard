"""Scenarios HTTP endpoints. Business flows stay in their existing services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..dependencies import list_attack_templates, list_episode_samples
from ..routing import ApiRequest, Route

if TYPE_CHECKING:
    from ..http_server import CogniGuardDashboardAPIHandler


def episodes(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    try:
        rows = list_episode_samples() if list_episode_samples is not None else []
        handler._send_json({"rows": rows, "preferred_layout": "scenario_layers"})
    except Exception as exc:
        handler._send_json({"error": str(exc)}, status=500)


def attack_templates(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    try:
        rows = list_attack_templates() if list_attack_templates is not None else []
        handler._send_json({"rows": rows})
    except Exception as exc:
        handler._send_json({"error": str(exc)}, status=500)


ROUTES = (
    Route("GET", "/api/scenario/episodes", episodes),
    Route("GET", "/api/scenario/attack-templates", attack_templates),
)
