"""X4: state consistency against a lock, a SQLite transaction, and version OCC.

L0, L1, and L2 are ordinary concurrency controls, not research mechanisms.
The receipt log for L0, L2, and the gate observation is in-memory. MySQL is
not opened. L1 uses stdlib sqlite3.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier, Lock, Thread

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cogniguard.governance.access_policy import (  # noqa: E402
    AccessGrant,
    AccessRegistry,
    RegistryHolder,
)
from cogniguard.governance.principals import AssetOwnership, Membership  # noqa: E402
from cogniguard.governance.reconstruction import check_release  # noqa: E402
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry  # noqa: E402

try:
    from cogniguard.runtime.release_gate import (  # noqa: E402
        ReleaseGate,
        ReleaseRequest,
        UnitRelease,
    )

    GATE_IMPORT = "ok"
except Exception as exc:  # pragma: no cover - import probe only
    ReleaseGate = None  # type: ignore
    ReleaseRequest = None  # type: ignore
    UnitRelease = None  # type: ignore
    GATE_IMPORT = type(exc).__name__


# Frozen. Do not retune.
PASS_MIN_ABS_SAFETY_GAIN = 0.10
MAX_UTILITY_DROP = 0.10
MAX_OVERHEAD_RATIO = 10.0
DEV_SEEDS = (0, 1, 2, 3, 4)
DEV_SUBJECTS = 8
DEV_ASSETS = 4
COALITION_K = 2

OWNER = "owner"
ORG = "school"
PURPOSE = "tutoring"
NOW = 1_000.0
N_CASES = 7
CASE_IDS = (
    "witness_race",
    "stale_policy_version",
    "revoke_commit_race",
    "duplicate_event",
    "retry_after_commit",
    "divergent_grant",
    "partial_commit",
)
BASELINES = ("L0", "L1", "L2")
CANDIDATE = "event_key"
# event_key is L1 plus a unique (event, unit) identity. Small variant of L1.
CANDIDATE_IS_SMALL_VARIANT = True
CANDIDATE_IS_STANDARD_LOCK_OR_TRANSACTION = False

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


class PartialFail(Exception):
    """Injected failure of the second receipt write."""


@dataclass(frozen=True)
class World:
    subjects: tuple[str, ...]
    resources: tuple[str, ...]
    targets: TargetRegistry


@dataclass(frozen=True)
class Job:
    event_id: str
    recipient: str
    units: tuple[tuple[str, str], ...]


def make_world(n_subjects: int, n_assets: int) -> World:
    if n_subjects > 10 or n_assets > 4:
        raise ValueError("dev scan cap is 10 subjects and 4 assets")
    subjects = tuple(f"s{i}" for i in range(n_subjects))
    resources = tuple(f"res-{i}" for i in range(n_assets))
    targets = []
    for resource_id in resources:
        targets.append(
            ProtectedTarget(
                f"target-{resource_id}",
                OWNER,
                ORG,
                (frozenset({(resource_id, "u1"), (resource_id, "u2")}),),
                kind="teaching_asset",
            )
        )
    return World(subjects, resources, TargetRegistry(targets))


def registry_at(
    world: World, versions: dict[str, tuple[int, int]] | None = None
) -> AccessRegistry:
    """versions maps resource_id to (policy_version, grant_version)."""
    ownerships = []
    grants = []
    for resource_id in world.resources:
        policy_version, grant_version = (1, 1) if versions is None else versions[resource_id]
        ownerships.append(AssetOwnership(resource_id, OWNER, ORG, policy_version))
        for subject in world.subjects:
            grants.append(AccessGrant(subject, resource_id, PURPOSE, grant_version))
    memberships = [Membership(OWNER, ORG, "teacher")]
    memberships.extend(Membership(subject, ORG, "student") for subject in world.subjects)
    return AccessRegistry(ownerships, memberships, grants)


def bumped(registry: AccessRegistry, resource_id: str) -> AccessRegistry:
    current = registry.owner_of(resource_id)
    if current is None:
        raise KeyError(resource_id)
    return registry.with_policy_version(resource_id, int(current.policy_version) + 1)


def interest(targets: TargetRegistry, units: tuple[tuple[str, str], ...]) -> set[tuple[str, str]]:
    found = set(units)
    for unit in units:
        for target in targets.targets_for_unit(unit):
            for witness in target.witness_sets:
                found.update(witness)
    return found


def judge_release(world: World, registry: AccessRegistry, knowledge: dict, job: Job) -> tuple[bool, str]:
    for resource_id, _unit_id in job.units:
        if not registry.is_authorized(job.recipient, resource_id, PURPOSE, ORG, NOW):
            return False, "unauthorized"
    verdict = check_release(
        world.targets,
        job.recipient,
        job.units,
        knowledge,
        COALITION_K,
    )
    if not verdict.safe:
        return False, "reconstruction"
    return True, "ok"


def state_unsafe(world: World, knowledge: dict[str, frozenset]) -> bool:
    for recipient, units in knowledge.items():
        if not units:
            continue
        others = {name: held for name, held in knowledge.items() if name != recipient}
        verdict = check_release(world.targets, recipient, units, others, COALITION_K)
        if not verdict.safe:
            return True
    return False


def knowledge_from_rows(rows: list[dict]) -> dict[str, frozenset]:
    held: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        if row["status"] not in ("reserved", "delivered"):
            continue
        held.setdefault(row["recipient"], set()).add((row["resource_id"], row["unit_id"]))
    return {name: frozenset(pairs) for name, pairs in held.items()}


class MemoryReceiptStore:
    """In-memory reserve/commit/cancel/holders_of/release_section log.

    A data lock keeps the row list intact. It is not the decision lock.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._rows: list[dict] = []
        self._next = 1

    @contextmanager
    def release_section(self):
        yield

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
        content: str,
        created_at: float,
        exposure_delta: float = 0.0,
        event_id: str = "",
    ) -> str:
        with self._lock:
            receipt_id = f"m{self._next}"
            self._next += 1
            self._rows.append(
                {
                    "receipt_id": receipt_id,
                    "event_id": event_id,
                    "resource_id": resource_id,
                    "unit_id": unit_id,
                    "recipient": recipient_principal_id,
                    "acting_org_id": acting_org_id,
                    "status": "reserved",
                    "policy_version": int(policy_version),
                    "exposure_delta": float(exposure_delta),
                    "content_len": len(content),
                    "created_at": created_at,
                    "session_id": session_id,
                    "agent_principal_id": agent_principal_id,
                }
            )
            return receipt_id

    def commit(self, receipt_id: str) -> None:
        with self._lock:
            for row in self._rows:
                if row["receipt_id"] == receipt_id:
                    row["status"] = "delivered"
                    return
            raise KeyError(receipt_id)

    def cancel(self, receipt_id: str) -> None:
        with self._lock:
            for row in self._rows:
                if row["receipt_id"] == receipt_id:
                    row["status"] = "cancelled"
                    return

    def holders_of(self, units: set[tuple[str, str]]) -> dict[str, frozenset[tuple[str, str]]]:
        with self._lock:
            snapshot = [dict(row) for row in self._rows]
        return _holders(snapshot, units)

    def rows(self) -> list[dict]:
        with self._lock:
            return [dict(row) for row in self._rows]


