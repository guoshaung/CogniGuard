"""Predicate meter: wording-independent matching that may over-count but should not miss."""

from __future__ import annotations

import pytest

from cogniguard.runtime.meters import PredicateMeter, UnitPredicate, UnitPredicateStore

_A = ("t", "a")  # feature 0 = 1
_B = ("t", "b")  # feature 1 = 2
_SCOPE = frozenset({_A, _B})


def _store() -> UnitPredicateStore:
    return UnitPredicateStore(
        {
            _A: UnitPredicate(("feature 0", "0"), ("1",)),
            _B: UnitPredicate(("feature 1", "1"), ("2",)),
        }
    )


def test_number_words_and_digits_match_the_same_unit() -> None:
    meter = PredicateMeter(_store())
    assert meter.measure("Feature zero has value one.", candidate_units=_SCOPE).units >= {_A}
    assert meter.measure("feature 00 -> 1", candidate_units=_SCOPE).units >= {_A}


def test_tokens_do_not_match_inside_longer_numbers() -> None:
    meter = PredicateMeter(_store())
    assert meter.measure("value 10 at slot 30", candidate_units=_SCOPE).units == frozenset()


def test_sentence_scope_counts_less_than_text_scope() -> None:
    text = "Feature 0 is noted. The value 2 is elsewhere."
    assert _A not in PredicateMeter(_store(), scope="sentence").measure(
        text, candidate_units=_SCOPE
    ).units
    split = "Feature 0. Value: 1."
    assert _A in PredicateMeter(_store()).measure(split, candidate_units=_SCOPE).units
    assert _A not in PredicateMeter(_store(), scope="sentence").measure(
        split, candidate_units=_SCOPE
    ).units


def test_unknown_unit_and_empty_aliases_are_disclosed() -> None:
    store = UnitPredicateStore({_A: UnitPredicate((), ("1",))})
    result = PredicateMeter(store).measure("nothing here", candidate_units=_SCOPE)
    assert result.units == _SCOPE
    assert result.method == "predicate-v1-text"
    assert "feature" not in repr(store)


def test_rejects_unknown_scope() -> None:
    with pytest.raises(ValueError):
        PredicateMeter(_store(), scope="paragraph")
