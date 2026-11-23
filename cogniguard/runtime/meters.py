"""Disclosure meters (lexical, predicate). Unit text and predicates stay in their stores and are not logged."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

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


_NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty"
).split()
_ORDINALS = (
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
    "twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
    "nineteenth twentieth"
).split()
_CARDINAL = {word: str(n) for n, word in enumerate(_NUMBER_WORDS)}
_ORDINAL = {word: f"ord:{n}" for n, word in enumerate(_ORDINALS)}
_SENTENCE_END = re.compile(r"[.!?;。！？；\n]+")


def _tokens(text: str) -> tuple[str, ...]:
    """Lowercase word and number tokens. Number words become digits, ordinals `ord:n`."""
    out: list[str] = []
    for token in re.findall(r"[^\W\d_]+|\d+", unicodedata.normalize("NFKC", text).lower()):
        if token.isdigit():
            out.append(str(int(token)))
        else:
            out.append(_CARDINAL.get(token) or _ORDINAL.get(token) or token)
    return tuple(out)


def _contains(tokens: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    width = len(phrase)
    if width == 0 or width > len(tokens):
        return False
    return any(tokens[i : i + width] == phrase for i in range(len(tokens) - width + 1))


@dataclass(frozen=True)
class UnitPredicate:
    """Surface forms of one slot = value predicate. Aliases are tokenized like the text."""

    slot_aliases: tuple[str, ...]
    value_aliases: tuple[str, ...]


class UnitPredicateStore:
    """Read-only predicate forms per unit. The repr shows only the count."""

    def __init__(self, predicates: dict[tuple[str, str], UnitPredicate]) -> None:
        self._predicates = {
            unit: (
                tuple(_tokens(a) for a in p.slot_aliases if _tokens(a)),
                tuple(_tokens(a) for a in p.value_aliases if _tokens(a)),
            )
            for unit, p in predicates.items()
        }

    def get(self, unit: tuple[str, str]):
        return self._predicates.get(unit)

    def __repr__(self) -> str:
        return f"UnitPredicateStore(units={len(self._predicates)})"


class PredicateMeter:
    """Disclose a unit when some slot alias and some value alias both occur.

    Built to over-count (assumption A1): word order, wording and distance are
    ignored. scope="text" looks at the whole text; scope="sentence" needs both
    in one sentence and counts less, at the risk of missing split statements.
    A unit with no stored predicate, or one with an empty alias list, is disclosed.
    """

    def __init__(self, store: UnitPredicateStore, *, scope: str = "text") -> None:
        if scope not in ("text", "sentence"):
            raise ValueError("scope must be text or sentence")
        self._store = store
        self._scope = scope

    def measure(
        self, text: str, *, candidate_units: frozenset[tuple[str, str]]
    ) -> Measurement:
        if self._scope == "text":
            spans = [_tokens(text)]
        else:
            spans = [_tokens(part) for part in _SENTENCE_END.split(text)]
        disclosed: set[tuple[str, str]] = set()
        for unit in candidate_units:
            forms = self._store.get(unit)
            if forms is None or not forms[0] or not forms[1]:
                disclosed.add(unit)
                continue
            slots, values = forms
            for span in spans:
                if any(_contains(span, s) for s in slots) and any(
                    _contains(span, v) for v in values
                ):
                    disclosed.add(unit)
                    break
        return Measurement(
            units=frozenset(disclosed), bits={}, method=f"predicate-v1-{self._scope}"
        )


class CalibratedMeter:
    """Placeholder until E3b produces a calibration table."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise NotImplementedError("pending E3b calibration")