def _holders(rows: list[dict], units: set[tuple[str, str]]) -> dict[str, frozenset]:
    held: dict[str, set[tuple[str, str]]] = {}
    for row in rows:
        if row["status"] not in ("reserved", "delivered"):
            continue
        pair = (row["resource_id"], row["unit_id"])
        if pair not in units:
            continue
        held.setdefault(row["recipient"], set()).add(pair)
    return {name: frozenset(pairs) for name, pairs in held.items()}


def delivered_rows(rows: list[dict], event_id: str | None = None) -> list[dict]:
    found = []
    for row in rows:
        if row["status"] != "delivered":
            continue
        if event_id is not None and row["event_id"] != event_id:
            continue
        found.append(row)
    return found


class L0System:
    """One process lock around decide-and-commit. No rollback, no event key."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.lock = Lock()
        self.store = MemoryReceiptStore()
        self.registry = registry_at(world)

    def set_registry(self, registry: AccessRegistry) -> None:
        with self.lock:
            self.registry = registry

    def bump(self, resource_id: str) -> None:
        self.set_registry(bumped(self.registry, resource_id))

    def decide_and_commit(self, job: Job, *, fail_second: bool = False) -> dict:
        with self.lock:
            return self._inside(job, fail_second=fail_second)

    def _inside(self, job: Job, *, fail_second: bool) -> dict:
        knowledge = self.store.holders_of(interest(self.world.targets, job.units))
        ok, reason = judge_release(self.world, self.registry, knowledge, job)
        if not ok:
            return {"delivered": False, "reason": reason, "aborted": False}
        ids = []
        versions = []
        for resource_id, unit_id in job.units:
            version = int(self.registry.owner_of(resource_id).policy_version)
            versions.append(version)
            ids.append(
                self.store.reserve(
                    resource_id=resource_id,
                    unit_id=unit_id,
                    recipient_principal_id=job.recipient,
                    acting_org_id=ORG,
                    agent_principal_id="agent",
                    session_id="s",
                    policy_version=version,
                    content=unit_id,
                    created_at=NOW,
                    exposure_delta=1.0,
                    event_id=job.event_id,
                )
            )
        try:
            for index, receipt_id in enumerate(ids):
                if fail_second and index == 1:
                    raise PartialFail()
                self.store.commit(receipt_id)
        except PartialFail:
            return {"delivered": False, "reason": "partial", "aborted": True}
        return {"delivered": True, "reason": "ok", "aborted": False, "versions": versions}

    def rows(self) -> list[dict]:
        return self.store.rows()


class L2System:
    """Monotonic policy version checked at commit. No lock and no rollback."""

    def __init__(self, world: World, shared_version: list[int] | None = None) -> None:
        self.world = world
        self.store = MemoryReceiptStore()
        self.registry = registry_at(world)
        self.shared_version = shared_version if shared_version is not None else [1]

    def bump(self, resource_id: str) -> None:
        self.registry = bumped(self.registry, resource_id)
        self.shared_version[0] = int(self.registry.owner_of(resource_id).policy_version)

    def evaluate(self, job: Job) -> dict:
        knowledge = self.store.holders_of(interest(self.world.targets, job.units))
        version = int(self.shared_version[0])
        ok, reason = judge_release(self.world, self.registry, knowledge, job)
        return {"ok": ok, "reason": reason, "version": version, "job": job}

    def commit(self, token: dict, *, fail_second: bool = False) -> dict:
        if not token["ok"]:
            return {"delivered": False, "reason": token["reason"], "aborted": False}
        if int(self.shared_version[0]) != int(token["version"]):
            return {"delivered": False, "reason": "version_mismatch", "aborted": False}
        job: Job = token["job"]
        ids = []
        for resource_id, unit_id in job.units:
            ids.append(
                self.store.reserve(
                    resource_id=resource_id,
                    unit_id=unit_id,
                    recipient_principal_id=job.recipient,
                    acting_org_id=ORG,
                    agent_principal_id="agent",
                    session_id="s",
                    policy_version=int(token["version"]),
                    content=unit_id,
                    created_at=NOW,
                    exposure_delta=1.0,
                    event_id=job.event_id,
                )
            )
        try:
            for index, receipt_id in enumerate(ids):
                if fail_second and index == 1:
                    raise PartialFail()
                self.store.commit(receipt_id)
        except PartialFail:
            return {"delivered": False, "reason": "partial", "aborted": True}
        return {"delivered": True, "reason": "ok", "aborted": False}

    def run(self, job: Job, *, fail_second: bool = False) -> dict:
        return self.commit(self.evaluate(job), fail_second=fail_second)

    def rows(self) -> list[dict]:
        return self.store.rows()


def init_db(path: str, world: World, *, event_key: bool) -> None:
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=8000")
        conn.execute(
            """
            CREATE TABLE policy (
                resource_id TEXT PRIMARY KEY,
                policy_version INTEGER NOT NULL,
                grant_version INTEGER NOT NULL
            )
            """
        )
        unique = (
            ", UNIQUE(event_id, resource_id, unit_id)"
            if event_key
            else ""
        )
        conn.execute(
            f"""
            CREATE TABLE receipt (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                unit_id TEXT NOT NULL,
                recipient TEXT NOT NULL,
                status TEXT NOT NULL,
                exposure REAL NOT NULL,
                policy_version INTEGER NOT NULL
                {unique}
            )
            """
        )
        conn.executemany(
            "INSERT INTO policy (resource_id, policy_version, grant_version) VALUES (?, 1, 1)",
            [(resource_id,) for resource_id in world.resources],
        )
    finally:
        conn.close()


def connect_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.execute("PRAGMA busy_timeout=8000")
    return conn


def _policy_map(conn: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        "SELECT resource_id, policy_version, grant_version FROM policy"
    ).fetchall()
    return {row[0]: (int(row[1]), int(row[2])) for row in rows}


def _sql_knowledge(conn: sqlite3.Connection, units: set[tuple[str, str]]) -> dict[str, frozenset]:
    if not units:
        return {}
    rows = conn.execute(
        """
        SELECT recipient, resource_id, unit_id, status
        FROM receipt
        WHERE status IN ('reserved', 'delivered')
        """
    ).fetchall()
    shaped = [
        {
            "recipient": row[0],
            "resource_id": row[1],
            "unit_id": row[2],
            "status": row[3],
        }
        for row in rows
    ]
    return _holders(shaped, units)


def _delivered_count(conn: sqlite3.Connection, event_id: str | None = None) -> int:
    if event_id is None:
        row = conn.execute(
            "SELECT COUNT(*) FROM receipt WHERE status = 'delivered'"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) FROM receipt WHERE status = 'delivered' AND event_id = ?",
            (event_id,),
        ).fetchone()
    return int(row[0])


def sqlite_apply(
    conn: sqlite3.Connection,
    world: World,
    job: Job,
    *,
    event_key: bool,
    fail_second: bool = False,
) -> dict:
    """One ordinary transaction: re-read, decide, write, commit or roll back.

    event_key adds a unique (event, unit) identity and treats a replay as the
    original effect. L1 leaves it off, matching surrogate receipt ids.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        versions = _policy_map(conn)
        registry = registry_at(world, versions)
        knowledge = _sql_knowledge(conn, interest(world.targets, job.units))
        ok, reason = judge_release(world, registry, knowledge, job)
        if not ok:
            conn.execute("ROLLBACK")
            return {"delivered": False, "reason": reason, "aborted": False, "replay": False}
        if event_key:
            already = True
            for resource_id, unit_id in job.units:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM receipt
                    WHERE event_id = ? AND resource_id = ? AND unit_id = ?
                      AND recipient = ? AND status = 'delivered'
                    """,
                    (job.event_id, resource_id, unit_id, job.recipient),
                ).fetchone()
                if int(row[0]) == 0:
                    already = False
                    break
            if already:
                conn.execute("ROLLBACK")
                return {
                    "delivered": False,
                    "reason": "replay",
                    "aborted": False,
                    "replay": True,
                }
        for index, (resource_id, unit_id) in enumerate(job.units):
            if fail_second and index == 1:
                raise PartialFail()
            policy_version = versions[resource_id][0]
            conn.execute(
                """
                INSERT INTO receipt (
                    event_id, resource_id, unit_id, recipient, status,
                    exposure, policy_version
                ) VALUES (?, ?, ?, ?, 'delivered', 1.0, ?)
                """,
                (job.event_id, resource_id, unit_id, job.recipient, policy_version),
            )
        conn.execute("COMMIT")
        return {"delivered": True, "reason": "ok", "aborted": False, "replay": False}
    except PartialFail:
        conn.execute("ROLLBACK")
        return {"delivered": False, "reason": "partial", "aborted": True, "replay": False}
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        if event_key and _delivered_count(conn, job.event_id) >= len(job.units):
            return {"delivered": False, "reason": "replay", "aborted": False, "replay": True}
        raise


def sqlite_apply_retry(path: str, world: World, job: Job, *, event_key: bool, fail_second: bool = False) -> dict:
    last: Exception | None = None
    for _ in range(6):
        conn = connect_db(path)
        try:
            return sqlite_apply(
                conn, world, job, event_key=event_key, fail_second=fail_second
            )
        except sqlite3.OperationalError as exc:
            last = exc
            text = str(exc).lower()
            if "locked" not in text and "busy" not in text:
                raise
        finally:
            conn.close()
    raise RuntimeError("sqlite busy") from last


class SQLiteSystem:
    def __init__(self, directory: str, world: World, *, event_key: bool) -> None:
        self.world = world
        self.event_key = event_key
        self.path = str(Path(directory) / f"x4-{event_key}-{time.perf_counter_ns()}.sqlite")
        init_db(self.path, world, event_key=event_key)

    def decide_and_commit(self, job: Job, *, fail_second: bool = False) -> dict:
        return sqlite_apply_retry(
            self.path, self.world, job, event_key=self.event_key, fail_second=fail_second
        )

    def bump(self, resource_id: str) -> None:
        conn = connect_db(self.path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE policy SET policy_version = policy_version + 1 WHERE resource_id = ?",
                (resource_id,),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()

    def rows(self) -> list[dict]:
        conn = connect_db(self.path)
        try:
            found = conn.execute(
                """
                SELECT receipt_id, event_id, resource_id, unit_id, recipient,
                       status, exposure, policy_version
                FROM receipt
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "receipt_id": str(row[0]),
                "event_id": row[1],
                "resource_id": row[2],
                "unit_id": row[3],
                "recipient": row[4],
                "status": row[5],
                "exposure_delta": row[6],
                "policy_version": row[7],
            }
            for row in found
        ]


