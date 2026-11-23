"""Protected targets keep minimal witness sets and do not store unit text."""

from __future__ import annotations

import json
import os
from dataclasses import fields

import pytest

from cogniguard.governance.targets import (
    ProtectedTarget,
    TargetRegistry,
    commit_value,
    load_asset_pack_targets,
    verify_commitment,
)


def _target(target_id: str, *witnesses: frozenset[tuple[str, str]]) -> ProtectedTarget:
    return ProtectedTarget(target_id, "owner-a", "org-a", witnesses)


def test_empty_witness_set_is_rejected() -> None:
    with pytest.raises(ValueError):
        _target("empty")
    with pytest.raises(ValueError):
        _target("blank", frozenset())


def test_superset_witness_sets_are_dropped() -> None:
    small = frozenset({("resource", "a")})
    larger = frozenset({("resource", "a"), ("resource", "b")})
    other = frozenset({("resource", "c")})

    target = _target("goal", larger, other, small, larger)

    assert target.witness_sets == (small, other)


def test_witness_sets_keep_a_stable_order() -> None:
    first = frozenset({("resource", "b")})
    second = frozenset({("resource", "a"), ("resource", "c")})
    third = frozenset({("resource", "a")})

    forward = _target("goal", first, second, third)
    reverse = _target("goal", third, second, first)

    assert forward.witness_sets == reverse.witness_sets
    assert forward.witness_sets == (
        frozenset({("resource", "a")}),
        frozenset({("resource", "b")}),
    )


def test_duplicate_target_id_is_rejected() -> None:
    unit = frozenset({("resource", "u")})
    with pytest.raises(ValueError):
        TargetRegistry([_target("same", unit), _target("same", unit)])


def test_targets_for_unit_uses_the_construction_index() -> None:
    shared = frozenset({("resource", "shared")})
    left = _target("left", frozenset({("resource", "left"), ("resource", "shared")}))
    right = _target("right", shared)
    other = _target("other", frozenset({("resource", "other")}))
    registry = TargetRegistry([left, right, other])

    assert registry.targets_for_unit(("resource", "shared")) == (left, right)
    assert registry.targets_for_unit(("resource", "left")) == (left,)
    assert registry.targets_for_unit(("resource", "missing")) == ()
    assert registry.get("right") == right


def test_load_asset_pack_targets_reads_a_small_pack(tmp_path) -> None:
    marker = "SYNTHETIC_TEXT_NOT_FROM_AN_ASSET_PACK"
    pack = tmp_path / "pack"
    pack.mkdir()
    record = {
        "package_id": "pkg-a",
        "units": [{"unit_id": "u1", "content": marker}],
        "protected_targets": [
            {"target_id": "one", "unit_ids": ["u2", "u1"], "success_condition": marker},
            {"target_id": "two", "unit_ids": ["u2"]},
        ],
    }
    (pack / "pedagogical_assets_v1.jsonl").write_text(
        json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    loaded = load_asset_pack_targets(pack, owner_principal_id="teacher-a", org_id="school")

    assert len(loaded) == 2
    assert loaded[0].target_id == "pkg-a/one"
    assert loaded[0].owner_principal_id == "teacher-a"
    assert loaded[0].org_id == "school"
    assert loaded[0].value == 1.0
    assert loaded[0].kind == "teaching_asset"
    assert loaded[0].domain_size is None
    assert loaded[0].value_commitment is None
    assert loaded[0].witness_sets == (frozenset({("pkg-a", "u1"), ("pkg-a", "u2")}),)
    assert loaded[1].target_id == "pkg-a/two"
    assert loaded[1].witness_sets == (frozenset({("pkg-a", "u2")}),)
    assert marker not in repr(loaded)
    registry = TargetRegistry(loaded)
    assert registry.targets_for_unit(("pkg-a", "u1")) == (loaded[0],)
    assert registry.get("pkg-a/two") == loaded[1]


def test_real_asset_pack_has_five_packages_and_fifteen_targets() -> None:
    root = os.environ.get("COGNIGUARD_ASSET_PACK", "").strip()
    if not root:
        pytest.skip("COGNIGUARD_ASSET_PACK is not set")

    loaded = load_asset_pack_targets(root, owner_principal_id="owner", org_id="org")
    packages = {target.target_id.split("/", 1)[0] for target in loaded}

    assert len(packages) == 5
    assert len(loaded) == 15
    assert {target.kind for target in loaded} == {"teaching_asset"}
    assert all(target.domain_size is None and target.value_commitment is None for target in loaded)


def test_old_construction_keeps_the_previous_defaults() -> None:
    target = ProtectedTarget("goal", "owner-a", "org-a", (frozenset({("resource", "u")}),))

    assert target.kind == "teaching_asset"
    assert target.domain_size is None
    assert target.value_commitment is None
    assert target.value == 1.0


def test_domain_size_below_two_is_rejected() -> None:
    witness = (frozenset({("resource", "u")}),)
    for size in (1, 0, -3):
        with pytest.raises(ValueError):
            ProtectedTarget("goal", "owner-a", "org-a", witness, domain_size=size)
    accepted = ProtectedTarget("goal", "owner-a", "org-a", witness, domain_size=2)
    assert accepted.domain_size == 2


def test_value_commitment_checks_the_salted_secret_without_storing_it() -> None:
    secret = "needs-step-free-access"
    salt = "salt-kept-outside-the-target"
    commitment = commit_value(secret, salt)
    target = ProtectedTarget(
        "goal",
        "owner-a",
        "org-a",
        (frozenset({("profile", "signal")}),),
        domain_size=2,
        value_commitment=commitment,
    )

    assert verify_commitment(secret, salt, target.value_commitment)
    assert not verify_commitment("does-not-need-support", salt, target.value_commitment)
    assert not verify_commitment(secret, "different-salt", target.value_commitment)
    stored = " ".join(repr(getattr(target, field.name)) for field in fields(target))
    assert secret not in stored
    assert salt not in stored


def test_commitment_splits_salt_and_value_at_the_boundary() -> None:
    assert commit_value("c", "ab") != commit_value("bc", "a")


def test_student_attribute_target_can_be_constructed() -> None:
    target = ProtectedTarget(
        "access-need",
        "owner-a",
        "org-a",
        (frozenset({("profile", "request")}),),
        kind="student_attribute",
        domain_size=2,
    )

    assert target.kind == "student_attribute"
    assert target.domain_size == 2
    assert target.value_commitment is None
