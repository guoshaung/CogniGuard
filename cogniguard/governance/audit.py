from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AuditLedger:
    records: list[dict[str, Any]] = field(default_factory=list)

    @property
    def head(self) -> str:
        return str(self.records[-1]["record_hash"]) if self.records else "GENESIS"

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = {"previous_hash": self.head, **payload}
        record = {**body, "record_hash": _hash(body)}
        self.records.append(record)
        return record

    def verify(self) -> bool:
        previous = "GENESIS"
        for record in self.records:
            body = {key: value for key, value in record.items() if key != "record_hash"}
            if body.get("previous_hash") != previous or _hash(body) != record.get("record_hash"):
                return False
            previous = str(record["record_hash"])
        return True