def new_system(method: str, world: World, directory: str):
    if method == "L0":
        return L0System(world)
    if method == "L2":
        return L2System(world)
    if method == "L1":
        return SQLiteSystem(directory, world, event_key=False)
    if method == CANDIDATE:
        return SQLiteSystem(directory, world, event_key=True)
    raise KeyError(method)


def _join(threads: list[Thread]) -> None:
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)
    if any(thread.is_alive() for thread in threads):
        raise TimeoutError("worker did not finish")


def race_call(functions: list) -> list[dict]:
    barrier = Barrier(len(functions), timeout=15)
    box: list[dict | None] = [None] * len(functions)

    def wrap(index: int, fn) -> None:
        barrier.wait()
        started = time.perf_counter()
        value = fn()
        value["latency_s"] = time.perf_counter() - started
        box[index] = value

    _join([Thread(target=wrap, args=(index, fn)) for index, fn in enumerate(functions)])
    return [value for value in box if value is not None]


def l2_split_race(system: L2System, jobs: tuple[Job, Job]) -> list[dict]:
    barrier = Barrier(2, timeout=15)
    box: list[dict | None] = [None, None]

    def wrap(index: int, job: Job) -> None:
        started = time.perf_counter()
        token = system.evaluate(job)
        read_s = time.perf_counter() - started
        barrier.wait()
        commit_started = time.perf_counter()
        value = system.commit(token)
        value["latency_s"] = read_s + (time.perf_counter() - commit_started)
        box[index] = value

    _join([Thread(target=wrap, args=(0, jobs[0])), Thread(target=wrap, args=(1, jobs[1]))])
    return [value for value in box if value is not None]


