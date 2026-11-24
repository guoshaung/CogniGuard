"""Same-information comparison and an enumeration check that does not call the DP.

Oracle safety is brute-force subset coverage on the planted holdings. Methods
see one shared admission of those holdings. ``trusted_event`` uses
``SourceEvidence.is_trusted_event`` and admits only a trusted log, which is
the existing shadow rule kept as a control. ``all_candidates`` admits every
verified holding and is a comparison view, not a change to that rule.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable

from cogniguard.governance.reconstruction import check_release
from cogniguard.governance.source_evidence import SourceEvidence

from experiments.nowm_scenarios_20261125.scenarios import (
    ORG, NOW, Ask, World, build, target_ids, witness_sizes,
)

INFOS = ("receipts", "trusted_event", "all_candidates")
RULES = ("capd", "union", "quota", "pairwise", "recipient_only")
KS = (1, 2, 3)


def admitted_units(row: SourceEvidence, info: str) -> tuple[tuple[str, str], ...]:
    if info == "receipts":
        return ()
    if info == "trusted_event":
        if row.evidence_type not in {"trusted_log", "ideal"} or not row.holder_principal_id:
            return ()
        if not row.is_trusted_event():
            return ()
        return row.trusted_units()
    if info == "all_candidates":
        if row.verification_status != "verified" or not row.holder_principal_id:
            return ()
        return row.matched_knowledge_units
    raise ValueError(info)


def knowledge_view(world: World, info: str) -> dict[str, frozenset]:
    merged = {name: set(units) for name, units in world.receipt_units.items()}
    for row in world.evidence:
        if not row.holder_principal_id:
            continue
        holder = merged.setdefault(row.holder_principal_id, set())
        holder.update(admitted_units(row, info))
    return {name: frozenset(units) for name, units in merged.items()}


def _affected(world: World, release: Iterable[tuple[str, str]]):
    found = {}
    for unit in release:
        for target in world.registry.targets_for_unit(unit):
            found.setdefault(target.target_id, target)
    return tuple(found[target_id] for target_id in sorted(found))


def brute_safe(world: World, ask: Ask, knowledge: dict[str, frozenset], k: int) -> bool:
    """True when no coalition of size at most k that contains the recipient covers a witness."""
    if k < 1:
        raise ValueError(k)
    held = {name: set(units) for name, units in knowledge.items()}
    mine = held.setdefault(ask.principal_id, set())
    mine.add(ask.unit)
    others = [name for name in sorted(held) if name != ask.principal_id]
    for target in _affected(world, (ask.unit,)):
        for witness in target.witness_sets:
            if witness <= mine:
                return False
            for size in range(1, k):
                for combo in itertools.combinations(others, size):
                    view = set(mine)
                    for name in combo:
                        view.update(held[name])
                    if witness <= view:
                        return False
    return True


def _authorized(world: World, ask: Ask) -> bool:
    return world.access.is_authorized(
        ask.principal_id, ask.unit[0], world.purpose, ORG, NOW,
    )


def quota_safe(world: World, ask: Ask, knowledge: dict[str, frozenset], k: int) -> bool:
    """WS04 Sec. 8 cap on the recipient's own units. Other holders are not read."""
    mine = set(knowledge.get(ask.principal_id, ()))
    mine.add(ask.unit)
    for target in _affected(world, (ask.unit,)):
        for witness in target.witness_sets:
            cap = (len(witness) - 1) // k
            if len(mine & witness) > cap:
                return False
    return True


def union_safe(world: World, ask: Ask, knowledge: dict[str, frozenset]) -> bool:
    """Deny when the union of every holder, plus the release, covers a witness."""
    pooled: set[tuple[str, str]] = set()
    for units in knowledge.values():
        pooled.update(units)
    pooled.add(ask.unit)
    for target in _affected(world, (ask.unit,)):
        for witness in target.witness_sets:
            if witness <= pooled:
                return False
    return True


def rule_safe(world: World, rule: str, ask: Ask, knowledge: dict[str, frozenset], k: int) -> bool:
    if not _authorized(world, ask):
        return False
    if rule == "capd":
        return check_release(world.registry, ask.principal_id, (ask.unit,), knowledge, k).safe
    if rule == "union":
        return union_safe(world, ask, knowledge)
    if rule == "quota":
        return quota_safe(world, ask, knowledge, k)
    if rule == "pairwise":
        return check_release(world.registry, ask.principal_id, (ask.unit,), knowledge, 2).safe
    if rule == "recipient_only":
        return check_release(world.registry, ask.principal_id, (ask.unit,), knowledge, 1).safe
    raise ValueError(rule)


