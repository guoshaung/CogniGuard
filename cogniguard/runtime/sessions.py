"""Server-owned anonymous sessions, durable budgets and request replay records.

Tokens convey possession of an anonymous session; they do not authenticate a
person. Only trusted server code may call state and budget mutation methods.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import sqlite3
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

from core.paths import RUNTIME_DIR

_SCALE = 1_000_000_000
_DEFAULT_LIMITS = {"images": 2, "requests": 1000, "privacy": 1, "copyright": 1}
_PROCESS_LOCKS: dict[tuple[str, str], threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()
_LOCAL = threading.local()


class SessionError(RuntimeError):
    """A session request cannot proceed."""


class InvalidSessionToken(SessionError):
    pass


class RequestConflict(SessionError):
    pass


class BudgetExceeded(SessionError):
    pass


class SessionBusy(SessionError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _units(value: int | float, *, limit: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Budget values must be finite non-negative numbers")
    if not math.isfinite(value) or value < 0:
        raise ValueError("Budget values must be finite non-negative numbers")
    rounding = ROUND_FLOOR if limit else ROUND_CEILING
    units = int((Decimal(str(value)) * _SCALE).to_integral_value(rounding=rounding))
    if units > 2**62:
        raise ValueError("Budget value is too large")
    return units


def _request_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError("A non-empty request_id of at most 200 characters is required")
    return value


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    budget: str
    amount: float
    request_id: str
    status: str
    _session: Session = field(repr=False, compare=False)

    def commit(self) -> None:
        self._session.commit(self)

    def release(self, *, no_side_effects: bool = False) -> None:
        self._session.release(self, no_side_effects=no_side_effects)


@dataclass
class RequestRecord:
    request_id: str
    cached: bool
    result: Any = None
    _session: Session = field(repr=False, compare=False, default=None)
    _finished: bool = field(default=False, repr=False)

    def complete(self, result: Any) -> None:
        if self.cached:
            raise RequestConflict("A cached request cannot execute again")
        self._session.complete_request(self.request_id, result)
        self.result = result
        self._finished = True


class SessionStore:
    """SQLite-backed state with short, atomic budget and replay transactions."""

    def __init__(
        self,
        path: str | Path = RUNTIME_DIR / "sessions.sqlite3",
        *,
        limits: Mapping[str, int | float] | None = None,
        lock_timeout: float = 60,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_dir = self.path.with_name(self.path.name + ".locks")
        self.lock_timeout = float(lock_timeout)
        configured = {**_DEFAULT_LIMITS, **(limits or {})}
        self.limits = {name: _units(value, limit=True) for name, value in configured.items()}
        if not all(isinstance(name, str) and name for name in self.limits):
            raise ValueError("Budget names must be non-empty strings")
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS budgets (
                    session_id TEXT NOT NULL, budget TEXT NOT NULL, limit_units INTEGER NOT NULL,
                    PRIMARY KEY (session_id, budget)
                );
                CREATE TABLE IF NOT EXISTS requests (
                    session_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, status TEXT NOT NULL,
                    result_json TEXT, PRIMARY KEY (session_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS reservations (
                    reservation_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                    request_id TEXT NOT NULL, budget TEXT NOT NULL, item_key TEXT NOT NULL,
                    amount_units INTEGER NOT NULL, status TEXT NOT NULL,
                    UNIQUE (session_id, request_id, budget, item_key)
                );
                CREATE INDEX IF NOT EXISTS reservation_budget
                ON reservations (session_id, budget, status);
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=self.lock_timeout, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    def get_or_create(self, token: str | None = None) -> Session:
        if token is not None:
            if not isinstance(token, str) or not token or len(token) > 1024:
                raise InvalidSessionToken("Invalid anonymous session token")
            digest = hashlib.sha256(token.encode()).hexdigest()
            with self._connect() as db:
                row = db.execute(
                    "SELECT session_id FROM sessions WHERE token_hash=?", (digest,)
                ).fetchone()
            if row is None:
                raise InvalidSessionToken("Invalid anonymous session token")
            return Session(row["session_id"], token, self)
        token = secrets.token_urlsafe(32)
        session_id = secrets.token_hex(16)
        with self._write() as db:
            db.execute(
                "INSERT INTO sessions(session_id,token_hash) VALUES (?,?)",
                (session_id, hashlib.sha256(token.encode()).hexdigest()),
            )
            db.executemany(
                "INSERT INTO budgets(session_id,budget,limit_units) VALUES (?,?,?)",
                [(session_id, name, value) for name, value in self.limits.items()],
            )
        return Session(session_id, token, self)


@dataclass(frozen=True)
class Session:
    session_id: str
    token: str = field(repr=False)
    _store: SessionStore = field(repr=False, compare=False)

    @property
    def _lock_key(self) -> tuple[str, str]:
        return str(self._store.path), self.session_id

    @contextmanager
    def lock(self) -> Iterator[Session]:
        """Serialize this session across threads/processes; nesting is supported."""
        with _PROCESS_LOCKS_GUARD:
            lock = _PROCESS_LOCKS.setdefault(self._lock_key, threading.RLock())
        if not lock.acquire(timeout=self._store.lock_timeout):
            raise SessionBusy("Anonymous session is busy")
        locks = getattr(_LOCAL, "locks", None)
        if locks is None:
            locks = _LOCAL.locks = {}
        nested = self._lock_key in locks
        handle = None
        try:
            if not nested:
                self._store.lock_dir.mkdir(parents=True, exist_ok=True)
                handle = (self._store.lock_dir / (self.session_id + ".lock")).open("a+b")
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                deadline = time.monotonic() + self._store.lock_timeout
                while True:
                    try:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise SessionBusy("Anonymous session is busy") from None
                        time.sleep(0.02)
                locks[self._lock_key] = handle
            yield self
        finally:
            if not nested and handle is not None:
                if self._lock_key in locks:
                    locks.pop(self._lock_key)
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
            lock.release()

    def load_state(self) -> dict[str, Any]:
        with self.lock(), self._store._connect() as db:
            row = db.execute(
                "SELECT state_json FROM sessions WHERE session_id=?", (self.session_id,)
            ).fetchone()
            return json.loads(row["state_json"])

    def save_state(self, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise ValueError("Server state must be a dictionary")
        encoded = _json(state)
        if self.token in encoded:
            raise ValueError("Session credentials cannot be persisted in state")
        with self.lock(), self._store._write() as db:
            db.execute(
                "UPDATE sessions SET state_json=? WHERE session_id=?", (encoded, self.session_id)
            )

    @contextmanager
    def transaction(self) -> Iterator[dict[str, Any]]:
        """Atomically update server state; reservations remain durable on errors.

        This is a state transaction under a session lock, not a long SQLite
        transaction. Exceptions discard state changes but never refund budgets.
        """
        with self.lock():
            states = getattr(_LOCAL, "states", None)
            if states is None:
                states = _LOCAL.states = {}
            if self._lock_key in states:
                yield states[self._lock_key]
                return
            state = self.load_state()
            states[self._lock_key] = state
            try:
                yield state
                self.save_state(state)
            finally:
                states.pop(self._lock_key)

    def reserve(
        self, budget: str, amount: int | float, request_id: str, *, key: str = "default"
    ) -> Reservation:
        """Reserve once per request/budget/key; pending reservations consume quota."""
        request_id = _request_id(request_id)
        amount_units = _units(amount)
        if budget in {"images", "requests"} and amount_units % _SCALE:
            raise ValueError("Count budgets require whole numbers")
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ValueError("A non-empty reservation key is required")
        with self._store._write() as db:
            row = db.execute(
                "SELECT * FROM reservations WHERE session_id=? AND request_id=? "
                "AND budget=? AND item_key=?",
                (self.session_id, request_id, budget, key),
            ).fetchone()
            if row is not None:
                if row["amount_units"] != amount_units or row["status"] == "released":
                    raise RequestConflict("Reservation has already been used with another state")
                return self._reservation(row)
            limit = db.execute(
                "SELECT limit_units FROM budgets WHERE session_id=? AND budget=?",
                (self.session_id, budget),
            ).fetchone()
            if limit is None:
                raise ValueError("Unknown server budget")
            used = db.execute(
                "SELECT COALESCE(SUM(amount_units),0) FROM reservations WHERE session_id=? "
                "AND budget=? AND status IN ('reserved','committed')",
                (self.session_id, budget),
            ).fetchone()[0]
            if used + amount_units > limit[0]:
                raise BudgetExceeded(f"Session {budget} budget is exhausted")
            reservation_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO reservations VALUES (?,?,?,?,?,?,?)",
                (
                    reservation_id,
                    self.session_id,
                    request_id,
                    budget,
                    key,
                    amount_units,
                    "reserved",
                ),
            )
            return Reservation(
                reservation_id, budget, amount_units / _SCALE, request_id, "reserved", self
            )

    def _reservation(self, row: sqlite3.Row) -> Reservation:
        return Reservation(
            row["reservation_id"],
            row["budget"],
            row["amount_units"] / _SCALE,
            row["request_id"],
            row["status"],
            self,
        )

    def commit(self, reservation: Reservation) -> None:
        self._finish_reservation(reservation, "committed")

    def release(self, reservation: Reservation, *, no_side_effects: bool = False) -> None:
        if not no_side_effects:
            raise ValueError("Release requires confirmation that no side effects occurred")
        self._finish_reservation(reservation, "released")

    def _finish_reservation(self, reservation: Reservation, status: str) -> None:
        with self._store._write() as db:
            row = db.execute(
                "SELECT status FROM reservations WHERE reservation_id=? AND session_id=?",
                (reservation.reservation_id, self.session_id),
            ).fetchone()
            if row is None or (row["status"] != "reserved" and row["status"] != status):
                raise RequestConflict("Reservation cannot change its final state")
            db.execute(
                "UPDATE reservations SET status=? WHERE reservation_id=? AND session_id=?",
                (status, reservation.reservation_id, self.session_id),
            )

    def budget(self, name: str) -> dict[str, float]:
        with self._store._connect() as db:
            limit = db.execute(
                "SELECT limit_units FROM budgets WHERE session_id=? AND budget=?",
                (self.session_id, name),
            ).fetchone()
            if limit is None:
                raise ValueError("Unknown server budget")
            totals = {
                row["status"]: row["total"]
                for row in db.execute(
                    "SELECT status,SUM(amount_units) AS total FROM reservations WHERE session_id=? "
                    "AND budget=? GROUP BY status",
                    (self.session_id, name),
                )
            }
            reserved, committed = totals.get("reserved", 0), totals.get("committed", 0)
            return {
                "limit": limit[0] / _SCALE,
                "reserved": reserved / _SCALE,
                "committed": committed / _SCALE,
                "remaining": (limit[0] - reserved - committed) / _SCALE,
            }

    def budget_snapshot(self) -> dict[str, dict[str, float]]:
        """Server-owned ledger evidence; pending reservations already consume quota."""
        with self._store._connect() as db:
            rows = db.execute(
                "SELECT b.budget, b.limit_units, "
                "COALESCE(SUM(CASE WHEN r.status='reserved' THEN r.amount_units ELSE 0 END),0) "
                "AS reserved, "
                "COALESCE(SUM(CASE WHEN r.status='committed' THEN r.amount_units ELSE 0 END),0) "
                "AS committed FROM budgets b LEFT JOIN reservations r "
                "ON b.session_id=r.session_id AND b.budget=r.budget "
                "WHERE b.session_id=? GROUP BY b.budget ORDER BY b.budget",
                (self.session_id,),
            ).fetchall()
        return {
            row["budget"]: {
                "limit": row["limit_units"] / _SCALE,
                "reserved": row["reserved"] / _SCALE,
                "pending": row["reserved"] / _SCALE,
                "committed": row["committed"] / _SCALE,
                "used": row["committed"] / _SCALE,
                "remaining": (row["limit_units"] - row["reserved"] - row["committed"]) / _SCALE,
            }
            for row in rows
        }

    def to_public(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "budget_owner": "CGC",
            "budgets": self.budget_snapshot(),
        }

    def claim_request(self, request_id: str, *, fingerprint: str = "") -> RequestRecord:
        request_id = _request_id(request_id)
        if not isinstance(fingerprint, str) or len(fingerprint) > 256:
            raise ValueError("Request fingerprint must be a short string")
        with self._store._write() as db:
            row = db.execute(
                "SELECT * FROM requests WHERE session_id=? AND request_id=?",
                (self.session_id, request_id),
            ).fetchone()
            if row is not None:
                if row["fingerprint"] != fingerprint:
                    raise RequestConflict("request_id was reused for a different request")
                if row["status"] == "completed":
                    return RequestRecord(request_id, True, json.loads(row["result_json"]), self)
                raise RequestConflict(
                    "Request is active, failed, or requires server reconciliation"
                )
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,'pending',NULL)",
                (self.session_id, request_id, fingerprint),
            )
        return RequestRecord(request_id, False, _session=self)

    def complete_request(self, request_id: str, result: Any) -> None:
        encoded = _json(result)
        if self.token in encoded:
            raise ValueError("Session credentials cannot be persisted in replay results")
        with self._store._write() as db:
            changed = db.execute(
                "UPDATE requests SET status='completed', result_json=? WHERE session_id=? "
                "AND request_id=? AND status='pending'",
                (encoded, self.session_id, request_id),
            ).rowcount
            if changed != 1:
                raise RequestConflict("Only the pending request can complete")
            db.execute(
                "UPDATE reservations SET status='committed' WHERE session_id=? AND request_id=? "
                "AND status='reserved'",
                (self.session_id, request_id),
            )

    def fail_request(self, request_id: str) -> None:
        with self._store._write() as db:
            db.execute(
                "UPDATE requests SET status='failed' WHERE session_id=? AND request_id=? "
                "AND status='pending'",
                (self.session_id, request_id),
            )
            db.execute(
                "UPDATE reservations SET status='committed' WHERE session_id=? AND request_id=? "
                "AND status='reserved'",
                (self.session_id, request_id),
            )

    @contextmanager
    def request(self, request_id: str, *, fingerprint: str = "") -> Iterator[RequestRecord]:
        """Claim once, serialize execution, and retain charges on uncertain failure."""
        record = self.claim_request(request_id, fingerprint=fingerprint)
        if record.cached:
            yield record
            return
        try:
            with self.lock():
                self.reserve("requests", 1, request_id)
                yield record
                if not record._finished:
                    raise RequestConflict("Request must save its final result before completion")
        except BaseException:
            self.fail_request(request_id)
            raise