def case_witness(method: str, world: World, directory: str) -> dict:
    system = new_system(method, world, directory)
    left = Job("w-left", world.subjects[0], ((world.resources[0], "u1"),))
    right = Job("w-right", world.subjects[1], ((world.resources[0], "u2"),))
    if method == "L2":
        outcomes = l2_split_race(system, (left, right))
    else:
        outcomes = race_call(
            [
                lambda: system.decide_and_commit(left),
                lambda: system.decide_and_commit(right),
            ]
        )
    unsafe = state_unsafe(world, knowledge_from_rows(system.rows()))
    delivered = sum(1 for item in outcomes if item.get("delivered") or item.get("replay"))
    return {
        "case": "witness_race",
        "method": method,
        "safety_violation": bool(unsafe),
        "delivered_requests": delivered,
        "latency_s": max(item["latency_s"] for item in outcomes),
        "detail": "both delivered" if unsafe else f"delivered_requests={delivered}",
    }


def case_stale(method: str, world: World, directory: str) -> dict:
    system = new_system(method, world, directory)
    job = Job("stale-1", world.subjects[0], ((world.resources[0], "u1"),))
    started = time.perf_counter()
    if method == "L2":
        token = system.evaluate(job)
        system.bump(world.resources[0])
        outcome = system.commit(token)
    else:
        system.bump(world.resources[0])
        outcome = system.decide_and_commit(job)
    latency = time.perf_counter() - started
    wrote = bool(delivered_rows(system.rows(), job.event_id))
    return {
        "case": "stale_policy_version",
        "method": method,
        "safety_violation": wrote,
        "delivered_requests": int(wrote),
        "latency_s": latency,
        "detail": outcome["reason"],
    }


def case_revoke(method: str, world: World, directory: str) -> dict:
    """Two orders. A violation is a commit after the revoke is already stored."""
    job = Job("revoke-1", world.subjects[0], ((world.resources[0], "u1"),))
    latencies = []

    first = new_system(method, world, directory)
    started = time.perf_counter()
    if method == "L2":
        token = first.evaluate(job)
        first.bump(world.resources[0])
        first.commit(token)
    else:
        first.bump(world.resources[0])
        first.decide_and_commit(job)
    revoke_first_wrote = bool(delivered_rows(first.rows(), job.event_id))
    latencies.append(time.perf_counter() - started)

    second = new_system(method, world, directory)
    started = time.perf_counter()
    if method == "L2":
        token = second.evaluate(job)
        commit_out = second.commit(token)
        commit_first_wrote = bool(commit_out.get("delivered"))
        second.bump(world.resources[0])
    else:
        commit_out = second.decide_and_commit(job)
        commit_first_wrote = bool(commit_out.get("delivered"))
        second.bump(world.resources[0])
    latencies.append(time.perf_counter() - started)
    return {
        "case": "revoke_commit_race",
        "method": method,
        "safety_violation": bool(revoke_first_wrote),
        "delivered_requests": int(commit_first_wrote),
        "latency_s": sum(latencies) / len(latencies),
        "detail": f"revoke_first_wrote={revoke_first_wrote};commit_first_wrote={commit_first_wrote}",
        "false_reject_commit_first": not commit_first_wrote,
    }


def case_duplicate(method: str, world: World, directory: str) -> dict:
    system = new_system(method, world, directory)
    job = Job("dup-event", world.subjects[0], ((world.resources[0], "u1"),))
    if method == "L2":
        outcomes = l2_split_race(system, (job, job))
    else:
        outcomes = race_call(
            [
                lambda: system.decide_and_commit(job),
                lambda: system.decide_and_commit(job),
            ]
        )
    count = len(delivered_rows(system.rows(), job.event_id))
    return {
        "case": "duplicate_event",
        "method": method,
        "safety_violation": count > 1,
        "delivered_requests": count,
        "latency_s": max(item["latency_s"] for item in outcomes),
        "detail": f"delivered_rows={count}",
    }


def case_retry(method: str, world: World, directory: str) -> dict:
    system = new_system(method, world, directory)
    job = Job("retry-event", world.subjects[0], ((world.resources[0], "u1"),))
    started = time.perf_counter()
    first = system.run(job) if method == "L2" else system.decide_and_commit(job)
    second = system.run(job) if method == "L2" else system.decide_and_commit(job)
    latency = time.perf_counter() - started
    count = len(delivered_rows(system.rows(), job.event_id))
    effect_missing = count == 0
    return {
        "case": "retry_after_commit",
        "method": method,
        "safety_violation": count > 1,
        "delivered_requests": count,
        "latency_s": latency,
        "detail": f"first={first['reason']};second={second['reason']};rows={count}",
        "false_reject": effect_missing,
    }


def case_partial(method: str, world: World, directory: str) -> dict:
    system = new_system(method, world, directory)
    job = Job(
        "partial-event",
        world.subjects[0],
        ((world.resources[0], "u1"), (world.resources[1], "u1")),
    )
    started = time.perf_counter()
    if method == "L2":
        outcome = system.run(job, fail_second=True)
    else:
        outcome = system.decide_and_commit(job, fail_second=True)
    latency = time.perf_counter() - started
    if not outcome.get("aborted"):
        raise RuntimeError(f"{method} did not inject the second-write failure")
    count = len(delivered_rows(system.rows(), job.event_id))
    # A failed multi-receipt commit must leave no delivered unit.
    return {
        "case": "partial_commit",
        "method": method,
        "safety_violation": count != 0,
        "delivered_requests": count,
        "latency_s": latency,
        "detail": f"delivered_after_abort={count}",
    }


