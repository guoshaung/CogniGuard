"""Frozen X3-E2E arms (PREREG_X3E2E.md §2). An arm only selects which evidence channels
governance may read; every arm uses the same verifier, state, policy and requests."""

from __future__ import annotations

from dataclasses import dataclass

from cogniguard.provenance.schema import EvidenceType as T


@dataclass(frozen=True)
class Arm:
    name: str
    evidence_types: frozenset
    method_prefixes: tuple[str, ...] = ()   # optional filter on method_version
    allow_ideal: bool = False
    upper_bound: bool = False               # never reported as a real-method result


ARMS = {a.name: a for a in (
    Arm("R0_receipts", frozenset()),
    Arm("F_STRONG", frozenset({T.FINGERPRINT, T.RETRIEVAL})),
    Arm("F_BGE", frozenset({T.RETRIEVAL}), method_prefixes=("codex-bge@",)),  # DEVIATIONS §7
    Arm("WM_REAL", frozenset({T.WATERMARK})),
    Arm("KBW_REAL", frozenset({T.KNOWLEDGE_BOUND_WATERMARK})),
    Arm("JOINT", frozenset({T.JOINT})),
    Arm("CRED", frozenset({T.SIGNED_CREDENTIAL})),
    Arm("LOG", frozenset({T.TRUSTED_LOG})),
    # Content-side combinations (no channel log: a worst-case log hop dominates any content signal).
    Arm("CONTENT_ALL", frozenset({T.FINGERPRINT, T.RETRIEVAL, T.SIGNED_CREDENTIAL})),
    Arm("CONTENT_ALL_WM", frozenset({T.FINGERPRINT, T.RETRIEVAL, T.SIGNED_CREDENTIAL, T.WATERMARK,
                                     T.KNOWLEDGE_BOUND_WATERMARK, T.JOINT})),
    Arm("ALL_REAL_LOG", frozenset({T.FINGERPRINT, T.RETRIEVAL, T.SIGNED_CREDENTIAL, T.WATERMARK,
                                   T.KNOWLEDGE_BOUND_WATERMARK, T.JOINT, T.TRUSTED_LOG})),
    Arm("IDEAL", frozenset({T.IDEAL}), allow_ideal=True, upper_bound=True),
)}
MODES = ("static", "dyn_knowledge", "dyn_full", "dyn_conservative")
MOCK_ARM = Arm("MOCK", frozenset({T.MOCK}))
