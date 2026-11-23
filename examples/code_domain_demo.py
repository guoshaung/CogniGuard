"""Show the code-domain gate: two coworkers, then a third function.

Developer A already receives parse_jobs and score_job. Developer B asks for
assign_slots. With coalition size 2 the witness would be completed, so B gets
the signature and docstring. No education types are involved.

Requires a local MySQL server. Connection settings match the disclosure tests.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pymysql

from cogniguard.applications.code.assistant import CodeAssistant
from cogniguard.applications.code.assets import load_python_file
from cogniguard.applications.code.targets import load_code_targets
from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.targets import TargetRegistry
from cogniguard.runtime.disclosure_store import DisclosureStore
from cogniguard.runtime.release_gate import ReleaseGate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "cogniguard/tests/fixtures/private_scheduler.py"
WITNESSES = ROOT / "cogniguard/tests/fixtures/private_scheduler.targets.json"
RESOURCE_ID = "private-scheduler"
ORG_ID = "lab"
OWNER_ID = "scheduler-owner"
PURPOSE = "development"
BODY_MARKER = "ranked = sorted"


def main() -> None:
    settings = {
        "host": os.environ.get("COGNIGUARD_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("COGNIGUARD_MYSQL_PORT", "3306")),
        "user": os.environ.get("COGNIGUARD_MYSQL_USER", "root"),
        "password": os.environ.get("COGNIGUARD_MYSQL_PASSWORD", ""),
    }
    database = "cg_code_demo_" + uuid.uuid4().hex[:12]
    store = DisclosureStore(**settings, database=database)
    try:
        assets = load_python_file(SOURCE, RESOURCE_ID)
        registry = AccessRegistry(
            [AssetOwnership(RESOURCE_ID, OWNER_ID, ORG_ID, 1)],
            [
                Membership(OWNER_ID, ORG_ID, "admin"),
                Membership("dev-a", ORG_ID, "admin"),
                Membership("dev-b", ORG_ID, "admin"),
            ],
            [
                AccessGrant("dev-a", RESOURCE_ID, PURPOSE, 1),
                AccessGrant("dev-b", RESOURCE_ID, PURPOSE, 1),
            ],
        )
        targets = TargetRegistry(
            load_code_targets(
                WITNESSES,
                resource_id=RESOURCE_ID,
                owner_principal_id=OWNER_ID,
                org_id=ORG_ID,
            )
        )
        gate = ReleaseGate(
            store,
            access_registry=registry,
            target_registry=targets,
            coalition_k=2,
        )
        developer_a = _assistant(gate, assets, "dev-a", "session-a")
        developer_b = _assistant(gate, assets, "dev-b", "session-b")
        for name in ("parse_jobs", "score_job"):
            reply = developer_a.show_function(name)
            print(f"A {name}: {reply.mode}")
        reply = developer_b.show_function("assign_slots")
        print(f"B assign_slots: {reply.mode}")
        print(reply.text)
        print(f"body_included={BODY_MARKER in reply.text}")
    finally:
        store.close()
        admin = pymysql.connect(**settings, autocommit=True, connect_timeout=3)
        try:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")
        finally:
            admin.close()


def _assistant(gate: ReleaseGate, assets, recipient: str, session_id: str) -> CodeAssistant:
    return CodeAssistant(
        gate,
        assets,
        recipient_principal_id=recipient,
        acting_org_id=ORG_ID,
        agent_principal_id="code-assistant",
        session_id=session_id,
        purpose=PURPOSE,
    )


if __name__ == "__main__":
    main()