def _case6_l0(stale_allow: bool) -> dict:
    started = time.perf_counter()
    if not stale_allow:
        return {"delivered": False, "reason": "cache_deny", "latency_s": time.perf_counter() - started}
    store = MemoryReceiptStore()
    lock = Lock()
    with lock:
        receipt_id = store.reserve(
            resource_id="res-0",
            unit_id="u1",
            recipient_principal_id="s0",
            acting_org_id=ORG,
            agent_principal_id="agent",
            session_id="s",
            policy_version=1,
            content="u1",
            created_at=NOW,
            exposure_delta=1.0,
            event_id="divergent",
        )
        store.commit(receipt_id)
    return {"delivered": True, "reason": "stale_cache", "latency_s": time.perf_counter() - started}


def _case6_l1(db_path: str) -> dict:
    world = make_world(2, 1)
    job = Job("divergent", "s0", (("res-0", "u1"),))
    started = time.perf_counter()
    outcome = sqlite_apply_retry(db_path, world, job, event_key=False)
    outcome["latency_s"] = time.perf_counter() - started
    outcome["db_rows"] = _count_path(db_path)
    return outcome


def _case6_l2(presented_version: int, shared_version) -> dict:
    started = time.perf_counter()
    current = int(shared_version.value)
    if current != int(presented_version):
        return {
            "delivered": False,
            "reason": "version_mismatch",
            "latency_s": time.perf_counter() - started,
            "seen_version": current,
        }
    return {
        "delivered": True,
        "reason": "version_match",
        "latency_s": time.perf_counter() - started,
        "seen_version": current,
    }


def _case6_candidate(db_path: str) -> dict:
    world = make_world(2, 1)
    job = Job("divergent", "s0", (("res-0", "u1"),))
    started = time.perf_counter()
    outcome = sqlite_apply_retry(db_path, world, job, event_key=True)
    outcome["latency_s"] = time.perf_counter() - started
    outcome["db_rows"] = _count_path(db_path)
    return outcome


def _count_path(db_path: str) -> int:
    conn = connect_db(db_path)
    try:
        return _delivered_count(conn)
    finally:
        conn.close()


def _process_entry(box, target, target_args) -> None:
    try:
        box.put(("ok", target(*target_args)))
    except Exception as exc:
        box.put(("err", f"{type(exc).__name__}: {exc}"[:240]))


def _process_call(fn, args: tuple) -> dict:
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_process_entry, args=(queue, fn, args))
    proc.start()
    proc.join(30)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        raise TimeoutError(fn.__name__)
    if proc.exitcode not in (0, None):
        raise RuntimeError(f"{fn.__name__} exit {proc.exitcode}")
    status, payload = queue.get(timeout=5)
    if status != "ok":
        raise RuntimeError(str(payload))
    return payload


def case_divergent(method: str, directory: str) -> dict:
    """Two processes. Logical grant is already revoked. Caches still say allow."""
    world = make_world(2, 1)
    db_path = str(Path(directory) / f"divergent-{method}.sqlite")
    if method in ("L1", CANDIDATE):
        init_db(db_path, world, event_key=(method == CANDIDATE))
        conn = connect_db(db_path)
        try:
            conn.execute("UPDATE policy SET policy_version = 2 WHERE resource_id = 'res-0'")
        finally:
            conn.close()
    started = time.perf_counter()
    if method == "L0":
        left = _process_call(_case6_l0, (True,))
        right = _process_call(_case6_l0, (True,))
        delivered = int(bool(left["delivered"])) + int(bool(right["delivered"]))
        detail = "two stale caches committed"
    elif method == "L1":
        left = _process_call(_case6_l1, (db_path,))
        right = _process_call(_case6_l1, (db_path,))
        delivered = int(left.get("db_rows") or 0)
        detail = f"left={left['reason']};right={right['reason']}"
    elif method == "L2":
        import multiprocessing as mp

        shared = mp.get_context("spawn").Value("i", 2)
        left = _process_call(_case6_l2, (1, shared))
        right = _process_call(_case6_l2, (1, shared))
        delivered = int(bool(left["delivered"])) + int(bool(right["delivered"]))
        detail = f"left={left['reason']};right={right['reason']}"
    else:
        left = _process_call(_case6_candidate, (db_path,))
        right = _process_call(_case6_candidate, (db_path,))
        delivered = int(left.get("db_rows") or 0)
        detail = f"left={left['reason']};right={right['reason']}"
    latency = max(left["latency_s"], right["latency_s"])
    _ = started
    # Logical grant is revoked, so any delivered row is unauthorized.
    return {
        "case": "divergent_grant",
        "method": method,
        "safety_violation": delivered > 0,
        "delivered_requests": delivered,
        "latency_s": latency,
        "detail": detail,
    }


CASE_RUNNERS = {
    "witness_race": case_witness,
    "stale_policy_version": case_stale,
    "revoke_commit_race": case_revoke,
    "duplicate_event": case_duplicate,
    "retry_after_commit": case_retry,
    "partial_commit": case_partial,
}


def run_deterministic(directory: str) -> list[dict]:
    world = make_world(2, 2)
    rows = []
    for method in (*BASELINES, CANDIDATE):
        for case_id, runner in CASE_RUNNERS.items():
            rows.append(runner(method, world, directory))
        rows.append(case_divergent(method, directory))
    return rows


def run_serial(method: str, world: World, directory: str, prefix: str) -> tuple[int, int, list[float]]:
    system = new_system(method, world, directory)
    denies = 0
    latencies = []
    for index, subject in enumerate(world.subjects):
        job = Job(f"{prefix}-{index}", subject, ((world.resources[0], "u1"),))
        started = time.perf_counter()
        outcome = system.run(job) if method == "L2" else system.decide_and_commit(job)
        latencies.append(time.perf_counter() - started)
        if not outcome.get("delivered"):
            denies += 1
    unsafe = state_unsafe(world, knowledge_from_rows(system.rows()))
    if unsafe:
        raise RuntimeError(f"serial workload completed a witness under {method}")
    return denies, len(world.subjects), latencies


