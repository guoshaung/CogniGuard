from __future__ import annotations

import warnings
from typing import Any

from .policy_selector import CopyrightSelection, select_copyright_candidate


CGSelection = CopyrightSelection


def select_candidate(candidates: list[dict[str, Any]], evidence: dict[str, Any], *, audit_valid: bool = True, privacy_risk: float = 0.0) -> CopyrightSelection:
    """Deprecated compatibility wrapper. Use select_copyright_candidate."""
    warnings.warn("cg_bridge is deprecated; copyright selection now belongs to C²-RAG", DeprecationWarning, stacklevel=2)
    domain_evidence = {**evidence, "provenance_valid": audit_valid}
    return select_copyright_candidate(candidates, domain_evidence)
