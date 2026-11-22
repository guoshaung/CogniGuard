"""MySQL disclosure receipt log. Only the content hash is stored."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from threading import Lock

import pymysql
from pymysql.cursors import DictCursor

from cogniguard.governance.disclosure import DisclosureReceipt

_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")
_CONNECT_TIMEOUT = 3


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
                    status, content_sha256, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'reserved', %s, %s)
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
                   status, content_sha256, created_at
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
                KEY idx_disclosure_recipient_status (recipient_principal_id, status)
            )
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
    )