def run_dev_scan(directory: str) -> dict:
    import random

    methods = (*BASELINES, CANDIDATE)
    summary = {
        method: {"races": 0, "witness_violations": 0, "exact_one": 0, "serial_denies": 0, "serial_n": 0, "latencies": []}
        for method in methods
    }
    for seed in DEV_SEEDS:
        rng = random.Random(seed)
        world = make_world(DEV_SUBJECTS, DEV_ASSETS)
        pairs = []
        for resource_id in world.resources:
            left, right = rng.sample(world.subjects, 2)
            pairs.append(
                (
                    Job(f"{seed}-{resource_id}-a", left, ((resource_id, "u1"),)),
                    Job(f"{seed}-{resource_id}-b", right, ((resource_id, "u2"),)),
                )
            )
        for method in methods:
            denies, total, latencies = run_serial(method, world, directory, f"serial-{seed}-{method}")
            bucket = summary[method]
            bucket["serial_denies"] += denies
            bucket["serial_n"] += total
            bucket["latencies"].extend(latencies)
            for left, right in pairs:
                system = new_system(method, world, directory)
                if method == "L2":
                    outcomes = l2_split_race(system, (left, right))
                else:
                    outcomes = race_call(
                        [
                            lambda system=system, left=left: system.decide_and_commit(left),
                            lambda system=system, right=right: system.decide_and_commit(right),
                        ]
                    )
                unsafe = state_unsafe(world, knowledge_from_rows(system.rows()))
                delivered = sum(1 for item in outcomes if item.get("delivered"))
                bucket["races"] += 1
                bucket["witness_violations"] += int(unsafe)
                bucket["exact_one"] += int(delivered == 1 and not unsafe)
                bucket["latencies"].append(max(item["latency_s"] for item in outcomes))
    rendered = {}
    for method, bucket in summary.items():
        rendered[method] = {
            "races": bucket["races"],
            "witness_violation_rate": bucket["witness_violations"] / bucket["races"],
            "exact_one_rate": bucket["exact_one"] / bucket["races"],
            "false_reject_rate": bucket["serial_denies"] / bucket["serial_n"],
            "mean_latency_s": sum(bucket["latencies"]) / len(bucket["latencies"]),
            "serial_n": bucket["serial_n"],
            "seeds": list(DEV_SEEDS),
            "subjects": DEV_SUBJECTS,
            "assets": DEV_ASSETS,
        }
    return rendered


def observe_gate(directory: str) -> dict:
    """Call ReleaseGate against the in-memory store. Not a scored baseline."""
    if ReleaseGate is None:
        return {"import": GATE_IMPORT, "ran": False}
    world = make_world(2, 2)
    registry = registry_at(world)
    observed: dict = {"import": GATE_IMPORT, "ran": True, "store": "in-memory"}

    def request(recipient: str, units: tuple[tuple[str, str], ...]) -> ReleaseRequest:
        return ReleaseRequest(
            recipient_principal_id=recipient,
            acting_org_id=ORG,
            agent_principal_id="agent",
            session_id="s",
            purpose=PURPOSE,
            units=tuple(
                UnitRelease(resource_id, unit_id, unit_id, 1.0) for resource_id, unit_id in units
            ),
            now=NOW,
        )

    store = MemoryReceiptStore()
    gate = ReleaseGate(
        store,
        access_registry=registry,
        target_registry=world.targets,
        coalition_k=COALITION_K,
    )
    box: list = [None, None]
    barrier = Barrier(2, timeout=15)

    def hit(index: int, job: ReleaseRequest) -> None:
        barrier.wait()
        decision = gate.evaluate_and_reserve(job)
        committed = gate.commit(decision, NOW) if decision.allowed else False
        box[index] = {"allowed": decision.allowed, "reason": decision.reason, "committed": committed}

    left = request("s0", (("res-0", "u1"),))
    right = request("s1", (("res-0", "u2"),))
    _join([Thread(target=hit, args=(0, left)), Thread(target=hit, args=(1, right))])
    observed["witness_race"] = {
        "outcomes": box,
        "both_committed": all(item and item["committed"] for item in box),
        "final_unsafe": state_unsafe(world, knowledge_from_rows(store.rows())),
    }

    holder = RegistryHolder(registry)
    stale_store = MemoryReceiptStore()
    stale_gate = ReleaseGate(
        stale_store,
        registry_holder=holder,
        target_registry=world.targets,
        coalition_k=COALITION_K,
    )
    decision = stale_gate.evaluate_and_reserve(request("s0", (("res-0", "u1"),)))
    holder.replace(bumped(registry, "res-0"))
    observed["stale_policy_version_commit_returned"] = bool(stale_gate.commit(decision, NOW))

    retry_store = MemoryReceiptStore()
    retry_gate = ReleaseGate(
        retry_store,
        access_registry=registry,
        target_registry=world.targets,
        coalition_k=COALITION_K,
    )
    first = retry_gate.evaluate_and_reserve(request("s0", (("res-0", "u1"),)))
    retry_gate.commit(first, NOW)
    second = retry_gate.evaluate_and_reserve(request("s0", (("res-0", "u1"),)))
    retry_gate.commit(second, NOW)
    observed["retry_delivered_rows"] = len(delivered_rows(retry_store.rows()))

    class FailSecond(MemoryReceiptStore):
        def __init__(self) -> None:
            super().__init__()
            self.commits = 0

        def commit(self, receipt_id: str) -> None:
            self.commits += 1
            if self.commits >= 2:
                raise PartialFail()
            super().commit(receipt_id)

    partial_store = FailSecond()
    partial_gate = ReleaseGate(
        partial_store,
        access_registry=registry,
        target_registry=world.targets,
        coalition_k=COALITION_K,
    )
    partial_decision = partial_gate.evaluate_and_reserve(
        request("s0", (("res-0", "u1"), ("res-1", "u1")))
    )
    partial_error = False
    try:
        partial_gate.commit(partial_decision, NOW)
    except PartialFail:
        partial_error = True
    observed["partial_commit"] = {
        "allowed": partial_decision.allowed,
        "raised": partial_error,
        "delivered_rows": len(delivered_rows(partial_store.rows())),
    }

    stale_registry = registry
    logical = bumped(registry, "res-0")
    stores = [MemoryReceiptStore(), MemoryReceiptStore()]
    committed = []
    for local in stores:
        local_gate = ReleaseGate(
            local,
            access_registry=stale_registry,
            target_registry=world.targets,
            coalition_k=COALITION_K,
        )
        decision = local_gate.evaluate_and_reserve(request("s0", (("res-0", "u1"),)))
        committed.append(bool(decision.allowed and local_gate.commit(decision, NOW)))
    observed["two_stores"] = {
        "logical_authorized": logical.is_authorized("s0", "res-0", PURPOSE, ORG, NOW),
        "both_committed": all(committed),
    }
    _ = directory
    return observed


