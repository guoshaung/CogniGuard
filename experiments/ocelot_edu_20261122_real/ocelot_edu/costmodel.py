"""Measured bit costs. Pairwise prediction never reads order-3 or order-4 hits."""

from __future__ import annotations

import math
from collections import defaultdict
from itertools import combinations

from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import MU_ADVERSARIAL, SAMPLES_PER_MODEL


def view_key(unit_ids) -> str:
    return ",".join(sorted(unit_ids))


def jeffreys(hits: int, n: int) -> float:
    if n <= 0:
        raise ValueError("n")
    return (hits + 0.5) / (n + 1.0)


def bits(h_view: float, h_base: float) -> float:
    if h_view <= 0 or h_base <= 0:
        raise ValueError("hit rate must stay positive under Jeffreys smoothing")
    return max(0.0, math.log2(h_view / h_base))


def all_views(private_ids) -> tuple[tuple[str, ...], ...]:
    ids = tuple(sorted(private_ids))
    views = [()]
    for size in range(1, 5):
        views.extend(combinations(ids, size))
    return tuple(views)


def covering_views(private_ids, target_units) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Every size-3 and size-4 private view that contains the target's units."""
    units = tuple(target_units)
    others = tuple(u for u in sorted(private_ids) if u not in units)
    items = []
    for order in (3, 4):
        need = order - len(units)
        if need < 0:
            continue
        for extra in combinations(others, need):
            items.append((order, tuple(sorted((*units, *extra)))))
    return tuple(items)


class Meas:
    """Pooled hit counts. h is the rate at which the proxy output contains every unit of the target."""

    def __init__(self, n: int, hits: dict[tuple[str, str, str], int]):
        self.n = n
        self.hits = hits

    def h(self, package_id: str, unit_ids, target_id: str) -> float:
        key = (package_id, view_key(unit_ids), target_id)
        if key not in self.hits:
            raise KeyError(key)
        return jeffreys(self.hits[key], self.n)


def predicted_cost(meas: Meas, package_id: str, unit_ids, target_id: str, target_units) -> float:
    """Size <= 2 uses the measured rate. Size >= 3 uses only empty, single, and pair rates."""
    ids = tuple(sorted(unit_ids))
    base = meas.h(package_id, (), target_id)
    if len(ids) <= 2:
        return bits(meas.h(package_id, ids, target_id), base)
    return _pair_extrapolation(meas, package_id, ids, target_id, tuple(target_units), base)


def _pair_extrapolation(meas, package_id, ids, target_id, target_units, base) -> float:
    def ell(view) -> float:
        return math.log2(meas.h(package_id, view, target_id))

    base_ell = math.log2(base)
    acc = base_ell
    inside = set(target_units)
    for unit_id in ids:
        acc += ell((unit_id,)) - base_ell
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            if left in inside and right in inside:
                acc += ell(tuple(sorted((left, right)))) - ell((left,)) - ell((right,)) + base_ell
    acc = min(0.0, max(base_ell, acc))
    return max(0.0, acc - base_ell)


def single_base(meas: Meas, package_id: str, unit_id: str, targets) -> float:
    """Max measured advantage of one fragment about a declared target that contains it.

    Units that sit in no protected target, including the anchor task, stay at 0.
    That is the absence of a declared secret, not a hand-set prior.
    """
    values = []
    for target in targets:
        if unit_id not in target.unit_ids:
            continue
        values.append(
            bits(
                meas.h(package_id, (unit_id,), target.target_id),
                meas.h(package_id, (), target.target_id),
            )
        )
    if not values:
        return 0.0
    return max(values)


def trajectory_increment(meas: Meas, package_id: str, unit_id: str, already, targets) -> float:
    """Pairwise incremental base cost on one trajectory. Ignores order >= 3 measurements."""
    prior = set(already)
    if unit_id in prior:
        return 0.0
    best = 0.0
    touched = False
    for target in targets:
        if unit_id not in target.unit_ids:
            continue
        touched = True
        before = tuple(sorted(prior & set(target.unit_ids)))
        after = tuple(sorted((*before, unit_id)))
        best = max(
            best,
            predicted_cost(meas, package_id, after, target.target_id, target.unit_ids)
            - predicted_cost(meas, package_id, before, target.target_id, target.unit_ids),
        )
    if not touched:
        return 0.0
    return max(0.0, best)


