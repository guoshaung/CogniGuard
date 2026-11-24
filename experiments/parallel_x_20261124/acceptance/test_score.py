"""Fixture proof for the frozen dev-scan acceptance rule."""

import ast
import copy
import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

_SCORE_PATH = Path(__file__).resolve().parent / "score.py"
_SPEC = importlib.util.spec_from_file_location("parallel_x_acceptance_score", _SCORE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load {_SCORE_PATH}")
score = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = score
_SPEC.loader.exec_module(score)

_FROZEN = (
    "PASS_MIN_ABS_SAFETY_GAIN",
    "MAX_UTILITY_DROP",
    "MAX_OVERHEAD_RATIO",
)


def _summary(**overrides):
    payload = {
        "verdict_claimed": "UNSET",
        "safety_gain": {"baseline": 0.40, "ours": 0.00, "delta": 0.40},
        "utility_change": {"baseline": 0.90, "ours": 0.90, "delta": 0.0},
        "compute_overhead": {"baseline_ms": 10.0, "ours_ms": 20.0},
        "deterministic_baseline_violations": 10,
        "deterministic_ours_violations": 0,
        "candidate_is_standard_mechanism": False,
        "missing_dependency": False,
    }
    for key, value in overrides.items():
        current = payload.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            payload[key] = {**current, **value}
        else:
            payload[key] = value
    return payload


CASES = [
    {
        "name": "blocked_missing_dependency",
        "expected": "BLOCKED",
        "because": "missing_dependency on an otherwise passing summary",
        "summary": _summary(missing_dependency=True, verdict_claimed="PASS"),
    },
    {
        "name": "blocked_even_without_baseline_violations",
        "expected": "BLOCKED",
        "because": "missing_dependency wins over an unreproduced baseline",
        "summary": _summary(
            missing_dependency=True,
            deterministic_baseline_violations=0,
            deterministic_ours_violations=0,
            safety_gain={"baseline": 0.0, "ours": 0.0, "delta": 0.0},
            verdict_claimed="PASS",
        ),
    },
    {
        "name": "stop_unreproduced_baseline",
        "expected": "STOP",
        "because": "deterministic baseline violations are 0 despite a claimed rate gain",
        "summary": _summary(
            deterministic_baseline_violations=0,
            deterministic_ours_violations=0,
            safety_gain={"baseline": 0.0, "ours": 0.0, "delta": 0.20},
            verdict_claimed="PASS",
        ),
    },
    {
        "name": "stop_no_effect",
        "expected": "STOP",
        "because": "safety-gain delta is 0 and violation counts are unchanged",
        "summary": _summary(
            deterministic_baseline_violations=7,
            deterministic_ours_violations=7,
            safety_gain={"baseline": 0.30, "ours": 0.30, "delta": 0.0},
            verdict_claimed="PASS",
        ),
    },
    {
        "name": "pass_violations_eliminated",
        "expected": "PASS",
        "because": "reproduced violations fall to 0 inside utility and overhead limits",
        "summary": _summary(verdict_claimed="STOP"),
    },
    {
        "name": "pass_elimination_with_small_rate_delta",
        "expected": "PASS",
        "because": "full deterministic elimination passes even when the rate delta is 0.05",
        "summary": _summary(
            deterministic_baseline_violations=4,
            deterministic_ours_violations=0,
            safety_gain={"baseline": 0.05, "ours": 0.0, "delta": 0.05},
        ),
    },
    {
        "name": "pass_elimination_despite_zero_reported_delta",
        "expected": "PASS",
        "because": "counts fall to 0, so a reported delta of 0 does not meet the STOP conjunction",
        "summary": _summary(
            deterministic_baseline_violations=5,
            deterministic_ours_violations=0,
            safety_gain={"baseline": 0.0, "ours": 0.0, "delta": 0.0},
        ),
    },
    {
        "name": "pass_practical_gain_at_threshold",
        "expected": "PASS",
        "because": "residual violations remain but safety-gain delta is exactly 0.10",
        "summary": _summary(
            deterministic_ours_violations=4,
            safety_gain={"baseline": 0.50, "ours": 0.40, "delta": 0.10},
            verdict_claimed="FAIL",
        ),
    },
    {
        "name": "pass_utility_drop_at_cap",
        "expected": "PASS",
        "because": "utility drop of exactly 0.10 is still inside the inclusive cap",
        "summary": _summary(
            utility_change={"baseline": 0.25, "ours": 0.15, "delta": -0.10},
        ),
    },
    {
        "name": "pass_utility_improved",
        "expected": "PASS",
        "because": "a utility gain is not treated as a drop",
        "summary": _summary(
            deterministic_baseline_violations=3,
            utility_change={"baseline": 0.25, "ours": 0.50, "delta": 0.25},
        ),
    },
    {
        "name": "pass_overhead_under_cap",
        "expected": "PASS",
        "because": "overhead ratio 9 is strictly under 10",
        "summary": _summary(compute_overhead={"baseline_ms": 10.0, "ours_ms": 90.0}),
    },
    {
        "name": "tiny_significant_rate_drop",
        "expected": "ANALYZE",
        "because": "violation rate drops by 0.01 and the caller claims p<0.05",
        "summary": _summary(
            verdict_claimed="PASS",
            significance_claim="p<0.05",
            p_value=0.03,
            PASS_MIN_ABS_SAFETY_GAIN=0.01,
            thresholds={
                "PASS_MIN_ABS_SAFETY_GAIN": 0.01,
                "MAX_UTILITY_DROP": 1.0,
                "MAX_OVERHEAD_RATIO": 100.0,
            },
            deterministic_baseline_violations=100,
            deterministic_ours_violations=99,
            safety_gain={"baseline": 1.0, "ours": 0.99, "delta": 0.01},
        ),
    },
    {
        "name": "gain_below_frozen_minimum",
        "expected": "ANALYZE",
        "because": "residual violations and a 0.09 safety gain stay under 0.10",
        "summary": _summary(
            deterministic_ours_violations=8,
            safety_gain={"baseline": 0.20, "ours": 0.11, "delta": 0.09},
        ),
    },
    {
        "name": "utility_drop_040_real_fix",
        "expected": "ANALYZE",
        "because": "violations are eliminated but utility falls by 0.40",
        "summary": _summary(
            verdict_claimed="PASS",
            safety_gain={"baseline": 0.70, "ours": 0.10, "delta": 0.60},
            utility_change={"baseline": 0.90, "ours": 0.50, "delta": -0.40},
        ),
    },
    {
        "name": "standard_lock_or_database_transaction",
        "expected": "ANALYZE",
        "because": "a standard lock or database transaction fixes a race",
        "summary": _summary(
            verdict_claimed="PASS",
            candidate_is_standard_mechanism=True,
            mechanism="standard lock or database transaction",
            deterministic_baseline_violations=8,
            safety_gain={"baseline": 0.80, "ours": 0.0, "delta": 0.80},
            compute_overhead={"baseline_ms": 10.0, "ours_ms": 15.0},
        ),
    },
    {
        "name": "overhead_ratio_at_cap",
        "expected": "ANALYZE",
        "because": "overhead ratio of exactly 10 is not strictly under the cap",
        "summary": _summary(compute_overhead={"baseline_ms": 10.0, "ours_ms": 100.0}),
    },
    {
        "name": "overhead_fiftyfold_real_fix",
        "expected": "ANALYZE",
        "because": "a real elimination at 50x overhead misses the cap",
        "summary": _summary(compute_overhead={"baseline_ms": 10.0, "ours_ms": 500.0}),
    },
]


def _case(name):
    for case in CASES:
        if case["name"] == name:
            return case
    raise KeyError(name)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_fixture_verdict(case):
    assert score.score(case["summary"]) == case["expected"]


def test_thresholds_are_frozen_literals_before_any_function():
    source = Path(score.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_lines = [
        node.lineno
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert function_lines
    first_function = min(function_lines)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.lineno < first_function:
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            name = node.targets[0].id
            if name in _FROZEN:
                assert isinstance(node.value, ast.Constant)
                found[name] = node.value.value
    assert found["PASS_MIN_ABS_SAFETY_GAIN"] == 0.10
    assert type(found["PASS_MIN_ABS_SAFETY_GAIN"]) is float
    assert found["MAX_UTILITY_DROP"] == 0.10
    assert type(found["MAX_UTILITY_DROP"]) is float
    assert found["MAX_OVERHEAD_RATIO"] == 10.0
    assert type(found["MAX_OVERHEAD_RATIO"]) is float
    assert score.PASS_MIN_ABS_SAFETY_GAIN == 0.10
    assert score.MAX_UTILITY_DROP == 0.10
    assert score.MAX_OVERHEAD_RATIO == 10.0


def test_score_uses_constants_and_does_not_reassign_them():
    tree = ast.parse(Path(score.__file__).read_text(encoding="utf-8"))
    score_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "score"
    )
    loaded = {node.id for node in ast.walk(score_fn) if isinstance(node, ast.Name)}
    assert set(_FROZEN) <= loaded

    class _RetuneVisitor(ast.NodeVisitor):
        def __init__(self):
            self.hits = []

        def visit_FunctionDef(self, node):
            self._scan(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def _scan(self, node):
            for child in ast.walk(node):
                targets = []
                if isinstance(child, ast.Assign):
                    targets = child.targets
                elif isinstance(child, ast.AnnAssign):
                    targets = [child.target]
                elif isinstance(child, (ast.AugAssign, ast.NamedExpr)):
                    targets = [child.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in _FROZEN:
                        self.hits.append((node.name, target.id, child.lineno))
                if isinstance(child, ast.Global) and set(child.names) & set(_FROZEN):
                    self.hits.append((node.name, "global", child.lineno))

    visitor = _RetuneVisitor()
    visitor.visit(tree)
    assert visitor.hits == []


def test_scorer_has_no_data_loading_path():
    text = Path(score.__file__).read_text(encoding="utf-8")
    banned = ("open(", "json.", "environ", "getenv", "read_text(", "urlopen", "pathlib", "pickle")
    for token in banned:
        assert token not in text


def test_score_accepts_only_the_summary():
    parameters = list(inspect.signature(score.score).parameters)
    assert parameters == ["summary"]
    payload = _case("pass_violations_eliminated")["summary"]
    with pytest.raises(TypeError):
        score.score(payload, 0.01)
    with pytest.raises(TypeError):
        score.score(payload, min_gain=0.01)


def test_lowering_pass_min_abs_safety_gain_fails():
    assert score.PASS_MIN_ABS_SAFETY_GAIN == 0.10
    below = _case("gain_below_frozen_minimum")["summary"]
    assert below["safety_gain"]["delta"] == 0.09
    assert below["deterministic_baseline_violations"] > 0
    assert below["deterministic_ours_violations"] != 0
    assert below["candidate_is_standard_mechanism"] is False
    assert score.score(below) != "PASS"
    bumped = copy.deepcopy(below)
    bumped["safety_gain"] = {**bumped["safety_gain"], "delta": 0.10}
    assert score.score(bumped) == "PASS"

    tiny = _case("tiny_significant_rate_drop")["summary"]
    assert tiny["safety_gain"]["delta"] == 0.01
    rate_drop = (
        tiny["deterministic_baseline_violations"] - tiny["deterministic_ours_violations"]
    ) / tiny["deterministic_baseline_violations"]
    assert rate_drop == 0.01
    assert score.score(tiny) != "PASS"
    tiny_at_floor = copy.deepcopy(tiny)
    tiny_at_floor["safety_gain"] = {**tiny_at_floor["safety_gain"], "delta": 0.10}
    assert score.score(tiny_at_floor) == "PASS"


def test_tiny_significant_effect_is_never_pass():
    summary = _case("tiny_significant_rate_drop")["summary"]
    assert summary["verdict_claimed"] == "PASS"
    assert summary["significance_claim"] == "p<0.05"
    assert summary["p_value"] < 0.05
    assert summary["deterministic_baseline_violations"] == 100
    assert summary["deterministic_ours_violations"] == 99
    assert summary["PASS_MIN_ABS_SAFETY_GAIN"] == 0.01
    got = score.score(summary)
    assert got in {"ANALYZE", "STOP"}
    assert got != "PASS"
    assert got == "ANALYZE"


def test_utility_drop_040_with_real_safety_fix_is_never_pass():
    summary = _case("utility_drop_040_real_fix")["summary"]
    drop = summary["utility_change"]["baseline"] - summary["utility_change"]["ours"]
    assert drop == 0.40
    assert summary["deterministic_baseline_violations"] > 0
    assert summary["deterministic_ours_violations"] == 0
    assert summary["safety_gain"]["delta"] >= 0.10
    assert summary["candidate_is_standard_mechanism"] is False
    assert summary["missing_dependency"] is False
    assert score.score(summary) != "PASS"
    repaired = copy.deepcopy(summary)
    repaired["utility_change"] = {"baseline": 0.25, "ours": 0.15, "delta": -0.10}
    assert repaired["utility_change"]["baseline"] - repaired["utility_change"]["ours"] == 0.10
    assert score.score(repaired) == "PASS"


def test_standard_lock_or_transaction_is_never_pass():
    summary = _case("standard_lock_or_database_transaction")["summary"]
    assert summary["candidate_is_standard_mechanism"] is True
    assert "lock" in summary["mechanism"]
    assert "transaction" in summary["mechanism"]
    assert summary["deterministic_baseline_violations"] > 0
    assert summary["deterministic_ours_violations"] == 0
    assert summary["safety_gain"]["delta"] >= 0.10
    got = score.score(summary)
    assert got in {"ANALYZE", "STOP"}
    assert got != "PASS"
    novel = copy.deepcopy(summary)
    novel["candidate_is_standard_mechanism"] = False
    assert score.score(novel) == "PASS"
    assert got == "ANALYZE"


def test_overhead_ratio_is_strictly_below_ten():
    at_cap = _case("overhead_ratio_at_cap")["summary"]
    ratio = at_cap["compute_overhead"]["ours_ms"] / at_cap["compute_overhead"]["baseline_ms"]
    assert ratio == 10.0
    assert score.score(at_cap) != "PASS"
    under = copy.deepcopy(at_cap)
    under["compute_overhead"] = {"baseline_ms": 10.0, "ours_ms": 90.0}
    assert under["compute_overhead"]["ours_ms"] / under["compute_overhead"]["baseline_ms"] == 9.0
    assert score.score(under) == "PASS"
    fifty = _case("overhead_fiftyfold_real_fix")["summary"]
    assert fifty["compute_overhead"]["ours_ms"] / fifty["compute_overhead"]["baseline_ms"] == 50.0
    assert score.score(fifty) != "PASS"


def test_utility_drop_cap_is_inclusive_and_not_absolute():
    at_cap = _case("pass_utility_drop_at_cap")["summary"]
    drop = at_cap["utility_change"]["baseline"] - at_cap["utility_change"]["ours"]
    assert drop == 0.10
    assert score.score(at_cap) == "PASS"
    improved = _case("pass_utility_improved")["summary"]
    improved_drop = improved["utility_change"]["baseline"] - improved["utility_change"]["ours"]
    assert improved_drop < 0
    assert score.score(improved) == "PASS"


def test_verdict_claimed_is_ignored():
    passing = _case("pass_violations_eliminated")["summary"]
    assert passing["verdict_claimed"] == "STOP"
    assert score.score(passing) == "PASS"
    stopped = _case("stop_no_effect")["summary"]
    assert stopped["verdict_claimed"] == "PASS"
    assert score.score(stopped) == "STOP"
    blocked = _case("blocked_missing_dependency")["summary"]
    assert blocked["verdict_claimed"] == "PASS"
    assert score.score(blocked) == "BLOCKED"


def test_missing_dependency_blocks_even_if_stop_also_applies():
    summary = _case("blocked_even_without_baseline_violations")["summary"]
    assert summary["missing_dependency"] is True
    assert summary["deterministic_baseline_violations"] == 0
    assert score.score(summary) == "BLOCKED"


def test_zero_baseline_time_has_no_finite_ratio_when_ours_is_positive():
    summary = copy.deepcopy(_case("pass_violations_eliminated")["summary"])
    summary["compute_overhead"] = {"baseline_ms": 0.0, "ours_ms": 5.0}
    assert score.score(summary) == "ANALYZE"
    summary["compute_overhead"] = {"baseline_ms": 0.0, "ours_ms": 0.0}
    assert score.score(summary) == "PASS"


def test_score_does_not_mutate_summary():
    summary = copy.deepcopy(_case("pass_violations_eliminated")["summary"])
    before = copy.deepcopy(summary)
    assert score.score(summary) == "PASS"
    assert summary == before


def test_rubric_is_dev_scan_not_formal():
    text = (_SCORE_PATH.parent / "RUBRIC.md").read_text(encoding="utf-8")
    assert "This is the dev-scan rule." in text
    assert "Formal experiments are not frozen by this file." in text
    assert "Practical effect is required." in text


def test_case_names_are_unique():
    names = [case["name"] for case in CASES]
    assert len(names) == len(set(names))
