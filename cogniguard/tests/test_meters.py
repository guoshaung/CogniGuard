"""Lexical disclosure meter: overlap, short units, and the calibration placeholder."""

from __future__ import annotations

import pytest

from cogniguard.governance.meter import Measurement
from cogniguard.runtime.meters import CalibratedMeter, LexicalMeter, UnitContentStore

_EN = ("pack", "en")
_ZH = ("pack", "zh")
_EN_TEXT = "The Protected Conclusion Is Secret."
_ZH_TEXT = "保护未公开的教学结论不被原样复述。"


def _lexical(measurement: Measurement) -> None:
    assert measurement.bits == {}
    assert measurement.method == "lexical-v1"


def test_full_original_text_is_disclosed() -> None:
    store = UnitContentStore({_EN: _EN_TEXT})
    result = LexicalMeter(store).measure(
        "the protected conclusion is secret",
        candidate_units=frozenset({_EN}),
    )

    assert result.units == frozenset({_EN})
    _lexical(result)


def test_chinese_original_text_is_disclosed() -> None:
    store = UnitContentStore({_ZH: _ZH_TEXT})
    result = LexicalMeter(store).measure(
        "保护未公开的教学结论不被原样复述",
        candidate_units=frozenset({_ZH}),
    )

    assert result.units == frozenset({_ZH})
    _lexical(result)


def test_unrelated_text_is_not_disclosed() -> None:
    store = UnitContentStore({_ZH: _ZH_TEXT})
    result = LexicalMeter(store).measure(
        "今天天气晴朗适合出门散步看海",
        candidate_units=frozenset({_ZH}),
    )

    assert result.units == frozenset()
    _lexical(result)


def test_half_of_the_original_follows_the_thresholds() -> None:
    unit = ("pack", "half")
    source = "abcdefghijklmnopqrstuvwxyz012345"
    store = UnitContentStore({unit: source})
    text = source[:16]
    disclosed = LexicalMeter(store, coverage_threshold=0.5, lcs_threshold=0.5).measure(
        text, candidate_units=frozenset({unit})
    )
    withheld = LexicalMeter(store, coverage_threshold=0.5, lcs_threshold=0.51).measure(
        text, candidate_units=frozenset({unit})
    )

    assert disclosed.units == frozenset({unit})
    assert withheld.units == frozenset()
    _lexical(disclosed)
    _lexical(withheld)


def test_unit_missing_from_the_store_is_disclosed() -> None:
    missing = ("pack", "missing")
    result = LexicalMeter(UnitContentStore({})).measure(
        "nothing stored",
        candidate_units=frozenset({missing}),
    )

    assert result.units == frozenset({missing})
    _lexical(result)


def test_units_outside_candidate_units_are_ignored() -> None:
    shown = ("pack", "shown")
    hidden = ("pack", "hidden")
    hidden_text = "zzzz yyyy xxxx wwww vvvv"
    store = UnitContentStore(
        {
            shown: "aaaa bbbb cccc dddd eeee",
            hidden: hidden_text,
        }
    )
    meter = LexicalMeter(store)
    result = meter.measure(hidden_text, candidate_units=frozenset({shown}))
    control = meter.measure(hidden_text, candidate_units=frozenset({shown, hidden}))

    assert result.units == frozenset()
    assert control.units == frozenset({hidden})
    _lexical(result)


def test_short_unit_uses_the_substring_rule() -> None:
    unit = ("pack", "short")
    store = UnitContentStore({unit: "Cat"})
    meter = LexicalMeter(store, n=4)

    present = meter.measure("The CAT sat.", candidate_units=frozenset({unit}))
    absent = meter.measure("ab x bc", candidate_units=frozenset({unit}))

    assert present.units == frozenset({unit})
    assert absent.units == frozenset()
    _lexical(present)
    _lexical(absent)


def test_store_repr_omits_unit_text() -> None:
    secret = "needs-step-free-access"
    unit = ("resource", "unit")
    contents = {unit: secret}
    store = UnitContentStore(contents)
    contents[unit] = "changed-after-construction"

    assert store.get(unit) == secret
    assert unit in store
    assert ("resource", "missing") not in store
    assert store.get(("resource", "missing")) is None
    assert repr(store) == "UnitContentStore(units=1)"
    assert secret not in repr(store)


def test_calibrated_meter_cannot_be_constructed() -> None:
    with pytest.raises(NotImplementedError, match="pending E3b calibration"):
        CalibratedMeter()
