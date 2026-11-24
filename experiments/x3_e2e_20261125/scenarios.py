"""Controlled X3-E2E fixtures. These rows are not the missing server pilot."""

from __future__ import annotations

from dataclasses import dataclass, field

from cogniguard.governance.access_policy import AccessGrant, AccessRegistry
from cogniguard.governance.principals import AssetOwnership, Membership
from cogniguard.governance.source_evidence import SourceEvidence
from cogniguard.governance.source_state import IssuanceBinding, ShadowRequest
from cogniguard.governance.targets import ProtectedTarget, TargetRegistry
from protection.student_profile.src.fopd.secret_targets import attribute_target

NOW = 50.0
ORG = "alpha"
FIVE = (
    "s1-same-perm-meta",
    "s2-other-grantee",
    "s4-teach-read",
    "s3-live-copy",
    "s6-external-copy",
)


def _unit(resource_id: str, unit_id: str = "body") -> tuple[str, str]:
    return (resource_id, unit_id)


def _evidence(
    evidence_id: str,
    evidence_type: str,
    artifact_id: str,
    issuance_ids: tuple[str, ...] = (),
    units: tuple[tuple[str, str], ...] = (),
    *,
    confidence: float = 0.0,
    status: str = "verified",
    event: str | None = None,
    version: int = 1,
    asserted: bool = False,
    holder: str | None = None,
) -> SourceEvidence:
    payload = {
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "artifact_id": artifact_id,
        "candidate_issuance_ids": list(issuance_ids),
        "matched_knowledge_units": [list(unit) for unit in units],
        "confidence": confidence,
        "verification_status": status,
        "trusted_event_id": event,
        "policy_version": version,
    }
    if asserted:
        payload["holdings_asserted"] = True
    if holder is not None:
        payload["holder_principal_id"] = holder
    return SourceEvidence.from_dict(payload)


def bindings() -> dict[str, IssuanceBinding]:
    def one(
        issuance_id: str,
        resource_id: str,
        grantee: str,
        purpose: str,
        revoked: bool = False,
        units: tuple[tuple[str, str], ...] | None = None,
    ):
        chosen = units or (_unit(resource_id), _unit(resource_id, "rest"))
        return IssuanceBinding(issuance_id, resource_id, grantee, chosen, (purpose,), revoked)

    rows = [
        one("iss-a1-u2", "A1", "u2", "education"),
        one("iss-a1-u1", "A1", "u1", "education"),
        one("iss-a2-u3", "A2", "u3", "audit"),
        one("iss-a2-u1", "A2", "u1", "education"),
        one("iss-a3-teach", "A3", "u4", "teaching"),
        one("iss-a3-research", "A3", "u4", "research"),
        one("iss-a4-new", "A4", "u5", "education"),
        one("iss-a4-old", "A4", "u5", "education", True),
        one("iss-a7-ext", "A7", "u2", "education"),
        one("iss-a7-int", "A7", "u2", "education"),
        one("iss-edu-s1", "edu", "s1", "education", units=(_unit("edu", "a"), _unit("edu", "b"))),
        one(
            "iss-edu-partner",
            "edu",
            "partner",
            "education",
            units=(_unit("edu", "a"), _unit("edu", "b")),
        ),
        one("iss-doc2", "doc2", "u2", "education"),
        one("iss-doc3", "doc3", "u2", "education"),
        one("iss-key", "svc-key", "e1", "review"),
        one("iss-readme", "svc-readme", "e1", "review"),
        one("iss-r1", "R1", "u2", "education"),
        one("iss-r2", "R2", "u2", "education"),
    ]
    return {row.issuance_id: row for row in rows}


def _principals() -> list[Membership]:
    names = ("u1", "u2", "u3", "u4", "u5", "partner", "outsider", "e1", "s1", "s2")
    return [Membership(name, ORG, "student") for name in names]