def expected_record_count(n_packages: int = 5, n_private: int = 6) -> int:
    n_views = sum(math.comb(n_private, k) for k in range(0, 5))
    return n_packages * n_views * len(("qwen2.5:7b", "llama3.1:8b")) * SAMPLES_PER_MODEL


def build_measurement(records: list[dict], packages, samples_per_model: int = SAMPLES_PER_MODEL) -> tuple[Meas, dict]:
    n = samples_per_model * 2
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in records:
        grouped[(row["package_id"], view_key(row["view"]), int(row["sample"]))].append(row)
    hits: dict[tuple[str, str, str], int] = {}
    per_model: dict[tuple[str, str, str, str], int] = {}
    for package in packages:
        views = all_views(package.leakage_unit_ids)
        if len(views) != 57:
            raise RuntimeError(f"{package.package_id} view count {len(views)}")
        for view in views:
            key = view_key(view)
            rows = []
            for sample in range(samples_per_model):
                got = grouped.get((package.package_id, key, sample), [])
                models = {row["model"] for row in got}
                if models != {"qwen2.5:7b", "llama3.1:8b"} or len(got) != 2:
                    raise RuntimeError(f"incomplete cost grid {package.package_id} {key} sample {sample}")
                rows.extend(got)
            for target in package.targets:
                needed = set(target.unit_ids)
                total = 0
                by_model = {"qwen2.5:7b": 0, "llama3.1:8b": 0}
                for row in rows:
                    if needed <= set(row["recovered"]):
                        total += 1
                        by_model[row["model"]] += 1
                hits[(package.package_id, key, target.target_id)] = total
                for model, count in by_model.items():
                    per_model[(package.package_id, key, target.target_id, model)] = count
    meas = Meas(n, hits)
    table = _public_table(meas, packages, per_model, samples_per_model)
    return meas, table


def _public_table(meas: Meas, packages, per_model, samples_per_model: int) -> dict:
    packs = {}
    higher = []
    for package in packages:
        views_out = {}
        for view in all_views(package.leakage_unit_ids):
            key = view_key(view)
            targets_out = {}
            for target in package.targets:
                count = meas.hits[(package.package_id, key, target.target_id)]
                targets_out[target.target_id] = {
                    "hits": count,
                    "n": meas.n,
                    "h_hat": round(jeffreys(count, meas.n), 6),
                    "qwen2.5:7b": per_model[(package.package_id, key, target.target_id, "qwen2.5:7b")],
                    "llama3.1:8b": per_model[(package.package_id, key, target.target_id, "llama3.1:8b")],
                }
            views_out[key] = {"units": list(view), "targets": targets_out}
        singles = {}
        charged = {}
        for unit_id in package.leakage_unit_ids:
            base = single_base(meas, package.package_id, unit_id, package.targets)
            singles[unit_id] = round(base, 6)
            charged[unit_id] = round(MU_ADVERSARIAL * base, 6)
        packs[package.package_id] = {
            "single_base": singles,
            "charged_identity": charged,
            "views": views_out,
        }
        for target in package.targets:
            for order, view in covering_views(package.leakage_unit_ids, target.unit_ids):
                meas_cost = predicted_cost(meas, package.package_id, view, target.target_id, target.unit_ids) if len(view) <= 2 else bits(
                    meas.h(package.package_id, view, target.target_id),
                    meas.h(package.package_id, (), target.target_id),
                )
                pred = _pair_extrapolation(
                    meas,
                    package.package_id,
                    view,
                    target.target_id,
                    target.unit_ids,
                    meas.h(package.package_id, (), target.target_id),
                )
                higher.append(
                    {
                        "package_id": package.package_id,
                        "target_id": target.target_id,
                        "layer": target.layer,
                        "order": order,
                        "view": list(view),
                        "cost_meas": round(meas_cost, 6),
                        "cost_pred": round(pred, 6),
                        "delta": round(meas_cost - pred, 6),
                    }
                )
    return {
        "n_per_view": meas.n,
        "samples_per_model": samples_per_model,
        "pooling": "sum of exact-string hits across qwen2.5:7b and llama3.1:8b",
        "packages": packs,
        "higher_order": higher,
    }


def measurement_from_table(table: dict) -> Meas:
    hits = {}
    n = int(table["n_per_view"])
    for package_id, pack in table["packages"].items():
        for key, view in pack["views"].items():
            for target_id, cell in view["targets"].items():
                hits[(package_id, key, target_id)] = int(cell["hits"])
    return Meas(n, hits)
