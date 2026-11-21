"""SQLite audit store for teacher DAG runs; never persists prompts or content.

The schema deliberately contains only run topology, decisions and numeric
metrics. SQLite is used because it is built in and needs no weak credentials.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .catalog import PromptSpec
from .skills import SkillSpec

SCHEMA_VERSION = 4


class DatabasePromptLibrary:
    def __init__(self, catalog_hash: str, prompts: dict[tuple[str, str], PromptSpec]):
        self.sha256 = catalog_hash
        self._prompts = prompts

    def get(self, teacher: str, version: str) -> PromptSpec:
        try:
            return self._prompts[teacher, version]
        except KeyError:
            raise ValueError("Unknown database teacher/prompt version") from None

    def inventory(self) -> list[dict[str, str]]:
        return [
            {
                "teacher": teacher,
                "version": version,
                "display_name": item.display_name,
                "sha256": item.sha256,
            }
            for (teacher, version), item in sorted(self._prompts.items())
        ]


class DatabaseSkillLibrary:
    def __init__(self, catalog_hash: str, skills: dict[str, SkillSpec]):
        self.sha256 = catalog_hash
        self._skills = skills

    def get(self, teacher: str) -> SkillSpec:
        try:
            return self._skills[teacher]
        except KeyError:
            raise ValueError("Unknown database teaching skill") from None

    def inventory(self) -> list[dict[str, str]]:
        return [
            {
                "teacher": teacher,
                "version": item.version,
                "title": item.title,
                "sha256": item.sha256,
            }
            for teacher, item in sorted(self._skills.items())
        ]


class SQLiteTeacherAuditStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3, SCHEMA_VERSION):
                raise RuntimeError("Unsupported teacher audit database schema")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS teacher_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    team TEXT NOT NULL,
                    team_hash TEXT NOT NULL,
                    prompt_library_hash TEXT NOT NULL,
                    skill_catalog_hash TEXT,
                    trust_mode TEXT NOT NULL,
                    handoff_guard_mode TEXT NOT NULL,
                    completed INTEGER NOT NULL,
                    teachers_executed INTEGER NOT NULL,
                    teachers_blocked INTEGER NOT NULL,
                    edges_accepted INTEGER NOT NULL,
                    edges_blocked INTEGER NOT NULL,
                    content_blocked INTEGER NOT NULL,
                    model_calls INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teacher_nodes (
                    run_id TEXT NOT NULL REFERENCES teacher_runs(run_id),
                    node_id TEXT NOT NULL,
                    teacher TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_chars INTEGER NOT NULL,
                    PRIMARY KEY (run_id, node_id)
                );
                CREATE TABLE IF NOT EXISTS teacher_edges (
                    run_id TEXT NOT NULL REFERENCES teacher_runs(run_id),
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    accepted INTEGER NOT NULL,
                    origin_valid INTEGER NOT NULL,
                    chain_valid INTEGER NOT NULL,
                    content_guard_decision TEXT NOT NULL,
                    reason_codes TEXT NOT NULL,
                    source_chars INTEGER NOT NULL,
                    delivered_chars INTEGER NOT NULL,
                    PRIMARY KEY (run_id, source, target)
                );
                CREATE TABLE IF NOT EXISTS teacher_final_decisions (
                    run_id TEXT PRIMARY KEY REFERENCES teacher_runs(run_id),
                    decision TEXT NOT NULL,
                    reason_codes TEXT NOT NULL,
                    fallback_used INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS teacher_prompt_versions (
                    catalog_hash TEXT NOT NULL,
                    teacher TEXT NOT NULL,
                    version TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    system_text TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    PRIMARY KEY (catalog_hash, teacher, version)
                );
                CREATE TABLE IF NOT EXISTS teacher_skill_versions (
                    catalog_hash TEXT NOT NULL,
                    teacher TEXT NOT NULL,
                    version TEXT NOT NULL,
                    title TEXT NOT NULL,
                    instructions TEXT NOT NULL,
                    spec_hash TEXT NOT NULL,
                    PRIMARY KEY (catalog_hash, teacher)
                );
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(teacher_runs)")}
            if "skill_catalog_hash" not in columns:
                db.execute("ALTER TABLE teacher_runs ADD COLUMN skill_catalog_hash TEXT")
            if version < SCHEMA_VERSION:
                db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 15000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def save_run(self, report: dict) -> None:
        run_id = report["run_id"]
        metrics = report["metrics"]
        with self._connect() as db:
            db.execute(
                """INSERT INTO teacher_runs (
                run_id, created_at, team, team_hash, prompt_library_hash, skill_catalog_hash,
                trust_mode, handoff_guard_mode, completed, teachers_executed,
                teachers_blocked, edges_accepted, edges_blocked, content_blocked, model_calls
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    report["team"],
                    report["team_hash"],
                    report["prompt_library_hash"],
                    report.get("skill_library_hash"),
                    report["trust_mode"],
                    report["handoff_guard_mode"],
                    int(bool(metrics["completed"])),
                    int(metrics["teachers_executed"]),
                    int(metrics["teachers_blocked"]),
                    int(metrics["edges_accepted"]),
                    int(metrics["edges_blocked"]),
                    int(metrics["edges_content_blocked"]),
                    int(metrics["model_calls"]),
                ),
            )
            db.executemany(
                """INSERT INTO teacher_nodes VALUES (?,?,?,?,?,?)""",
                [
                    (
                        run_id,
                        item["node"],
                        item["teacher"],
                        item["backend"],
                        item["status"],
                        len(item.get("text", "")),
                    )
                    for item in report["nodes"]
                ],
            )
            db.executemany(
                """INSERT INTO teacher_edges VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [
                    (
                        run_id,
                        item["source"],
                        item["target"],
                        int(bool(item["accepted"])),
                        int(bool(item["origin_valid"])),
                        int(bool(item["chain_valid"])),
                        item.get("content_guard_decision", "not_checked"),
                        json.dumps(item.get("reasons", []) + item.get("content_guard_reasons", [])),
                        int(item.get("source_chars", 0)),
                        int(item.get("delivered_chars", 0)),
                    )
                    for item in report["edges"]
                ],
            )
            final = report.get("final_guard", {})
            db.execute(
                "INSERT INTO teacher_final_decisions VALUES (?,?,?,?)",
                (
                    run_id,
                    final.get("decision", "not_checked"),
                    json.dumps(final.get("reasons", [])),
                    int(bool(final.get("fallback_used", False))),
                ),
            )

    def sync_catalogs(self, prompts, skills) -> None:
        """Seed a trusted YAML snapshot; reject in-place mutation of an existing hash."""
        with self._connect() as db:
            for item in prompts.inventory():
                spec = prompts.get(item["teacher"], item["version"])
                expected = (spec.display_name, spec.system, spec.sha256)
                key = (prompts.sha256, spec.teacher, spec.version)
                row = db.execute(
                    """SELECT display_name, system_text, spec_hash
                                    FROM teacher_prompt_versions
                                    WHERE catalog_hash=? AND teacher=? AND version=?""",
                    key,
                ).fetchone()
                if row is not None and row != expected:
                    raise RuntimeError("Stored teacher prompt does not match trusted snapshot")
                if row is None:
                    db.execute(
                        "INSERT INTO teacher_prompt_versions VALUES (?,?,?,?,?,?)",
                        (*key, *expected),
                    )
            for item in skills.inventory():
                spec = skills.get(item["teacher"])
                expected = (spec.version, spec.title, spec.instructions, spec.sha256)
                key = (skills.sha256, spec.teacher)
                row = db.execute(
                    """SELECT version, title, instructions, spec_hash
                                    FROM teacher_skill_versions
                                    WHERE catalog_hash=? AND teacher=?""",
                    key,
                ).fetchone()
                if row is not None and row != expected:
                    raise RuntimeError("Stored teaching skill does not match trusted snapshot")
                if row is None:
                    db.execute(
                        "INSERT INTO teacher_skill_versions VALUES (?,?,?,?,?,?)", (*key, *expected)
                    )

    def load_prompt_catalog(self, catalog_hash: str, *, expected_count: int | None = None):
        with self._connect() as db:
            rows = db.execute(
                """SELECT teacher, version, display_name, system_text, spec_hash
                                 FROM teacher_prompt_versions WHERE catalog_hash=?""",
                (catalog_hash,),
            ).fetchall()
        if not rows or expected_count is not None and len(rows) != expected_count:
            raise RuntimeError("Teacher prompt catalog is incomplete")
        prompts = {}
        for teacher, version, display_name, system, expected_hash in rows:
            spec = PromptSpec(teacher, display_name, version, system)
            if spec.sha256 != expected_hash:
                raise RuntimeError("Teacher prompt catalog integrity check failed")
            prompts[teacher, version] = spec
        return DatabasePromptLibrary(catalog_hash, prompts)

    def load_skill_catalog(self, catalog_hash: str, *, expected_count: int | None = None):
        with self._connect() as db:
            rows = db.execute(
                """SELECT teacher, version, title, instructions, spec_hash
                                 FROM teacher_skill_versions WHERE catalog_hash=?""",
                (catalog_hash,),
            ).fetchall()
        if not rows or expected_count is not None and len(rows) != expected_count:
            raise RuntimeError("Teaching skill catalog is incomplete")
        skills = {}
        for teacher, version, title, instructions, expected_hash in rows:
            spec = SkillSpec(teacher, version, title, instructions)
            if spec.sha256 != expected_hash:
                raise RuntimeError("Teaching skill catalog integrity check failed")
            skills[teacher] = spec
        return DatabaseSkillLibrary(catalog_hash, skills)

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            return {
                "runs": db.execute("SELECT COUNT(*) FROM teacher_runs").fetchone()[0],
                "nodes": db.execute("SELECT COUNT(*) FROM teacher_nodes").fetchone()[0],
                "edges": db.execute("SELECT COUNT(*) FROM teacher_edges").fetchone()[0],
                "content_blocked": db.execute(
                    "SELECT COUNT(*) FROM teacher_edges WHERE content_guard_decision = 'blocked'"
                ).fetchone()[0],
                "final_blocked": db.execute(
                    "SELECT COUNT(*) FROM teacher_final_decisions WHERE decision = 'blocked'"
                ).fetchone()[0],
                "prompt_versions": db.execute(
                    "SELECT COUNT(*) FROM teacher_prompt_versions"
                ).fetchone()[0],
                "skill_versions": db.execute(
                    "SELECT COUNT(*) FROM teacher_skill_versions"
                ).fetchone()[0],
            }