def _grants(version_for: dict[str, int] | None = None, expired: tuple[str, ...] = ()) -> list[AccessGrant]:
    specs = [
        ("u2", "A1", "education"),
        ("u1", "A1", "education"),
        ("u3", "A2", "audit"),
        ("u1", "A2", "education"),
        ("u4", "A3", "teaching"),
        ("u4", "A3", "research"),
        ("u5", "A4", "education"),
        ("u2", "A7", "education"),
        ("s1", "edu", "education"),
        ("s2", "edu", "education"),
        ("partner", "edu", "education"),
        ("u2", "doc2", "education"),
        ("u2", "doc3", "education"),
        ("e1", "svc-key", "review"),
        ("e1", "svc-readme", "review"),
        ("s1", "profile:stu_001", "tutoring"),
        ("s2", "profile:stu_001", "tutoring"),
        ("u2", "R1", "education"),
        ("u2", "R2", "education"),
    ]
    grants = []
    for principal, resource_id, purpose in specs:
        version = 1 if version_for is None else version_for.get(resource_id, 1)
        expires = NOW if resource_id in expired else None
        grants.append(AccessGrant(principal, resource_id, purpose, 1, expires_at=expires))
        if version != 1:
            continue
    return grants


def make_registry(
    *,
    ownership_version: dict[str, int] | None = None,
    expired: tuple[str, ...] = (),
) -> AccessRegistry:
    versions = ownership_version or {}
    resources = [
        "A1", "A2", "A3", "A4", "A7", "edu", "doc2", "doc3",
        "svc-key", "svc-readme", "profile:stu_001", "R1", "R2",
    ]
    ownerships = [
        AssetOwnership(resource_id, "publisher", ORG, versions.get(resource_id, 1))
        for resource_id in resources
    ]
    return AccessRegistry(ownerships, _principals(), _grants(expired=expired))


def target_registry() -> TargetRegistry:
    targets = []
    paired = (
        "A1", "A2", "A3", "A4", "A7", "doc2", "doc3", "svc-key", "svc-readme", "R1", "R2",
    )
    for resource_id in paired:
        targets.append(
            ProtectedTarget(
                f"{resource_id}-secret",
                "publisher",
                ORG,
                (frozenset({_unit(resource_id), _unit(resource_id, "rest")}),),
            )
        )
    targets.append(
        ProtectedTarget(
            "edu-secret",
            "publisher",
            ORG,
            (frozenset({_unit("edu", "a"), _unit("edu", "b")}),),
        )
    )
    targets.append(
        attribute_target(
            "stu_001",
            "attendance_risk",
            [["p2", "p4"]],
            owner_principal_id="publisher",
            org_id=ORG,
        )
    )
    return TargetRegistry(targets)


@dataclass
class Scenario:
    scenario_id: str
    group: str
    request: ShadowRequest
    registry: AccessRegistry
    true_issuance_ids: tuple[str, ...]
    true_retained: tuple[tuple[str, str], ...]
    channels: dict[str, tuple[SourceEvidence, ...]]
    knowledge: dict[str, frozenset] = field(default_factory=dict)
    true_knowledge: dict[str, frozenset] = field(default_factory=dict)
    note: str = ""
    origin: str = "controlled_fixture"


def _request(principal: str, resource_id: str, purpose: str, units: tuple[tuple[str, str], ...]):
    return ShadowRequest(principal, resource_id, purpose, ORG, units, NOW)


def _ideal(
    scenario_id: str,
    true_ids: tuple[str, ...],
    retained: tuple[tuple[str, str], ...],
    true_knowledge: dict[str, frozenset],
    book: dict[str, IssuanceBinding],
) -> tuple[SourceEvidence, ...]:
    rows = []
    for issuance_id in true_ids:
        binding = book[issuance_id]
        rows.append(
            _evidence(
                f"{scenario_id}-ideal-{issuance_id}",
                "ideal",
                scenario_id,
                (issuance_id,),
                retained,
                event=f"{scenario_id}-oracle",
                asserted=True,
                holder=binding.grantee_principal_id,
            )
        )
    for holder, units in true_knowledge.items():
        if not units:
            continue
        rows.append(
            _evidence(
                f"{scenario_id}-ideal-hold-{holder}",
                "ideal",
                scenario_id,
                (),
                tuple(sorted(units)),
                event=f"{scenario_id}-hold-{holder}",
                asserted=True,
                holder=holder,
            )
        )
    return tuple(rows)


