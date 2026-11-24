"""Hand witnesses for the quota and union baselines. No phase-1 data."""

from cogniguard.governance.targets import ProtectedTarget, TargetRegistry

from experiments.classical_inference_20261125.baseline import (
    capd_allows,
    quota_cap,
    quota_state_within_cap,
    union_proxy_allows,
    ws04_quota_allows,
)

W = frozenset((("r", "a"), ("r", "b"), ("r", "c"), ("r", "d")))


def registry():
    target = ProtectedTarget("t", "owner", "school", (W,), kind="teaching_asset")
    return TargetRegistry([target])


def test_cap_matches_the_collusion_allocation():
    assert quota_cap(4, 1) == 3
    assert quota_cap(4, 2) == 1
    assert quota_cap(5, 2) == 2
    assert quota_cap(2, 2) == 0
    assert quota_cap(5, 3) == 1


def test_quota_refuses_a_safe_release_that_capd_allows():
    """Empty coalition, k=2: two units are still short of W, but over the cap of 1."""
    targets = registry()
    knowledge = {"A": frozenset(), "B": frozenset()}
    release = (("r", "a"), ("r", "b"))
    assert ws04_quota_allows(targets, "A", release, knowledge, 2) is False
    assert capd_allows(targets, "A", release, knowledge, 2) is True
    assert union_proxy_allows(targets, "A", release, knowledge, 2) is True


def test_quota_can_allow_an_unsafe_release_outside_the_invariant():
    """B already holds three units. A's one unit finishes W. The cap ignores B."""
    targets = registry()
    knowledge = {"A": frozenset(), "B": frozenset((("r", "b"), ("r", "c"), ("r", "d")))}
    release = (("r", "a"),)
    assert quota_state_within_cap(targets, knowledge, 2) is False
    assert ws04_quota_allows(targets, "A", release, knowledge, 2) is True
    assert capd_allows(targets, "A", release, knowledge, 2) is False


def test_inside_the_cap_a_quota_allow_is_a_capd_allow():
    targets = registry()
    units = (("r", "a"), ("r", "b"), ("r", "c"), ("r", "d"))
    holders = ("A", "B", "C")
    for assignment in _assignments(units, holders, cap=1):
        knowledge = {name: frozenset(held) for name, held in assignment.items()}
        assert quota_state_within_cap(targets, knowledge, 2)
        for unit in units:
            release = (unit,)
            if ws04_quota_allows(targets, "A", release, knowledge, 2):
                assert capd_allows(targets, "A", release, knowledge, 2)


def test_union_refuses_a_k_safe_release_and_never_safely_allows_one_capd_refuses():
    targets = registry()
    knowledge = {
        "A": frozenset(),
        "B": frozenset((("r", "a"),)),
        "C": frozenset((("r", "b"),)),
        "D": frozenset((("r", "c"),)),
    }
    release = (("r", "d"),)
    assert capd_allows(targets, "A", release, knowledge, 2) is True
    assert union_proxy_allows(targets, "A", release, knowledge, 2) is False
    # Any union allow on this witness is k-safe, so CA-PD allows it too.
    knowledge_ok = {"A": frozenset((("r", "a"),)), "B": frozenset()}
    one = (("r", "b"),)
    assert union_proxy_allows(targets, "A", one, knowledge_ok, 2) is True
    assert capd_allows(targets, "A", one, knowledge_ok, 2) is True


def _assignments(units, holders, cap):
    """Each holder gets at most `cap` distinct units. Yields every such map."""
    chosen = {name: [] for name in holders}

    def place(index):
        if index == len(units):
            yield {name: tuple(held) for name, held in chosen.items()}
            return
        unit = units[index]
        yield from place(index + 1)
        for name in holders:
            if len(chosen[name]) < cap:
                chosen[name].append(unit)
                yield from place(index + 1)
                chosen[name].pop()

    yield from place(0)
