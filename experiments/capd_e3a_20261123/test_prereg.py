"""The frozen pre-registration matches the hash stored beside it."""

from __future__ import annotations

import hashlib
from pathlib import Path


def test_preregistration_file_matches_its_recorded_hash() -> None:
    directory = Path(__file__).resolve().parent
    recorded = (directory / "PREREG_E3a.sha256").read_text(encoding="utf-8").split()[0]
    digest = hashlib.sha256((directory / "PREREG_E3a.md").read_bytes()).hexdigest()
    assert recorded == digest