def _case(
    scenario_id: str,
    group: str,
    principal: str,
    resource_id: str,
    purpose: str,
    units: tuple[tuple[str, str], ...],
    true_ids: tuple[str, ...],
    retained: tuple[tuple[str, str], ...],
    channels: dict[str, tuple[SourceEvidence, ...]],
    *,
    registry: AccessRegistry | None = None,
    knowledge: dict | None = None,
    true_knowledge: dict | None = None,
    note: str = "",
    book: dict[str, IssuanceBinding],
) -> Scenario:
    store = knowledge or {}
    truth = true_knowledge if true_knowledge is not None else store
    ideal = _ideal(scenario_id, true_ids, retained, truth, book)
    merged = dict(channels)
    merged["ideal"] = ideal
    return Scenario(
        scenario_id,
        group,
        _request(principal, resource_id, purpose, units),
        registry if registry is not None else make_registry(),
        true_ids,
        retained,
        merged,
        store,
        truth,
        note,
    )


def build_scenarios() -> list[Scenario]:
    """Same propagation artifact for every arm. Channels differ by what they can see."""
    book = bindings()
    base = make_registry()
    body = lambda resource_id: (_unit(resource_id),)  # noqa: E731
    scenarios: list[Scenario] = []

    def add(scenario_id, group, principal, resource_id, purpose, true_ids, channels, **kwargs):
        units = kwargs.pop("units", body(resource_id))
        retained = kwargs.pop("retained", units)
        scenarios.append(
            _case(
                scenario_id,
                group,
                principal,
                resource_id,
                purpose,
                units,
                true_ids,
                retained,
                channels,
                book=book,
                **kwargs,
            )
        )

    # Historical X3 flips. The artifact does not carry a credential except where noted.
    # iss-a7-int is the same AccessRegistry grant as iss-a7-ext; redistribution is not reimplemented.
    x3 = [
        ("s1-same-perm-meta", "u2", "A1", "education", ("iss-a1-u2",), "meta keeps an issuance id; that id is not trusted"),
        ("s2-other-grantee", "u3", "A2", "audit", ("iss-a2-u3",), "metadata and receipt stripped"),
        ("s4-teach-read", "u4", "A3", "teaching", ("iss-a3-teach",), "metadata and receipt stripped"),
        ("s3-live-copy", "u5", "A4", "education", ("iss-a4-new",), "revoked sibling iss-a4-old is not this copy"),
        ("s6-external-copy", "u2", "A7", "education", ("iss-a7-ext",), "boundary drops metadata; registry has no redistribution field"),
    ]
    for scenario_id, principal, resource_id, purpose, true_ids, note in x3:
        mark = _evidence(
            f"{scenario_id}-mark",
            "watermark",
            scenario_id,
            true_ids,
            body(resource_id),
            confidence=0.99,
            event="mark-only",
        )
        add(
            scenario_id,
            "x3",
            principal,
            resource_id,
            purpose,
            true_ids,
            {"watermark": (mark,)},
            note=note,
        )

    add(
        "same-text-two-issuances",
        "propagation",
        "u4",
        "A3",
        "teaching",
        ("iss-a3-teach",),
        {
            "fingerprint": (
                _evidence(
                    "same-fp",
                    "fingerprint",
                    "same-text",
                    ("iss-a3-teach", "iss-a3-research"),
                    body("A3"),
                    confidence=1.0,
                ),
            ),
            "watermark": (
                _evidence("same-mark", "watermark", "same-text", ("iss-a3-teach",), body("A3"), confidence=0.7),
            ),
            "signed_credential": (
                _evidence("same-cred", "signed_credential", "same-text", ("iss-a3-teach",), body("A3")),
            ),
        },
        note="one body, education and research issuances; the credential names teaching",
    )
    add(
        "research-on-teaching-copy",
        "propagation",
        "u4",
        "A3",
        "research",
        ("iss-a3-teach",),
        {
            "signed_credential": (
                _evidence("teach-cred", "signed_credential", "teach-copy", ("iss-a3-teach",), body("A3")),
            ),
            "watermark": (
                _evidence(
                    "teach-mark",
                    "watermark",
                    "teach-copy",
                    ("iss-a3-research",),
                    body("A3"),
                    confidence=0.8,
                ),
            ),
        },
        note="wrong mark says research; the true copy is the teaching issuance",
    )
    for rounds, confidence in ((1, 0.9), (3, 0.5), (5, 0.2)):
        add(
            f"rounds-{rounds}",
            "propagation",
            "u2",
            "A1",
            "education",
            ("iss-a1-u2",),
            {
                "watermark": (
                    _evidence(
                        f"rounds-{rounds}-mark",
                        "watermark",
                        "rounds",
                        ("iss-a1-u2",),
                        body("A1"),
                        confidence=confidence,
                    ),
                ),
                "trusted_log": (
                    _evidence(
                        f"rounds-{rounds}-log",
                        "trusted_log",
                        "rounds",
                        ("iss-a1-u2",),
                        body("A1"),
                        event=f"issue-a1-{rounds}",
                        holder="u2",
                    ),
                ),
            },
            note=f"controlled mark confidence {confidence} after {rounds} hops; the log does not decay",
        )
    add(
        "summary-credential-kept",
        "propagation",
        "u2",
        "A1",
        "education",
        ("iss-a1-u2",),
        {
            "signed_credential": (
                _evidence("sum-cred", "signed_credential", "summary", ("iss-a1-u2",), body("A1")),
            ),
        },
        note="summary keeps the embedded credential",
    )
    add(
        "paraphrase-credential-lost",
        "propagation",
        "u2",
        "A1",
        "education",
        ("iss-a1-u2",),
        {
            "watermark": (
                _evidence("para-mark", "watermark", "paraphrase", ("iss-a1-u2",), (), confidence=0.15),
            ),
        },
        note="paraphrase drops the credential; a weak mark remains",
    )
    add(
        "fusion-two-sources",
        "propagation",
        "u2",
        "R1",
        "education",
        ("iss-r1", "iss-r2"),
        {
            "trusted_log": (
                _evidence("fuse-1", "trusted_log", "fusion", ("iss-r1",), (_unit("R1"),), event="fuse-r1", holder="u2"),
                _evidence("fuse-2", "trusted_log", "fusion", ("iss-r2",), (_unit("R2"),), event="fuse-r2", holder="u2"),
            ),
            "watermark": (
                _evidence("fuse-mark", "watermark", "fusion", ("iss-r1", "iss-r2"), (_unit("R1"), _unit("R2")), confidence=0.6),
            ),
        },
        units=(_unit("R1"), _unit("R2")),
        retained=(_unit("R1"), _unit("R2")),
        note="derived text keeps both source logs",
    )
    add(
        "metadata-missing",
        "propagation",
        "u2",
        "A1",
        "education",
        ("iss-a1-u2",),
        {"watermark": (_evidence("meta-mark", "watermark", "no-meta", ("iss-a1-u2",), body("A1"), confidence=0.4),)},
        note="no source metadata channel exists on this artifact",
    )
    add(
        "residual-mark-knowledge-gone",
        "propagation",
        "u2",
        "doc2",
        "education",
        ("iss-doc2",),
        {
            "signed_credential": (
                _evidence("resid-cred", "signed_credential", "residual", ("iss-doc2",)),
            ),
            "watermark": (
                _evidence(
                    "resid-mark",
                    "watermark",
                    "residual",
                    ("iss-doc2",),
                    (),
                    confidence=0.95,
                    asserted=True,
                ),
            ),
        },
        retained=(),
        note="credential and mark remain; the knowledge check asserts no units",
    )
    add(
        "detector-false-empty",
        "propagation",
        "u2",
        "doc2",
        "education",
        ("iss-doc2",),
        {
            "signed_credential": (
                _evidence("false-cred", "signed_credential", "false-empty", ("iss-doc2",), body("doc2")),
            ),
            "watermark": (
                _evidence(
                    "false-mark",
                    "watermark",
                    "false-empty",
                    ("iss-doc2",),
                    (),
                    confidence=0.7,
                    asserted=True,
                ),
            ),
        },
        note="units are still present; the controlled mark falsely asserts they are gone",
    )
    add(
        "copied-mark-wrong-grantee",
        "propagation",
        "outsider",
        "A1",
        "education",
        ("iss-a1-u2",),
        {
            "watermark": (
                _evidence("copy-mark", "watermark", "copied", ("iss-a1-u2",), body("A1"), confidence=1.0),
            ),
        },
        note="outsider has no grant; the copied mark names u2",
    )
    add(
        "independent-generation",
        "propagation",
        "u2",
        "doc3",
        "education",
        ("iss-doc3",),
        {
            "fingerprint": (
                _evidence(
                    "indep-fp",
                    "fingerprint",
                    "independent",
                    ("iss-a1-u2",),
                    body("doc3"),
                    confidence=1.0,
                ),
            ),
        },
        note="same units generated independently; fingerprint collides with A1 and is not a hop",
    )
    add(
        "grant-expired",
        "propagation",
        "u2",
        "doc2",
        "education",
        ("iss-doc2",),
        {
            "signed_credential": (
                _evidence("exp-cred", "signed_credential", "expired", ("iss-doc2",), body("doc2")),
            ),
        },
        registry=make_registry(expired=("doc2",)),
        note="the grant's expires_at equals now, so the registry denies",
    )
    add(
        "policy-version-bump",
        "software",
        "e1",
        "svc-key",
        "review",
        ("iss-key",),
        {
            "signed_credential": (
                _evidence("bump-cred", "signed_credential", "bumped", ("iss-key",), body("svc-key")),
            ),
        },
        registry=make_registry(ownership_version={"svc-key": 2}),
        note="ownership policy is 2; the grant and the credential stay at version 1",
    )
    add(
        "readme-stays-authorized",
        "software",
        "e1",
        "svc-readme",
        "review",
        ("iss-readme",),
        {},
        registry=make_registry(ownership_version={"svc-key": 2}),
        note="the key policy bump does not revoke the readme grant",
    )
    add(
        "unrecorded-share",
        "education",
        "s1",
        "edu",
        "education",
        ("iss-edu-s1",),
        {
            "watermark": (
                _evidence(
                    "share-mark",
                    "watermark",
                    "share",
                    ("iss-edu-partner",),
                    (_unit("edu", "b"),),
                    confidence=0.85,
                    asserted=True,
                    holder="partner",
                ),
            ),
            "signed_credential": (
                _evidence("share-cred", "signed_credential", "share", ("iss-edu-s1",), (_unit("edu", "a"),)),
            ),
            "trusted_log": (
                _evidence(
                    "share-self",
                    "trusted_log",
                    "share",
                    ("iss-edu-s1",),
                    (_unit("edu", "a"),),
                    event="edu-issue",
                    holder="s1",
                ),
                _evidence(
                    "share-partner",
                    "trusted_log",
                    "share",
                    ("iss-edu-partner",),
                    (_unit("edu", "b"),),
                    event="edu-forward",
                    holder="partner",
                ),
            ),
        },
        units=(_unit("edu", "a"),),
        retained=(_unit("edu", "a"),),
        true_knowledge={"partner": frozenset({_unit("edu", "b")})},
        note="partner already holds unit b; only a trusted log may enter that holding",
    )
    add(
        "edu-one-unit",
        "education",
        "s1",
        "edu",
        "education",
        ("iss-edu-s1",),
        {
            "trusted_log": (
                _evidence(
                    "one-log",
                    "trusted_log",
                    "one",
                    ("iss-edu-s1",),
                    (_unit("edu", "a"),),
                    event="edu-one",
                    holder="s1",
                ),
            ),
        },
        units=(_unit("edu", "a"),),
        retained=(_unit("edu", "a"),),
        note="one witness member; k=2 does not finish the target",
    )
    add(
        "edu-completing-unit",
        "education",
        "s2",
        "edu",
        "education",
        ("iss-edu-s1",),
        {},
        units=(_unit("edu", "b"),),
        retained=(_unit("edu", "b"),),
        knowledge={"s1": frozenset({_unit("edu", "a")})},
        true_knowledge={"s1": frozenset({_unit("edu", "a")})},
        note="s1 already holds unit a, so releasing b to s2 finishes the witness",
    )
    # edu-completing true issuance is not s2's. Fix by using a real s2 issuance? s2 has a grant
    # but no binding. ground truth requires a true issuance. Add iss-edu-s2 via a local binding
    # override after build.
    add(
        "attribute-one-signal",
        "education",
        "s1",
        "profile:stu_001",
        "tutoring",
        (),
        {},
        units=(("profile:stu_001", "p2"),),
        retained=(("profile:stu_001", "p2"),),
        note="one signal of a two-signal student attribute",
    )
    return _repair(scenarios, book)


