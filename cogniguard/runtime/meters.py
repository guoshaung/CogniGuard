"""Lexical disclosure meter. Unit text stays in the store and is not logged."""

from __future__ import annotations

import difflib
import re
import unicodedata

from cogniguard.governance.meter import Measurement


def _normalize(text: str) -> str:
    kept: list[str] = []
    for char in unicodedata.normalize("NFKC", text).lower():
        if unicodedata.category(char).startswith("P"):
            continue
        kept.append(char)
    return re.sub(r"\s+", " ", "".join(kept)).strip()


def _ngram_coverage(unit: str, text: str, n: int) -> float:
    total = len(unit) - n + 1
    if total <= 0:
        return 0.0
    present = sum(1 for start in range(total) if unit[start : start + n] in text)
    return present / total


def _lcs_ratio(unit: str, text: str) -> float:
    if not unit:
        return 0.0
    match = difflib.SequenceMatcher(None, unit, text, autojunk=False).find_longest_match(
        0, len(unit), 0, len(text)
    )
    return match.size / len(unit)


class UnitContentStore:
    """Read-only unit text. The repr shows how many units are stored, not their text."""

    def __init__(self, contents: dict[tuple[str, str], str]) -> None:
        self._contents = dict(contents)

    def get(self, unit: tuple[str, str]) -> str | None:
        return self._contents.get(unit)

    def __contains__(self, unit: object) -> bool:
        return unit in self._contents

    def __repr__(self) -> str:
        return f"UnitContentStore(units={len(self._contents)})"


class LexicalMeter:
    """Disclose a unit when n-gram coverage or the longest common substring reaches its threshold."""

    def __init__(
        self,
        store: UnitContentStore,
        *,
        n: int = 4,
        coverage_threshold: float = 0.5,
        lcs_threshold: float = 0.3,
    ) -> None:
        self._store = store
        self._n = n
        self._coverage_threshold = coverage_threshold
        self._lcs_threshold = lcs_threshold

    def measure(
        self, text: str, *, candidate_units: frozenset[tuple[str, str]]
    ) -> Measurement:
        normalized_text = _normalize(text)
        disclosed: set[tuple[str, str]] = set()
        for unit in candidate_units:
            content = self._store.get(unit)
            if content is None:
                disclosed.add(unit)
                continue
            normalized_unit = _normalize(content)
            if len(normalized_unit) < self._n:
                if normalized_unit in normalized_text:
                    disclosed.add(unit)
                continue
            covered = _ngram_coverage(normalized_unit, normalized_text, self._n)
            if covered >= self._coverage_threshold or _lcs_ratio(
                normalized_unit, normalized_text
            ) >= self._lcs_threshold:
                disclosed.add(unit)
        return Measurement(units=frozenset(disclosed), bits={}, method="lexical-v1")


class CalibratedMeter:
    """Placeholder until E3b produces a calibration table."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise NotImplementedError("pending E3b calibration")
