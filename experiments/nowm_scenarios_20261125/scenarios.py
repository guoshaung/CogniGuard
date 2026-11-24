"""Non-degenerate teacher-knowledge and student-attribute scenarios.

Witness sizes are 3, 4, or 5. Both domains use the same request pattern.
The teacher placement witness overlaps unit ``a``; the student placement
witness uses signal ``z``, which principal A already holds. Decision code
does not read an allow/deny label.
"""

from __future__ import annotations

from dataclasses import dataclass

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.source_evidence import SourceEvidence
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from protection.student_profile.src.fopd.secret_targets import attribute_target

ORG = "school"
NOW = 50.0
PURPOSE = {"teacher": "teach", "student": "advise"}

# Role letters are the same incidence in both domains.
_RECEIPTS = {
    "A": ("a", "b", "u"),
    "B": ("c", "v"),
    "C": ("f",),
    "D": ("h",),
    "E": ("q", "r", "x", "y"),
}
_EXTRAS = (
    ("A", "d", "content"),
    ("B", "e", "content"),
    ("B", "g", "trusted_event"),
    ("D", "i", "content"),
)
_REQUESTS = (
    ("r1", "A", "c"),
    ("r2", "C", "c"),
    ("r3", "A", "g"),
    ("r4", "B", "a"),
    ("r5", "C", "h"),
    ("r6", "X", "a"),
    ("r7", "D", "b"),
    ("r8", "A", "e"),
    ("r9", "H", "p"),
    ("r10", "C", "m"),
)
_NAMES = {
    "teacher": {
        "A": "s1", "B": "s2", "C": "s3", "D": "s4", "E": "s5", "H": "s8", "X": "sx",
    },
    "student": {
        "A": "c1", "B": "t1", "C": "n1", "D": "k1", "E": "h5", "H": "h8", "X": "sx",
    },
}


@dataclass(frozen=True)
class Ask:
    request_id: str
    principal_id: str
    unit: tuple[str, str]


@dataclass(frozen=True)
class World:
    domain: str
    resource_id: str
    purpose: str
    registry: TargetRegistry
    access: AccessRegistry
    requests: tuple[Ask, ...]
    evidence: tuple[SourceEvidence, ...]
    receipt_units: dict[str, frozenset]


def _unit(resource_id: str, unit_id: str) -> tuple[str, str]:
    return (resource_id, unit_id)


def _evidence(
    evidence_id: str, principal: str, unit: tuple[str, str], channel: str,
) -> SourceEvidence:
    if channel == "trusted_event":
        return SourceEvidence(
            evidence_id=evidence_id,
            evidence_type="trusted_log",
            artifact_id=f"art-{evidence_id}",
            candidate_issuance_ids=(f"iss-{evidence_id}",),
            matched_knowledge_units=(unit,),
            confidence=1.0,
            verification_status="verified",
            trusted_event_id=f"evt-{evidence_id}",
            policy_version=1,
            holdings_asserted=True,
            holder_principal_id=principal,
        )
    if channel == "content":
        return SourceEvidence(
            evidence_id=evidence_id,
            evidence_type="watermark",
            artifact_id=f"art-{evidence_id}",
            candidate_issuance_ids=(f"iss-{evidence_id}",),
            matched_knowledge_units=(unit,),
            confidence=1.0,
            verification_status="verified",
            trusted_event_id=None,
            policy_version=1,
            holdings_asserted=True,
            holder_principal_id=principal,
        )
    raise ValueError(channel)


def _member_role(domain: str, principal: str, owner: str) -> str:
    if principal == owner:
        return "teacher" if domain == "teacher" else "student"
    if domain == "student" and principal != "sx":
        return "teacher"
    return "student"


