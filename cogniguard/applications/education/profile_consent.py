"""Session-scoped, trusted-server prototype for per-field teaching consent.

The caller must authenticate the student before recording a decision. A session
token is not identity verification. Only trusted code constructs the policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4

from protection.common.schemas import StudentProfile


@dataclass(frozen=True)
class ProfileConsentPolicy:
    version: str
    agent: str
    purpose: str
    fields: Mapping[str, str]

    def __post_init__(self):
        if not all(isinstance(x, str) and x.strip() for x in (self.version, self.agent, self.purpose)):
            raise ValueError("Policy version, agent and purpose must be non-empty")
        rules = dict(self.fields)
        if not rules or any(not isinstance(k, str) or not k or v not in {"automatic", "ask", "deny"}
                            for k, v in rules.items()):
            raise ValueError("Field policies must be automatic, ask or deny")
        object.__setattr__(self, "fields", MappingProxyType(rules))


def _state(state):
    return state.setdefault("profile_consent", {"revision": 0, "grants": {}, "pending": {}})


def _key(policy, field):
    # JSON encoding avoids ambiguous concatenation of caller-supplied names.
    import json
    return json.dumps([policy.version, policy.agent, policy.purpose, field], ensure_ascii=False)


def filter_profile(profile, policy, state):
    """Build a field-minimized view; pending requests never include values."""
    consent = _state(state)
    allowed, requests = [], []
    for field in sorted({record.type for record in profile.profile_records}):
        rule = policy.fields.get(field, "deny")
        key = _key(policy, field)
        if rule == "automatic" or (rule == "ask" and consent["grants"].get(key) == "allow"):
            allowed.append(field)
        elif rule == "ask" and consent["grants"].get(key) != "deny":
            found = next((item for item in consent["pending"].values() if item["key"] == key), None)
            if found is None:
                request_id = uuid4().hex
                found = {"request_id": request_id, "key": key, "field": field,
                         "agent": policy.agent, "purpose": policy.purpose,
                         "policy_version": policy.version}
                consent["pending"][request_id] = found
            requests.append({k: v for k, v in found.items() if k != "key"})
    view = StudentProfile(profile.student_id, dict(profile.local_only_fields),
                          [record for record in profile.profile_records if record.type in allowed])
    return view, requests


def resolve_profile_consent(session, request_id, *, verified_student_id, approve):
    """Record a UI decision after the hosting application authenticates the student."""
    if not isinstance(approve, bool):
        raise ValueError("Consent decision must be a boolean")
    with session.transaction() as state:
        if not verified_student_id or state.get("education_subject") != verified_student_id:
            raise PermissionError("Consent subject does not match the trusted session")
        consent = _state(state)
        pending = consent["pending"].pop(request_id, None)
        if pending is None:
            raise ValueError("Unknown or already resolved consent request")
        consent["grants"][pending["key"]] = "allow" if approve else "deny"
        consent["revision"] += 1


def revoke_profile_consent(session, policy, field, *, verified_student_id):
    """Revoke an explicit grant; already delivered content cannot be recalled."""
    if policy.fields.get(field) != "ask":
        raise ValueError("Only explicit consent can be revoked through this interface")
    with session.transaction() as state:
        if not verified_student_id or state.get("education_subject") != verified_student_id:
            raise PermissionError("Consent subject does not match the trusted session")
        consent = _state(state)
        key = _key(policy, field)
        consent["grants"][key] = "deny"
        consent["pending"] = {
            request_id: request for request_id, request in consent["pending"].items()
            if request["key"] != key
        }
        consent["revision"] += 1