def _covers(
    world: World, ask: Ask, knowledge: dict[str, frozenset],
    coalition: tuple[str, ...], witness,
) -> bool:
    held = {name: set(units) for name, units in knowledge.items()}
    held.setdefault(ask.principal_id, set()).add(ask.unit)
    view: set[tuple[str, str]] = set()
    for name in coalition:
        view.update(held.get(name, ()))
    return witness <= view


def enumeration_mismatches(world: World) -> tuple[list[dict], int]:
    """Compare check_release with brute force on every information view, including planted truth."""
    mismatches = []
    checks = 0
    views = {info: knowledge_view(world, info) for info in INFOS}
    views["planted"] = knowledge_view(world, "all_candidates")
    for info, knowledge in views.items():
        for k in KS:
            for ask in world.requests:
                checks += 1
                verdict = check_release(
                    world.registry, ask.principal_id, (ask.unit,), knowledge, k,
                )
                brute = brute_safe(world, ask, knowledge, k)
                if verdict.safe != brute:
                    mismatches.append({
                        "domain": world.domain, "info": info, "k": k,
                        "request_id": ask.request_id, "check_release": verdict.safe,
                        "brute": brute,
                    })
                    continue
                if verdict.safe:
                    continue
                for item in verdict.violations:
                    if item.reason == "too_large":
                        mismatches.append({
                            "domain": world.domain, "info": info, "k": k,
                            "request_id": ask.request_id, "problem": "too_large",
                        })
                        continue
                    if ask.principal_id not in item.coalition or len(item.coalition) > k:
                        mismatches.append({
                            "domain": world.domain, "info": info, "k": k,
                            "request_id": ask.request_id, "problem": "coalition",
                        })
                    elif not _covers(world, ask, knowledge, item.coalition, item.witness):
                        mismatches.append({
                            "domain": world.domain, "info": info, "k": k,
                            "request_id": ask.request_id, "problem": "uncovered",
                        })
    return mismatches, checks


def _oracle(world: World, ask: Ask, planted: dict[str, frozenset], k: int) -> bool:
    return _authorized(world, ask) and brute_safe(world, ask, planted, k)


def evaluate_world(world: World) -> dict:
    planted = knowledge_view(world, "all_candidates")
    mismatches, checks = enumeration_mismatches(world)
    rows = []
    for k in KS:
        oracle = {ask.request_id: _oracle(world, ask, planted, k) for ask in world.requests}
        for info in INFOS:
            knowledge = knowledge_view(world, info)
            for rule in RULES:
                decisions = {}
                harmful = false_refusal = unauthorized_success = 0
                for ask in world.requests:
                    allowed = rule_safe(world, rule, ask, knowledge, k)
                    decisions[ask.request_id] = allowed
                    is_oracle = oracle[ask.request_id]
                    if allowed and not _authorized(world, ask):
                        unauthorized_success += 1
                    if allowed and _authorized(world, ask) and not is_oracle:
                        harmful += 1
                    if (not allowed) and is_oracle:
                        false_refusal += 1
                allows = sum(oracle.values())
                rows.append({
                    "domain": world.domain,
                    "k": k,
                    "info": info,
                    "rule": rule,
                    "oracle_allows": allows,
                    "oracle_denies": len(world.requests) - allows,
                    "harmful": harmful,
                    "false_refusal": false_refusal,
                    "unauthorized_success": unauthorized_success,
                    "utility": (allows - false_refusal) / allows if allows else None,
                    "decisions": decisions,
                })
    return {
        "domain": world.domain,
        "witness_sizes": witness_sizes(world),
        "rows": rows,
        "mismatches": mismatches,
        "enumeration_checks": checks,
    }


def _row(report: dict, domain: str, k: int, info: str, rule: str) -> dict:
    for row in report["rows"]:
        if (row["domain"], row["k"], row["info"], row["rule"]) == (domain, k, info, rule):
            return row
    raise KeyError((domain, k, info, rule))


