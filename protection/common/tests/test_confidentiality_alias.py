"""confidentiality_level is the read-only name for copyright_level."""

from __future__ import annotations

from protection.common.schemas import TeacherResource


def test_confidentiality_level_matches_copyright_level() -> None:
    resource = TeacherResource.from_dict({"copyright_level": 0.7})
    assert resource.confidentiality_level == 0.7
