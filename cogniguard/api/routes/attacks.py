"""Attack result and simulation HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..demo_data import ATTACK_TEST_CASES
from ..dependencies import build_attack_results
from ..routing import ApiRequest, Route
from ..services.attacks import (
    load_attack_evaluation,
    load_c2rag_attacks,
    record_attack,
    record_attack_batch,
)

if TYPE_CHECKING:
    from ..http_server import CogniGuardDashboardAPIHandler


def attack_results(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_api_payload(build_attack_results, attack_cases=ATTACK_TEST_CASES)


def attack_evaluation(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(load_attack_evaluation())


def c2rag_attacks(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(load_c2rag_attacks())


def attack_cases(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(ATTACK_TEST_CASES)


def run_attack(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(record_attack(handler._read_json()))


def run_batch(handler: CogniGuardDashboardAPIHandler, request: ApiRequest) -> None:
    handler._send_json(record_attack_batch())


ROUTES = (
    Route("GET", "/api/attacks/results", attack_results),
    Route("GET", "/api/attack-eval-results", attack_evaluation),
    Route("GET", "/api/c2rag-attacks", c2rag_attacks),
    Route("GET", "/api/attack-cases", attack_cases),
    Route("POST", "/api/run-attack", run_attack),
    Route("POST", "/api/attacks/run-batch", run_batch),
)
