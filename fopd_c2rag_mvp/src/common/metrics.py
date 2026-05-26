from __future__ import annotations

from statistics import mean
from typing import Any


def avg(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def summarize_metric_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"num_requests": len(rows)}
    numeric_keys: set[str] = set()
    for row in rows:
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric_keys.add(key)
    for key in sorted(numeric_keys):
        out[f"avg_{key}"] = avg([float(r[key]) for r in rows if isinstance(r.get(key), (int, float))])
    return out
