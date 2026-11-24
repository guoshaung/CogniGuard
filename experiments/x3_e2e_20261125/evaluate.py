"""Score shadow arms on the controlled fixtures. No MySQL and no watermark server."""

from __future__ import annotations

import time

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.source_evidence import SourceEvidence
from cogniguard.governance.source_state import (
    JOINT_ACCEPT,
    shadow_decide,
    untrusted_mismatch,
)
from experiments.x3_e2e_20261125.scenarios import (
    FIVE,
    Scenario,
    _evidence,
    bindings,
    build_scenarios,
    target_registry,
)

ARMS = {
    "B0": {"accept": frozenset(), "fallback": True, "veto": False, "channels": ()},
    "B1": {"accept": frozenset(), "fallback": True, "veto": False, "channels": ("fingerprint",)},
    "B2": {
        "accept": frozenset({"signed_credential"}),
        "fallback": True,
        "veto": False,
        "channels": ("signed_credential",),
    },
    "B3": {
        "accept": frozenset({"trusted_log"}),
        "fallback": True,
        "veto": False,
        "channels": ("trusted_log",),
    },
    "B4": {"accept": frozenset(), "fallback": True, "veto": False, "channels": ("watermark",)},
    "B5": {"accept": frozenset(), "fallback": True, "veto": False, "channels": ("watermark",)},
    "Ours": {
        "accept": JOINT_ACCEPT - frozenset({"ideal"}),
        "fallback": True,
        "veto": True,
        "channels": ("fingerprint", "watermark", "signed_credential", "trusted_log"),
    },
    "Oracle": {
        "accept": frozenset({"ideal"}),
        "fallback": False,
        "veto": False,
        "channels": ("ideal",),
    },
}


def _needed(scenario: Scenario) -> set[str]:
    resources = {scenario.request.resource_id}
    resources.update(resource_id for resource_id, _unit in scenario.request.release_units)
    return resources


def ground_truth(scenario: Scenario, book, targets) -> dict:
    needed = _needed(scenario)
    licensed: set[str] = set()
    request = scenario.request
    for issuance_id in scenario.true_issuance_ids:
        binding = book[issuance_id]
        if binding.revoked or binding.grantee_principal_id != request.principal_id:
            continue
        if binding.purposes and request.purpose not in binding.purposes:
            continue
        if binding.resource_id not in needed:
            continue
        if not scenario.registry.is_authorized(
            request.principal_id,
            binding.resource_id,
            request.purpose,
            request.acting_org_id,
            request.now,
        ):
            continue
        licensed.add(binding.resource_id)
    covered = frozenset(request.release_units) <= frozenset(scenario.true_retained)
    verdict = check_release(
        targets,
        request.principal_id,
        request.release_units,
        scenario.true_knowledge,
        2,
    )
    allow = licensed >= needed and covered and verdict.safe
    return {
        "allow": allow,
        "licensed": licensed >= needed,
        "covered": covered,
        "coalition_safe": verdict.safe,
    }


def _rows_for(scenario: Scenario, channels: tuple[str, ...]) -> list[SourceEvidence]:
    rows: list[SourceEvidence] = []
    for name in channels:
        rows.extend(scenario.channels.get(name, ()))
    return rows


def decide(arm: str, scenario: Scenario, book, targets):
    spec = ARMS[arm]
    return shadow_decide(
        _rows_for(scenario, spec["channels"]),
        scenario.request,
        scenario.registry,
        book,
        target_registry=targets,
        knowledge=scenario.knowledge,
        accept_types=spec["accept"],
        fallback_registry=spec["fallback"],
        apply_untrusted_veto=spec["veto"],
    )


def interface_regression(scenarios: list[Scenario], book, targets) -> list[dict]:
    """Fail closed on the five historical flips, then admit a real credential."""
    found = []
    for scenario in scenarios:
        if scenario.scenario_id not in FIVE:
            continue
        watermark = shadow_decide(
            scenario.channels["watermark"],
            scenario.request,
            scenario.registry,
            book,
            target_registry=targets,
            accept_types=frozenset(),
            fallback_registry=False,
        )
        credential = _evidence(
            f"{scenario.scenario_id}-cred-regression",
            "signed_credential",
            scenario.scenario_id,
            scenario.true_issuance_ids,
            scenario.request.release_units,
        )
        signed = shadow_decide(
            [credential],
            scenario.request,
            scenario.registry,
            book,
            target_registry=targets,
            accept_types=frozenset({"signed_credential"}),
            fallback_registry=False,
        )
        found.append(
            {
                "scenario_id": scenario.scenario_id,
                "watermark_only_allowed": watermark.allowed,
                "watermark_confirmed_propagation": watermark.confirmed_propagation,
                "watermark_charged_budget": watermark.charged_budget,
                "credential_allowed": signed.allowed,
                "credential_confirmed_propagation": signed.confirmed_propagation,
                "changes_production_path": watermark.changes_production_path
                or signed.changes_production_path,
            }
        )
    return found


def _rate(numerator: int, denominator: int):
    if denominator == 0:
        return None
    return numerator / denominator


