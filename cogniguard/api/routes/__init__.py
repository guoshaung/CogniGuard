"""The single composition point for all active HTTP endpoints."""

from ..routing import Router
from . import (
    attacks,
    cases,
    dashboard,
    demo_identity,
    dialogue,
    profile_consent_demo,
    scenarios,
    watermarks,
)


def create_router() -> Router:
    router = Router()
    for module in (dashboard, dialogue, cases, scenarios, attacks, watermarks, profile_consent_demo, demo_identity):
        for route in module.ROUTES:
            router.register(route)
    return router