def _access(domain: str, resource_id: str, names: dict[str, str]) -> AccessRegistry:
    owner = "lead" if domain == "teacher" else "stu"
    principals = [owner, *names.values()]
    memberships = [
        Membership(principal, ORG, _member_role(domain, principal, owner))
        for principal in principals
    ]
    grants = [
        AccessGrant(names[role], resource_id, PURPOSE[domain], 1)
        for role in ("A", "B", "C", "D", "E", "H")
    ]
    return AccessRegistry(
        [AssetOwnership(resource_id, owner, ORG, 1)],
        memberships,
        grants,
    )


def _targets(domain: str, resource_id: str) -> TargetRegistry:
    if domain == "teacher":
        owner = "lead"
        targets = (
            ProtectedTarget(
                "design", owner, ORG,
                (
                    frozenset(_unit(resource_id, item) for item in ("a", "b", "c")),
                    frozenset(_unit(resource_id, item) for item in ("c", "d", "e", "f")),
                ),
                kind="teaching_asset",
            ),
            ProtectedTarget(
                "rubric", owner, ORG,
                (
                    frozenset(_unit(resource_id, item) for item in ("b", "d", "g", "h", "i")),
                    frozenset(_unit(resource_id, item) for item in ("a", "e", "g")),
                ),
                kind="teaching_asset",
            ),
            ProtectedTarget(
                "placement", owner, ORG,
                (frozenset(_unit(resource_id, item) for item in ("a", "p", "q", "r", "x")),),
                kind="teaching_asset",
            ),
            ProtectedTarget(
                "lab", owner, ORG,
                (frozenset(_unit(resource_id, item) for item in ("m", "u", "v", "h", "y")),),
                kind="teaching_asset",
            ),
        )
        return TargetRegistry(targets)
    support = attribute_target(
        "stu", "support", [["a", "b", "c"], ["c", "d", "e", "f"]],
        owner_principal_id="stu", org_id=ORG,
    )
    family = attribute_target(
        "stu", "family", [["b", "d", "g", "h", "i"], ["a", "e", "g"]],
        owner_principal_id="stu", org_id=ORG,
    )
    placement = attribute_target(
        "stu", "placement", [["z", "p", "q", "r", "x"]],
        owner_principal_id="stu", org_id=ORG,
    )
    mobility = attribute_target(
        "stu", "mobility", [["m", "u", "v", "h", "y"]],
        owner_principal_id="stu", org_id=ORG,
    )
    return TargetRegistry((support, family, placement, mobility))


def build(domain: str) -> World:
    if domain not in _NAMES:
        raise ValueError(domain)
    names = _NAMES[domain]
    resource_id = "lesson" if domain == "teacher" else "profile:stu"
    receipts: dict[str, set[tuple[str, str]]] = {}
    for role, unit_ids in _RECEIPTS.items():
        principal = names[role]
        receipts.setdefault(principal, set()).update(
            _unit(resource_id, unit_id) for unit_id in unit_ids
        )
    if domain == "student":
        receipts[names["A"]].add(_unit(resource_id, "z"))
    evidence = []
    for index, (role, unit_id, channel) in enumerate(_EXTRAS, start=1):
        principal = names[role]
        unit = _unit(resource_id, unit_id)
        evidence.append(_evidence(f"{domain}-{index}", principal, unit, channel))
    requests = tuple(
        Ask(request_id, names[role], _unit(resource_id, unit_id))
        for request_id, role, unit_id in _REQUESTS
    )
    return World(
        domain=domain,
        resource_id=resource_id,
        purpose=PURPOSE[domain],
        registry=_targets(domain, resource_id),
        access=_access(domain, resource_id, names),
        requests=requests,
        evidence=tuple(evidence),
        receipt_units={name: frozenset(units) for name, units in receipts.items()},
    )


def target_ids(domain: str) -> tuple[str, ...]:
    if domain == "teacher":
        return ("design", "rubric", "placement", "lab")
    return ("stu/support", "stu/family", "stu/placement", "stu/mobility")


def witness_sizes(world: World) -> tuple[int, ...]:
    sizes = []
    for target_id in target_ids(world.domain):
        for witness in world.registry.get(target_id).witness_sets:
            sizes.append(len(witness))
    return tuple(sizes)
