"""MySQL disclosure receipt log. Only the content hash is stored."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from contextlib import contextmanager
from threading import Lock

import pymysql
from pymysql.cursors import DictCursor

from cogniguard.governance.disclosure import DisclosureReceipt

_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")
_CONNECT_TIMEOUT = 3


class ReleaseBusy(Exception):
    """Another connection still holds this database's release lock."""


class DisclosureStore:
    """MySQL receipt log. Writes run inside a transaction under one lock."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        if not _DATABASE_NAME.fullmatch(database):
            raise ValueError(database)
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._lock = Lock()
        bootstrap = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            autocommit=True,
            connect_timeout=_CONNECT_TIMEOUT,
        )
        try:
            with bootstrap.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4"
                )
        finally:
            bootstrap.close()
        self._conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            autocommit=False,
            cursorclass=DictCursor,
            connect_timeout=_CONNECT_TIMEOUT,
        )
        self._ensure_table()

    @classmethod
    def from_env(cls) -> DisclosureStore:
        user = os.environ.get("COGNIGUARD_MYSQL_USER", "").strip()
        if not user:
            raise RuntimeError(
                "COGNIGUARD_MYSQL_USER is required to open the disclosure store"
            )
        return cls(
            host=os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
            user=user,
            password=os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
            database=os.environ.get("COGNIGUARD_MYSQL_DATABASE", "cogniguard_disclosure"),
        )

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
        content_sha256 = hashlib.sha256(payload).hexdigest()
        receipt_id = uuid.uuid4().hex
        with self._lock:
            self._write_unlocked(
                """
                INSERT INTO disclosure_receipt (
                    receipt_id, resource_id, unit_id, recipient_principal_id,
                    acting_org_id, agent_principal_id, session_id, policy_version,
                    status, content_sha256, created_at, exposure_delta
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'reserved', %s, %s, %s)
                """,
                (
                    receipt_id,
                    resource_id,
                    unit_id,
                    recipient_principal_id,
                    acting_org_id,
                    agent_principal_id,
                    session_id,
                    policy_version,
                    content_sha256,
                    created_at,
                    float(exposure_delta),
                ),
            )
            return receipt_id

    def commit(self, receipt_id: str) -> None:
        self._transition(receipt_id, "delivered")

    def cancel(self, receipt_id: str) -> None:
        self._transition(receipt_id, "cancelled")

    def history(self, recipient_principal_id: str) -> list[DisclosureReceipt]:
        rows = self._read(
            """
            SELECT receipt_id, resource_id, unit_id, recipient_principal_id,
                   acting_org_id, agent_principal_id, session_id, policy_version,
                   status, content_sha256, created_at, exposure_delta
            FROM disclosure_receipt
            WHERE recipient_principal_id = %s AND status = 'delivered'
            ORDER BY created_at, receipt_id
            """,
            (recipient_principal_id,),
        )
        return [_receipt(row) for row in rows]

    def coalition_units(self, recipient_ids: list[str]) -> frozenset[tuple[str, str]]:
        if not recipient_ids:
            return frozenset()
        placeholders = ", ".join(["%s"] * len(recipient_ids))
        rows = self._read(
            f"""
            SELECT DISTINCT resource_id, unit_id
            FROM disclosure_receipt
            WHERE status = 'delivered'
              AND recipient_principal_id IN ({placeholders})
            """,
            tuple(recipient_ids),
        )
        return frozenset((row["resource_id"], row["unit_id"]) for row in rows)

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset[tuple[str, str]]]:
        """Units each recipient already holds among `units`.

        Reserved receipts count as held. An in-flight release is treated as
        already disclosed so a concurrent coalition is not under-counted.
        """
        if not units:
            return {}
        ordered = tuple(sorted(units))
        placeholders = ", ".join(["(%s, %s)"] * len(ordered))
        params = tuple(part for unit in ordered for part in unit)
        rows = self._read(
            f"""
            SELECT recipient_principal_id, resource_id, unit_id
            FROM disclosure_receipt
            WHERE status IN ('reserved', 'delivered')
              AND (resource_id, unit_id) IN ({placeholders})
            """,
            params,
        )
        held: dict[str, set[tuple[str, str]]] = {}
        for row in rows:
            held.setdefault(row["recipient_principal_id"], set()).add(
                (row["resource_id"], row["unit_id"])
            )
        return {name: frozenset(pairs) for name, pairs in held.items()}

    def exposure_by_recipient(self, resource_id: str, unit_id: str) -> dict[str, float]:
        rows = self._read(
            """
            SELECT recipient_principal_id, SUM(exposure_delta) AS exposure
            FROM disclosure_receipt
            WHERE resource_id = %s AND unit_id = %s AND status = 'delivered'
            GROUP BY recipient_principal_id
            """,
            (resource_id, unit_id),
        )
        return {
            row["recipient_principal_id"]: float(row["exposure"] or 0.0) for row in rows
        }

    def coalition_exposure(
        self, resource_id: str, unit_id: str, recipient_ids: list[str]
    ) -> float:
        if not recipient_ids:
            return 0.0
        placeholders = ", ".join(["%s"] * len(recipient_ids))
        rows = self._read(
            f"""
            SELECT SUM(exposure_delta) AS exposure
            FROM disclosure_receipt
            WHERE resource_id = %s AND unit_id = %s AND status = 'delivered'
              AND recipient_principal_id IN ({placeholders})
            """,
            (resource_id, unit_id, *recipient_ids),
        )
        exposure = rows[0]["exposure"] if rows else None
        return 0.0 if exposure is None else float(exposure)

    @contextmanager
    def release_section(self, timeout: float = 10.0):
        """Hold this database's release lock on the store's own connection.

        GET_LOCK is per connection. The store lock is not held across the
        section, because holders_of and reserve take that same lock.
        """
        name = f"cogniguard_release_{self._database}"
        with self._lock:
            got = self._select_value_unlocked(
                "SELECT GET_LOCK(%s, %s) AS release_lock",
                (name, timeout),
            )
        if got is None or int(got) != 1:
            raise ReleaseBusy(name)
        try:
            yield
        finally:
            with self._lock:
                self._select_value_unlocked(
                    "SELECT RELEASE_LOCK(%s) AS release_lock",
                    (name,),
                )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _ensure_table(self) -> None:
        self._write(
            """
            CREATE TABLE IF NOT EXISTS disclosure_receipt (
                receipt_id VARCHAR(64) NOT NULL PRIMARY KEY,
                resource_id VARCHAR(255) NOT NULL,
                unit_id VARCHAR(255) NOT NULL,
                recipient_principal_id VARCHAR(255) NOT NULL,
                acting_org_id VARCHAR(255) NOT NULL,
                agent_principal_id VARCHAR(255) NOT NULL,
                session_id VARCHAR(255) NOT NULL,
                policy_version INT NOT NULL,
                status VARCHAR(16) NOT NULL,
                content_sha256 CHAR(64) NOT NULL,
                created_at DOUBLE NOT NULL,
                exposure_delta DOUBLE NOT NULL DEFAULT 0,
                KEY idx_disclosure_recipient_status (recipient_principal_id, status)
            )
            """
        )
        columns = self._read(
            """
            SELECT COLUMN_NAME AS column_name
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'disclosure_receipt'
              AND COLUMN_NAME = 'exposure_delta'
            """,
            (self._database,),
        )
        if not columns:
            self._write(
                """
                ALTER TABLE disclosure_receipt
                ADD COLUMN exposure_delta DOUBLE NOT NULL DEFAULT 0
                """
            )

    def _transition(self, receipt_id: str, status: str) -> None:
        with self._lock:
            try:
                self._conn.begin()
                with self._conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT status FROM disclosure_receipt
                        WHERE receipt_id = %s
                        FOR UPDATE
                        """,
                        (receipt_id,),
                    )
                    row = cursor.fetchone()
                    if row is None or row["status"] != "reserved":
                        raise ValueError(receipt_id)
                    cursor.execute(
                        """
                        UPDATE disclosure_receipt
                        SET status = %s
                        WHERE receipt_id = %s AND status = 'reserved'
                        """,
                        (status, receipt_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError(receipt_id)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _write(self, sql: str, params: tuple = ()) -> None:
        with self._lock:
            self._write_unlocked(sql, params)

    def _write_unlocked(self, sql: str, params: tuple = ()) -> None:
        try:
            self._conn.begin()
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _select_value_unlocked(self, sql: str, params: tuple):
        try:
            self._conn.begin()
            with self._conn.cursor() as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        if row is None:
            return None
        return next(iter(row.values()))

    def _read(self, sql: str, params: tuple) -> list[dict]:
        with self._lock:
            try:
                self._conn.begin()
                with self._conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = list(cursor.fetchall())
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return rows


def _receipt(row: dict) -> DisclosureReceipt:
    return DisclosureReceipt(
        receipt_id=row["receipt_id"],
        resource_id=row["resource_id"],
        unit_id=row["unit_id"],
        recipient_principal_id=row["recipient_principal_id"],
        acting_org_id=row["acting_org_id"],
        agent_principal_id=row["agent_principal_id"],
        session_id=row["session_id"],
        policy_version=int(row["policy_version"]),
        status=row["status"],
        content_sha256=row["content_sha256"],
        created_at=float(row["created_at"]),
        exposure_delta=float(row["exposure_delta"]),
    )