def semantic_self_check() -> None:
    world = make_world(2, 2)
    registry = registry_at(world)
    assert registry.is_authorized("s0", "res-0", PURPOSE, ORG, NOW)
    assert not bumped(registry, "res-0").is_authorized("s0", "res-0", PURPOSE, ORG, NOW)
    alone = check_release(world.targets, "s0", [("res-0", "u1")], {}, COALITION_K)
    paired = check_release(
        world.targets,
        "s1",
        [("res-0", "u2")],
        {"s0": frozenset({("res-0", "u1")})},
        COALITION_K,
    )
    if not alone.safe or paired.safe:
        raise RuntimeError("check_release self-check failed")
    partial = check_release(
        world.targets,
        "s0",
        [("res-0", "u1"), ("res-1", "u1")],
        {},
        COALITION_K,
    )
    if not partial.safe:
        raise RuntimeError("partial-commit release is not reconstruction-safe")


def mean(values: list[float]) -> float:
    if not values:
        raise RuntimeError("empty latency sample")
    return sum(values) / len(values)


def build_summary(rows: list[dict], dev: dict, observed: dict, head: str) -> dict:
    by_method: dict[str, list[dict]] = {}
    for row in rows:
        by_method.setdefault(row["method"], []).append(row)
    fails = {
        method: sorted(row["case"] for row in items if row["safety_violation"])
        for method, items in by_method.items()
    }
    latencies = {
        method: [row["latency_s"] for row in items]
        for method, items in by_method.items()
    }
    for method, payload in dev.items():
        latencies[method] = latencies.get(method, []) + [payload["mean_latency_s"]]
    false_reject = {method: payload["false_reject_rate"] for method, payload in dev.items()}
    strongest = min(
        BASELINES,
        key=lambda method: (len(fails[method]), false_reject[method], mean(latencies[method]), method),
    )
    shared = set(fails[BASELINES[0]])
    for method in BASELINES[1:]:
        shared &= set(fails[method])
    candidate_fails = set(fails[CANDIDATE])
    safety_gain = (len(fails[strongest]) - len(candidate_fails)) / N_CASES
    utility = {method: 1.0 - false_reject[method] for method in (*BASELINES, CANDIDATE)}
    utility_change = utility[CANDIDATE] - utility[strongest]
    utility_drop = utility[strongest] - utility[CANDIDATE]
    overhead = mean(latencies[CANDIDATE]) / mean(latencies[strongest])
    numeric_ok = (
        safety_gain >= PASS_MIN_ABS_SAFETY_GAIN
        and utility_drop <= MAX_UTILITY_DROP
        and overhead < MAX_OVERHEAD_RATIO
    )
    if len(fails[strongest]) == 0:
        verdict = "STOP"
        safety_gain_out = 0.0
        utility_change_out = 0.0
    elif shared and candidate_fails.isdisjoint(shared) and CANDIDATE_IS_SMALL_VARIANT:
        verdict = "ANALYZE"
        safety_gain_out = safety_gain
        utility_change_out = utility_change
    elif (
        shared
        and candidate_fails.isdisjoint(shared)
        and numeric_ok
        and not CANDIDATE_IS_SMALL_VARIANT
        and not CANDIDATE_IS_STANDARD_LOCK_OR_TRANSACTION
    ):
        verdict = "PASS"
        safety_gain_out = safety_gain
        utility_change_out = utility_change
    elif shared and CANDIDATE_IS_SMALL_VARIANT:
        verdict = "ANALYZE"
        safety_gain_out = safety_gain
        utility_change_out = utility_change
    else:
        verdict = "STOP"
        safety_gain_out = 0.0
        utility_change_out = 0.0

    case_table = []
    for row in rows:
        case_table.append(
            {
                "method": row["method"],
                "case": row["case"],
                "safety_violation": row["safety_violation"],
                "detail": row["detail"],
                "latency_s": row["latency_s"],
                "delivered_requests": row["delivered_requests"],
            }
        )
    notes = (
        "Receipt state for L0, L2, and the ReleaseGate observation is an in-memory "
        "store with reserve/commit/cancel/holders_of/release_section. DisclosureStore "
        "was not opened and MySQL was not started. L0 is one process lock around "
        "decide-and-commit, with no rollback and no event identity; the two case-6 "
        "processes do not share that lock. L1 is one stdlib sqlite3 BEGIN IMMEDIATE "
        "transaction that re-reads policy and receipts, then commits or rolls back. "
        "Its receipt identity is a surrogate receipt_id, the same kind of identity "
        "DisclosureStore uses, not an event key. L2 checks one shared monotonic "
        "policy version at commit and does not lock or roll back a multi-receipt write. "
        f"Shared failures: {sorted(shared) or 'none'}. Candidate {CANDIDATE} is L1 plus "
        "UNIQUE(event_id, resource_id, unit_id) and an in-transaction replay check. "
        "That is a small variant of L1, not a new mechanism, so the verdict is ANALYZE "
        "when that residual is real. "
        f"numeric_thresholds_met={numeric_ok}. "
        f"dev scan {len(DEV_SEEDS)} seeds, {DEV_SUBJECTS} subjects, {DEV_ASSETS} assets. "
        "formal=false. E9/E10: no frozen definition in this checkout."
    )
    return {
        "experiment": "X4",
        "base_sha": head,
        "verdict": verdict,
        "counterexample": ", ".join(sorted(shared)) if shared else None,
        "strongest_baseline": strongest,
        "safety_gain": safety_gain_out,
        "utility_change": utility_change_out,
        "false_reject_rate": false_reject[CANDIDATE if verdict != "STOP" else strongest],
        "compute_overhead": overhead if verdict != "STOP" else (
            mean(latencies[strongest]) / min(mean(latencies[method]) for method in BASELINES)
        ),
        "literature_overlap": "pending-worker-E",
        "code_reuse": [
            "AccessRegistry.is_authorized",
            "AccessRegistry.with_policy_version",
            "RegistryHolder",
            "ProtectedTarget",
            "TargetRegistry",
            "check_release",
            "ReleaseGate.evaluate_and_reserve",
            "ReleaseGate.commit",
            "in-memory reserve/commit/cancel/holders_of/release_section",
        ],
        "dev_scan": True,
        "formal": False,
        "paths": {
            "run": str(HERE / "run.py"),
            "result": str(HERE / "RESULT.md"),
            "summary": str(RESULTS / "summary.json"),
            "e9_e10_status": str(RESULTS / "e9_e10_status.txt"),
        },
        "notes": notes,
        "failures": fails,
        "shared_failures": sorted(shared),
        "deterministic_violation_rate": {
            method: len(fails[method]) / N_CASES for method in (*BASELINES, CANDIDATE)
        },
        "false_reject_rate_by_method": false_reject,
        "utility_by_method": utility,
        "mean_latency_s": {method: mean(latencies[method]) for method in (*BASELINES, CANDIDATE)},
        "numeric_thresholds_met": numeric_ok,
        "candidate": {
            "name": CANDIDATE,
            "small_variant_of": "L1",
            "is_standard_lock_or_transaction": CANDIDATE_IS_STANDARD_LOCK_OR_TRANSACTION,
            "failures": sorted(candidate_fails),
        },
        "dev_scan_metrics": dev,
        "cases": case_table,
        "observed_release_gate": observed,
        "constants": {
            "PASS_MIN_ABS_SAFETY_GAIN": PASS_MIN_ABS_SAFETY_GAIN,
            "MAX_UTILITY_DROP": MAX_UTILITY_DROP,
            "MAX_OVERHEAD_RATIO": MAX_OVERHEAD_RATIO,
            "coalition_k": COALITION_K,
        },
    }


