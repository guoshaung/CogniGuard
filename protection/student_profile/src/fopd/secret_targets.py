"""Register a student attribute as a discrete secret. No model and no secret value."""

from __future__ import annotations

from cogniguard.governance.targets import ProtectedTarget


def attribute_target(
    student_id: str,
    attribute: str,
    signal_groups: list[list[str]],
    *,
    owner_principal_id: str,
    org_id: str,
    domain_size: int = 2,
    value_commitment: str | None = None,
) -> ProtectedTarget:
    """One witness set per signal group. Record ids are the profile record ids.

    The caller passes an already computed commitment. The value and its salt
    are not arguments and are not stored on the target.
    """
    if not signal_groups or any(not group for group in signal_groups):
        raise ValueError("signal groups must be non-empty")
    resource_id = f"profile:{student_id}"
    witnesses = tuple(
        frozenset((resource_id, record_id) for record_id in group) for group in signal_groups
    )
    return ProtectedTarget(
        target_id=f"{student_id}/{attribute}",
        owner_principal_id=owner_principal_id,
        org_id=org_id,
        witness_sets=witnesses,
        kind="student_attribute",
        domain_size=domain_size,
        value_commitment=value_commitment,
    )
