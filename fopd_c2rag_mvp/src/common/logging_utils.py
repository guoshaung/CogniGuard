from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stage_log(stage: str, message: str) -> str:
    return f"[{stage}] {message}"