def structural_findings(report: dict) -> dict:
    """Counts that separate extra information from a same-evidence rule difference."""
    findings = []
    for domain in ("teacher", "student"):
        for k in KS:
            capd_receipts = _row(report, domain, k, "receipts", "capd")
            capd_trusted = _row(report, domain, k, "trusted_event", "capd")
            capd_all = _row(report, domain, k, "all_candidates", "capd")
            union_all = _row(report, domain, k, "all_candidates", "union")
            quota_all = _row(report, domain, k, "all_candidates", "quota")
            pairwise = _row(report, domain, k, "all_candidates", "pairwise")
            evidence_flips = sorted(
                request_id for request_id, allowed in capd_receipts["decisions"].items()
                if allowed and not capd_all["decisions"][request_id]
            )
            trusted_flips = sorted(
                request_id for request_id, allowed in capd_receipts["decisions"].items()
                if allowed and not capd_trusted["decisions"][request_id]
            )
            union_stricter = sorted(
                request_id for request_id, allowed in capd_all["decisions"].items()
                if allowed and not union_all["decisions"][request_id]
            )
            quota_over_refuse = sorted(
                request_id for request_id, allowed in capd_all["decisions"].items()
                if allowed and not quota_all["decisions"][request_id]
            )
            quota_miss = sorted(
                request_id for request_id, allowed in quota_all["decisions"].items()
                if allowed and not capd_all["decisions"][request_id]
            )
            findings.append({
                "domain": domain,
                "k": k,
                "oracle_allows": capd_all["oracle_allows"],
                "oracle_denies": capd_all["oracle_denies"],
                "evidence_flips": evidence_flips,
                "trusted_event_flips": trusted_flips,
                "capd_all_harmful": capd_all["harmful"],
                "capd_all_false_refusal": capd_all["false_refusal"],
                "capd_all_utility": capd_all["utility"],
                "trusted_event_harmful": capd_trusted["harmful"],
                "union_stricter_than_capd": union_stricter,
                "quota_refuses_capd_allow": quota_over_refuse,
                "quota_allows_capd_deny": quota_miss,
                "pairwise_matches_capd": pairwise["decisions"] == capd_all["decisions"],
            })
    return {"cells": findings}


def nondegeneracy_failures(report: dict) -> list[str]:
    failures = []
    if report["mismatches"]:
        failures.append(f"enumeration mismatches: {len(report['mismatches'])}")
    sizes = {}
    for domain in ("teacher", "student"):
        world = build(domain)
        sizes[domain] = witness_sizes(world)
        if any(size < 3 or size > 5 for size in sizes[domain]):
            failures.append(f"{domain} witness size outside 3-5: {sizes[domain]}")
        units: dict[tuple[str, str], int] = {}
        for target_id in target_ids(domain):
            for witness in world.registry.get(target_id).witness_sets:
                for unit in witness:
                    units[unit] = units.get(unit, 0) + 1
        if not any(count > 1 for count in units.values()):
            failures.append(f"{domain} witnesses do not overlap")
        content = [
            row for row in world.evidence
            if row.evidence_type == "watermark" and row.verification_status == "verified"
        ]
        if len(content) < 2:
            failures.append(f"{domain} has fewer than two content holdings")
    cells = structural_findings(report)["cells"]
    for cell in cells:
        if cell["oracle_allows"] == 0 or cell["oracle_denies"] == 0:
            failures.append(f"{cell['domain']} k={cell['k']} oracle is one-sided")
        if cell["capd_all_harmful"] != 0 or cell["capd_all_false_refusal"] != 0:
            failures.append(
                f"{cell['domain']} k={cell['k']} capd on all candidates is not the oracle"
            )
        if cell["k"] == 2 and not cell["pairwise_matches_capd"]:
            failures.append(f"{cell['domain']} pairwise diverges from capd at k=2")
        if cell["k"] == 1 and (
            cell["quota_refuses_capd_allow"] or cell["quota_allows_capd_deny"]
        ):
            failures.append(f"{cell['domain']} k=1 quota diverges from capd")
    for domain in ("teacher", "student"):
        domain_cells = [cell for cell in cells if cell["domain"] == domain]
        if not any(cell["evidence_flips"] for cell in domain_cells):
            failures.append(f"{domain} content admission never changes capd")
        if not any(
            set(cell["trusted_event_flips"]) != set(cell["evidence_flips"])
            and cell["evidence_flips"]
            for cell in domain_cells
        ):
            failures.append(f"{domain} trusted-event control matches full admission")
        if not any(cell["union_stricter_than_capd"] for cell in domain_cells):
            failures.append(f"{domain} capd never allows where union denies")
        if not any(cell["quota_refuses_capd_allow"] for cell in domain_cells):
            failures.append(f"{domain} quota never over-refuses")
        if not any(cell["quota_allows_capd_deny"] for cell in domain_cells):
            failures.append(f"{domain} quota never misses a capd deny")
    return failures


def full_report() -> dict:
    worlds = [build(domain) for domain in ("teacher", "student")]
    rows = []
    mismatches = []
    witness = {}
    checks = 0
    for world in worlds:
        piece = evaluate_world(world)
        witness[world.domain] = piece["witness_sizes"]
        rows.extend(piece["rows"])
        mismatches.extend(piece["mismatches"])
        checks += piece["enumeration_checks"]
    report = {
        "witness_sizes": witness,
        "rows": rows,
        "mismatches": mismatches,
        "enumeration_checks": checks,
    }
    report["findings"] = structural_findings(report)
    report["failures"] = nondegeneracy_failures(report)
    return report
