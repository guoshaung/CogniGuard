"""Disclosure receipt. Persistence lives in cogniguard.runtime.disclosure_store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DisclosureReceipt:
    receipt_id: str
    resource_id: str
    unit_id: str
    recipient_principal_id: str
    acting_org_id: str
    agent_principal_id: str
    session_id: str
    policy_version: int
    status: Literal["reserved", "delivered", "cancelled"]
    content_sha256: str
    created_at: float
