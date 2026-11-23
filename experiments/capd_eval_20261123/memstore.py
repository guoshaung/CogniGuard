"""In-memory disclosure log for the evaluation harness.

The method set matches DisclosureStore. A large simulation can run without a
MySQL server. Receipt ids are still random, so comparisons use the query views.
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager
from threading import Lock

from cogniguard.governance.disclosure import DisclosureReceipt
from cogniguard.runtime.disclosure_store import ReleaseBusy


class MemoryDisclosureStore:
    """Process-local receipt log. Reserved and delivered rows count as held."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._section = Lock()
        self._rows: dict[str, dict] = {}
        self._closed = False

    def reserve(
        self,
        *,
        resource_id: str,
        unit_id: str,
        recipient_principal_id: str,
        acting_org_id: str,
        agent_principal_id: str,
        session_id: str,
        policy_version: int,
        content: str | bytes,
        created_at: float,
        exposure_delta: float = 0.0,
    ) -> str:
        payload = content.encode() if isinstance(content, str) else content
        receipt_id = uuid.uuid4().hex
        row = {
            "receipt_id": receipt_id,
            "resource_id": resource_id,
            "unit_id": unit_id,
            "recipient_principal_id": recipient_principal_id,
            "acting_org_id": acting_org_id,
            "agent_principal_id": agent_principal_id,
            "session_id": session_id,
            "policy_version": int(policy_version),
            "status": "reserved",
            "content_sha256": hashlib.sha256(payload).hexdigest(),
            "created_at": float(created_at),
            "exposure_delta": float(exposure_delta),
        }
        with self._lock:
            self._check_open()
            self._rows[receipt_id] = row
        return receipt_id

    def commit(self, receipt_id: str) -> None:
        self._transition(receipt_id, "delivered")

    def cancel(self, receipt_id: str) -> None:
        self._transition(receipt_id, "cancelled")

    def history(self, recipient_principal_id: str) -> list[DisclosureReceipt]:
        with self._lock:
            self._check_open()
            rows = [
                row
                for row in self._rows.values()
                if row["recipient_principal_id"] == recipient_principal_id
                and row["status"] == "delivered"
            ]
        rows.sort(key=lambda row: (row["created_at"], row["receipt_id"]))
        return [_receipt(row) for row in rows]

    def coalition_units(self, recipient_ids: list[str]) -> frozenset[tuple[str, str]]:
        wanted = set(recipient_ids)
        if not wanted:
            return frozenset()
        with self._lock:
            self._check_open()
            return frozenset(
                (row["resource_id"], row["unit_id"])
                for row in self._rows.values()
                if row["status"] == "delivered" and row["recipient_principal_id"] in wanted
            )

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset[tuple[str, str]]]:
        if not units:
            return {}
        with self._lock:
            self._check_open()
            held: dict[str, set[tuple[str, str]]] = {}
            for row in self._rows.values():
                pair = (row["resource_id"], row["unit_id"])
                if row["status"] not in {"reserved", "delivered"} or pair not in units:
                    continue
                held.setdefault(row["recipient_principal_id"], set()).add(pair)
        return {name: frozenset(pairs) for name, pairs in held.items()}

    def exposure_by_recipient(self, resource_id: str, unit_id: str) -> dict[str, float]:
        with self._lock:
            self._check_open()
            totals: dict[str, float] = {}
            for row in self._rows.values():
                if row["status"] != "delivered":
                    continue
                if row["resource_id"] != resource_id or row["unit_id"] != unit_id:
                    continue
                name = row["recipient_principal_id"]
                totals[name] = totals.get(name, 0.0) + row["exposure_delta"]
        return totals

    def coalition_exposure(
        self, resource_id: str, unit_id: str, recipient_ids: list[str]
    ) -> float:
        wanted = set(recipient_ids)
        if not wanted:
            return 0.0
        with self._lock:
            self._check_open()
            total = 0.0
            for row in self._rows.values():
                if row["status"] != "delivered":
                    continue
                if row["resource_id"] != resource_id or row["unit_id"] != unit_id:
                    continue
                if row["recipient_principal_id"] not in wanted:
                    continue
                total += row["exposure_delta"]
        return total

    @contextmanager
    def release_section(self, timeout: float = 10.0):
        """Exclude other release sections in this process. The data lock stays free."""
        if not self._section.acquire(timeout=timeout):
            raise ReleaseBusy("cogniguard_release_memory")
        try:
            yield
        finally:
            self._section.release()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _transition(self, receipt_id: str, status: str) -> None:
        with self._lock:
            self._check_open()
            row = self._rows.get(receipt_id)
            if row is None or row["status"] != "reserved":
                raise ValueError(receipt_id)
            row["status"] = status

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("disclosure store is closed")


def _receipt(row: dict) -> DisclosureReceipt:
    return DisclosureReceipt(
        receipt_id=row["receipt_id"],
        resource_id=row["resource_id"],
        unit_id=row["unit_id"],
        recipient_principal_id=row["recipient_principal_id"],
        acting_org_id=row["acting_org_id"],
        agent_principal_id=row["agent_principal_id"],
        session_id=row["session_id"],
        policy_version=row["policy_version"],
        status=row["status"],
        content_sha256=row["content_sha256"],
        created_at=row["created_at"],
        exposure_delta=row["exposure_delta"],
    )