def _median(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[len(ordered) // 2]


def evaluate(scenarios: list[Scenario] | None = None) -> dict:
    scenarios = list(scenarios or build_scenarios())
    book = bindings()
    # build_scenarios injects iss-edu-s2 and iss-attr into its own dict.
    # Rebuild that injection by reading a completed scenario's ideal ids.
    book = _book_from_scenarios(scenarios)
    targets = target_registry()
    truths = {row.scenario_id: ground_truth(row, book, targets) for row in scenarios}
    rows = []
    for scenario in scenarios:
        per_arm = {}
        for arm in ARMS:
            decision = decide(arm, scenario, book, targets)
            evidence = _rows_for(scenario, ARMS[arm]["channels"])
            per_arm[arm] = {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "source_status": decision.source_status,
                "authorizing_issuance_ids": list(decision.authorizing_issuance_ids),
                "confirmed_propagation": decision.confirmed_propagation,
                "charged_budget": decision.charged_budget,
                "changes_production_path": decision.changes_production_path,
                "coalition_safe": decision.coalition_safe,
                "mismatch_reported": arm == "B5" and untrusted_mismatch(evidence, book),
            }
        truth = truths[scenario.scenario_id]
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "group": scenario.group,
                "origin": scenario.origin,
                "note": scenario.note,
                "oracle_allow": truth["allow"],
                "oracle_coalition_safe": truth["coalition_safe"],
                "true_issuance_ids": list(scenario.true_issuance_ids),
                "arms": per_arm,
            }
        )
    return {
        "scenarios": rows,
        "metrics": _metrics(rows),
        "interface_regression": interface_regression(scenarios, book, targets),
        "latency_ms": _latency(scenarios, book, targets),
        "round_decisions_stable": _rounds_stable(rows),
    }


def _book_from_scenarios(scenarios: list[Scenario]):
    book = bindings()
    from cogniguard.governance.source_state import IssuanceBinding

    if "iss-edu-s2" not in book:
        book["iss-edu-s2"] = IssuanceBinding(
            "iss-edu-s2", "edu", "s2", (("edu", "a"), ("edu", "b")), ("education",)
        )
    if "iss-attr" not in book:
        book["iss-attr"] = IssuanceBinding(
            "iss-attr",
            "profile:stu_001",
            "s1",
            (("profile:stu_001", "p2"), ("profile:stu_001", "p4")),
            ("tutoring",),
        )
    return book


def _metrics(rows: list[dict]) -> dict:
    summary = {}
    b0 = {row["scenario_id"]: row["arms"]["B0"]["allowed"] for row in rows}
    for arm in ARMS:
        unauth_hit = unauth_n = benign_hit = benign_n = 0
        wrong_attr = registry_over = extra = coalition_bad = allows = 0
        confirmed = charged = 0
        for row in rows:
            decision = row["arms"][arm]
            truth = row["oracle_allow"]
            if truth:
                benign_n += 1
                benign_hit += int(decision["allowed"])
            else:
                unauth_n += 1
                unauth_hit += int(decision["allowed"])
            if decision["allowed"]:
                allows += 1
                if not row["oracle_coalition_safe"]:
                    coalition_bad += 1
            attributed = set(decision["authorizing_issuance_ids"])
            true_ids = _true_ids(row["scenario_id"], rows)
            if decision["allowed"] and not truth and attributed and not attributed <= true_ids:
                wrong_attr += 1
            if decision["allowed"] and not truth and not attributed:
                registry_over += 1
            if decision["allowed"] == truth and b0[row["scenario_id"]] != truth:
                extra += 1
            confirmed += int(decision["confirmed_propagation"])
            charged += int(decision["charged_budget"])
        summary[arm] = {
            "unauthorized_success": _rate(unauth_hit, unauth_n),
            "unauthorized_success_count": [unauth_hit, unauth_n],
            "benign_success": _rate(benign_hit, benign_n),
            "false_reject": _rate(benign_n - benign_hit, benign_n),
            "coalition_violation_among_allows": _rate(coalition_bad, allows),
            "wrong_attribution_authorization_count": wrong_attr,
            "wrong_attribution_authorization_rate": _rate(wrong_attr, unauth_n),
            "registry_allow_without_true_issuance_count": registry_over,
            "additional_correct_vs_b0": extra,
            "confirmed_propagation_count": confirmed,
            "charged_budget_count": charged,
        }
    return summary


def _true_ids(scenario_id: str, rows: list[dict]) -> set[str]:
    # The authorizing ids are compared with the scenario's ideal channel, which
    # lists the true issuance ids. Stored on the row by evaluate.
    for row in rows:
        if row["scenario_id"] == scenario_id:
            return set(row.get("true_issuance_ids", ()))
    return set()


def _latency(scenarios, book, targets) -> dict:
    samples = {arm: [] for arm in ARMS}
    for _ in range(5):
        started = {arm: time.perf_counter() for arm in ARMS}
        counts = {arm: 0 for arm in ARMS}
        for scenario in scenarios:
            for arm in ARMS:
                before = time.perf_counter()
                decide(arm, scenario, book, targets)
                samples[arm].append((time.perf_counter() - before) * 1000.0)
                counts[arm] += 1
        del started, counts
    medians = {arm: _median(samples[arm]) for arm in ARMS}
    base = medians["B0"] or 1e-9
    return {
        "median_ms": medians,
        "overhead_vs_b0": {arm: medians[arm] / base for arm in ARMS},
    }


def _rounds_stable(rows: list[dict]) -> bool:
    picked = [row for row in rows if row["scenario_id"] in {"rounds-1", "rounds-3", "rounds-5"}]
    if len(picked) != 3:
        return False
    first = picked[0]["arms"]
    return all(row["arms"][arm]["allowed"] == first[arm]["allowed"] for row in picked for arm in ARMS)