def result_markdown(summary: dict) -> str:
    lines = [
        "# X4 state consistency",
        "",
        f"Verdict: **{summary['verdict']}**.",
        f"Base SHA: `{summary['base_sha']}`.",
        "dev_scan: true. formal: false.",
        f"Strongest baseline: `{summary['strongest_baseline']}`.",
        f"Counterexample (unsafe under L0, L1, and L2): `{summary['counterexample']}`.",
        "",
        "L0, L1, and L2 are standard controls, not a new mechanism.",
        "L0 is a process-global lock around decide-and-commit.",
        "L1 is one stdlib sqlite3 transaction (`BEGIN IMMEDIATE`, rollback).",
        "L2 is optimistic concurrency control on a monotonic policy version.",
        "The candidate `event_key` only adds a unique event identity to L1.",
        "It is a small variant of L1, so it is not claimed as a new mechanism.",
        "",
        "## Deterministic cases",
        "",
        "| Method | Case | Safety violation | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary["cases"]:
        flag = "yes" if row["safety_violation"] else "no"
        lines.append(
            f"| {row['method']} | {row['case']} | {flag} | {row['detail']} |"
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Method | Violation rate | False-reject rate | Mean latency (s) | Dev witness violation rate |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for method in (*BASELINES, CANDIDATE):
        dev_rate = summary["dev_scan_metrics"][method]["witness_violation_rate"]
        lines.append(
            "| {method} | {vio:.3f} | {fr:.3f} | {lat:.6f} | {dev:.3f} |".format(
                method=method,
                vio=summary["deterministic_violation_rate"][method],
                fr=summary["false_reject_rate_by_method"][method],
                lat=summary["mean_latency_s"][method],
                dev=dev_rate,
            )
        )
    lines.extend(
        [
            "",
            f"Safety gain of event_key over {summary['strongest_baseline']}: {summary['safety_gain']:.3f}.",
            f"Utility change (serial delivery rate): {summary['utility_change']:.3f}.",
            f"False-reject rate reported in summary.json: {summary['false_reject_rate']:.3f}.",
            f"Compute overhead (event_key / strongest, or strongest / fastest if STOP): {summary['compute_overhead']:.3f}.",
            f"Numeric PASS gates met: {summary['numeric_thresholds_met']}.",
            "PASS also requires the candidate not be a standard lock, transaction, or small variant of L0-L2.",
            "",
            "Safety gain uses the seven deterministic cases. A case counts once.",
            "False-reject rate is the share of serial authorized single-unit releases that were denied.",
            "Those serial releases do not complete a witness. Duplicate replay that keeps one delivered row is not a false reject.",
            "Dev scan: 5 seeds, 8 subjects, 4 assets, one complementary pair per asset.",
            "The L2 pair reads both snapshots before either commit, so the version check is not saved by an accidental serial order.",
            "",
            "## ReleaseGate observation",
            "",
            "The gate ran on the in-memory store. It is not scored as L0, L1, or L2.",
            "",
            "```json",
            json.dumps(summary["observed_release_gate"], indent=2, sort_keys=True),
            "```",
            "",
            "## E9/E10",
            "",
            "BLOCKED: no frozen E9/E10 definition in this checkout.",
            "",
            "## Notes",
            "",
            summary["notes"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    semantic_self_check()
    RESULTS.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    status = RESULTS / "e9_e10_status.txt"
    status.write_text(
        "BLOCKED: no frozen E9/E10 definition in this checkout\n"
        "\n"
        f"Searched this checkout at {head}: git branch -a, filenames, and git paths.\n"
        "Branches include exp/e5-synthetic and exp/e6-eedi, not E9 or E10.\n"
        "Watermark stage9/stage10 scripts are not a frozen CA-PD E9/E10 protocol.\n"
        "No definition was invented.\n",
        encoding="utf-8",
    )
    with tempfile.TemporaryDirectory(prefix="x4-consistency-") as directory:
        rows = run_deterministic(directory)
        dev = run_dev_scan(directory)
        observed = observe_gate(directory)
    summary = build_summary(rows, dev, observed, head)
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "RESULT.md").write_text(result_markdown(summary), encoding="utf-8")
    print(json.dumps(
        {
            "verdict": summary["verdict"],
            "failures": summary["failures"],
            "shared_failures": summary["shared_failures"],
            "strongest_baseline": summary["strongest_baseline"],
            "safety_gain": summary["safety_gain"],
            "utility_change": summary["utility_change"],
            "false_reject_rate": summary["false_reject_rate"],
            "compute_overhead": summary["compute_overhead"],
            "head": head,
            "summary": str(RESULTS / "summary.json"),
        },
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