def _repair(scenarios: list[Scenario], book: dict[str, IssuanceBinding]) -> list[Scenario]:
    """Drop the awkward sibling draft if a clean copy was also added, and fix s2's attribute case."""
    cleaned = list(scenarios)
    drop = {"sibling-revoked-live-grant", "edu-completing-unit", "attribute-one-signal"}
    kept = [row for row in cleaned if row.scenario_id not in drop]
    registry = make_registry()
    sibling_channels = {
        "signed_credential": (
            _evidence("sib-old", "signed_credential", "siblings", ("iss-a4-old",), (_unit("A4"),)),
            _evidence("sib-new", "signed_credential", "siblings", ("iss-a4-new",), (_unit("A4"),)),
        )
    }
    kept.append(
        _case(
            "sibling-revoked-live-grant",
            "propagation",
            "u5",
            "A4",
            "education",
            (_unit("A4"),),
            ("iss-a4-new",),
            (_unit("A4"),),
            sibling_channels,
            registry=registry,
            book=book,
            note="iss-a4-old is revoked; iss-a4-new still authorizes",
        )
    )
    kept.append(
        _case(
            "edu-completing-unit",
            "education",
            "s2",
            "edu",
            "education",
            (_unit("edu", "b"),),
            ("iss-edu-s1",),
            (_unit("edu", "b"),),
            {},
            registry=registry,
            knowledge={"s1": frozenset({_unit("edu", "a")})},
            true_knowledge={"s1": frozenset({_unit("edu", "a")})},
            book=book,
            note="store already shows s1 holds unit a",
        )
    )
    # s2 releasing b is licensed by s2's grant, but true issuance iss-edu-s1 is u's? grantee s1.
    # ground truth will deny because grantee is s1 not s2. That is wrong for this case.
    # Use an s2 binding. Inject it.
    book["iss-edu-s2"] = IssuanceBinding(
        "iss-edu-s2",
        "edu",
        "s2",
        (_unit("edu", "a"), _unit("edu", "b")),
        ("education",),
    )
    book["iss-attr"] = IssuanceBinding(
        "iss-attr",
        "profile:stu_001",
        "s1",
        (("profile:stu_001", "p2"), ("profile:stu_001", "p4")),
        ("tutoring",),
    )
    kept = [row for row in kept if row.scenario_id != "edu-completing-unit"]
    kept.append(
        _case(
            "edu-completing-unit",
            "education",
            "s2",
            "edu",
            "education",
            (_unit("edu", "b"),),
            ("iss-edu-s2",),
            (_unit("edu", "b"),),
            {},
            registry=registry,
            knowledge={"s1": frozenset({_unit("edu", "a")})},
            true_knowledge={"s1": frozenset({_unit("edu", "a")})},
            book=book,
            note="s1 holds unit a; releasing b to s2 finishes the witness",
        )
    )
    kept.append(
        _case(
            "attribute-one-signal",
            "education",
            "s1",
            "profile:stu_001",
            "tutoring",
            (("profile:stu_001", "p2"),),
            ("iss-attr",),
            (("profile:stu_001", "p2"),),
            {
                "trusted_log": (
                    _evidence(
                        "attr-log",
                        "trusted_log",
                        "attribute",
                        (),
                        (("profile:stu_001", "p2"),),
                        event="attr-read",
                        holder="s1",
                    ),
                )
            },
            registry=registry,
            book=book,
            note="one attribute signal; the other signal is not held",
        )
    )
    return kept
