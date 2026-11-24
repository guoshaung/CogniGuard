"""Complete protection targets from an owner policy, a schema, and visible fields.

The Protocol B gate registered one E7 secret per scenario (largest domain, then
a fixed name order) or, if that secret was missing, one witness containing every
table named in the defense line. A minimal witness of a different declared
attribute was dropped, and a witness already held by the asking agent was still
the only registered target.

This module enumerates every determined attribute inside the declared
combination. It does not read attack plans, attack goals, or final inferences.
Those fields may be scored later by an audit; they are not arguments here.

Join rule, unchanged from the frozen E7 generator: same-name columns that end
in ``_id``. A candidate is undetermined, and is not registered, when joining on
every shared column name changes the minimal witness sets. A column that one
table already determines is recorded and not promoted: the owner declared a
combination, not that single table.

Leak classes of a witness, given two disjoint holding sets supplied by the caller:

- ``initial_held``: every unit is already held before the gated system runs.
- ``external_propagation``: not initial, but every unit is initial or arrived
  from outside the gated system.
- ``system_new``: some unit is in neither set, so only a new disclosure from
  this system can finish the witness.

A target takes the class of its easiest witness. Already-known targets are not
registered: ``check_release`` blocks a release that touches a witness the
recipient already holds.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cogniguard.governance.targets import ProtectedTarget

UnitRef = tuple[str, str]
CLAIM = re.compile(r"\bcombination of (.+?) is sensitive\b", re.I)
MAX_TABLES = 12
SOURCE_SCHEMA = "schema_attribute"
SOURCE_POLICY = "policy_combination"
CLASS_INITIAL = "initial_held"
CLASS_EXTERNAL = "external_propagation"
CLASS_SYSTEM = "system_new"


def _key(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def declared_names(sentence: str, names: set[str]) -> tuple[str, ...]:
    """Table names in the last ``combination of ... is sensitive`` clause.

    A reasoning preamble is ignored. Tokens that are not table names are
    dropped. This is the owner policy, not a guess at an attack target.
    """
    clauses = CLAIM.findall(sentence or "")
    if not clauses:
        return ()
    bits = re.split(r",\s*(?:and\s+)?|\s+and\s+", clauses[-1])
    found: list[str] = []
    for bit in bits:
        cleaned = re.sub(r"^.*?['’]s\s+", "", bit.strip()).strip("' `*\"")
        if cleaned in names and cleaned not in found:
            found.append(cleaned)
    return tuple(found)


def load_tables(data_distribution: Mapping) -> list[dict]:
    """Tables and columns from ``data_distribution`` only."""
    tables = []
    for agent, obj in sorted(data_distribution.items()):
        table_map = (obj or {}).get("table") or {}
        for name, table in sorted(table_map.items()):
            rows = [dict(row) for row in (table.get("rows") or [])]
            columns = sorted({col for row in rows for col in row})
            tables.append({
                "unit_id": f"{agent}.{name}",
                "agent": agent,
                "name": name,
                "sensitive": table.get("sensitivity") == "sensitive",
                "rows": rows,
                "columns": columns,
            })
    return tables


def default_visible_fields(tables: Iterable[dict]) -> frozenset[tuple[str, str]]:
    """Identifier columns on tables the schema does not mark sensitive.

    The values are public anchors. The rest of a public row is not visible:
    a later join still has to hold the table that stores the pairing.
    """
    fields = []
    for table in tables:
        if table["sensitive"]:
            continue
        for column in table["columns"]:
            if column.endswith("_id"):
                fields.append((table["unit_id"], column))
    return frozenset(fields)


def units_owned_by(tables: Iterable[dict], agent: str) -> frozenset[str]:
    return frozenset(table["unit_id"] for table in tables if table["agent"] == agent)


def _join_columns(tables, *, ids_only: bool) -> frozenset[str]:
    counts: Counter[str] = Counter()
    for table in tables:
        counts.update(table["columns"])
    shared = {col for col, count in counts.items() if count >= 2}
    if ids_only:
        return frozenset(col for col in shared if col.endswith("_id"))
    return frozenset(shared)


def _reach(tables, held: frozenset[int], joins, seeds, seed_cols, target_idx, target_col):
    """Values of ``target_col`` reachable from the visible seeds through ``held``."""
    known = set(seeds)
    matched: set[tuple[int, int]] = set()
    changed = True
    while changed:
        changed = False
        for index in held:
            for row_index, row in enumerate(tables[index]["rows"]):
                if (index, row_index) in matched:
                    continue
                hit = False
                for column, value in row.items():
                    if column not in joins and column not in seed_cols:
                        continue
                    if (column, _key(value)) in known:
                        hit = True
                        break
                if not hit:
                    continue
                matched.add((index, row_index))
                changed = True
                for column, value in row.items():
                    if column not in joins:
                        continue
                    pair = (column, _key(value))
                    if pair not in known:
                        known.add(pair)
                        changed = True
    if target_idx not in held:
        return set()
    found = set()
    for index, row_index in matched:
        if index != target_idx:
            continue
        row = tables[index]["rows"][row_index]
        if target_col in row and row[target_col] is not None:
            found.add(_key(row[target_col]))
    return found


def _leakage(tables, joins, seeds, seed_cols, target_idx, target_col, domain):
    size = len(domain)
    out = {}
    for mask in range(1 << len(tables)):
        held = frozenset(i for i in range(len(tables)) if mask >> i & 1)
        values = _reach(
            tables, held, joins, seeds, seed_cols, target_idx, target_col
        ) & domain
        out[mask] = math.log2(size / len(values)) if values else 0.0
    return out


def _minimal_masks(leakage: dict[int, float], n: int, tau: float) -> list[int]:
    star: dict[int, float] = {}
    found = []
    for mask in sorted(leakage, key=lambda item: (item.bit_count(), item)):
        previous = max(
            (star[mask ^ (1 << bit)] for bit in range(n) if mask >> bit & 1),
            default=0.0,
        )
        star[mask] = max(leakage[mask], previous)
        if previous <= tau < star[mask]:
            found.append(mask)
    return found


def classify_units(units: Iterable[str], initial: set[str], external: set[str]) -> str:
    held = set(units)
    if held <= initial:
        return CLASS_INITIAL
    if held <= initial | external:
        return CLASS_EXTERNAL
    return CLASS_SYSTEM


def _target_class(classes: Iterable[str]) -> str:
    found = set(classes)
    if CLASS_INITIAL in found:
        return CLASS_INITIAL
    if CLASS_EXTERNAL in found:
        return CLASS_EXTERNAL
    return CLASS_SYSTEM


@dataclass(frozen=True)
class KnowledgeWitness:
    units: frozenset[UnitRef]
    leak_class: str

    @property
    def unit_ids(self) -> frozenset[str]:
        return frozenset(unit_id for _resource, unit_id in self.units)


@dataclass(frozen=True)
class CandidateTarget:
    target_id: str
    source: str
    table_unit: str
    column: str
    anchor_column: str
    witnesses: tuple[KnowledgeWitness, ...]
    leak_class: str
    domain_size: int | None
    status: str

    def witness_unit_sets(self) -> tuple[frozenset[str], ...]:
        return tuple(witness.unit_ids for witness in self.witnesses)


@dataclass(frozen=True)
class ProtectionPlan:
    scene_id: str
    resource_id: str
    parse_status: str
    declared_names: tuple[str, ...]
    declared_units: tuple[str, ...]
    initial_units: tuple[str, ...]
    external_units: tuple[str, ...]
    targets: tuple[CandidateTarget, ...]
    single_table_excluded: int
    undetermined_excluded: int
    truncated: bool
    complexity: dict

    def targets_of_class(self, leak_class: str) -> tuple[CandidateTarget, ...]:
        return tuple(target for target in self.targets if target.leak_class == leak_class)


def _anchor_values(tables, visible: frozenset[tuple[str, str]]):
    by_unit = {table["unit_id"]: table for table in tables}
    found: dict[str, set[str]] = {}
    for unit_id, column in visible:
        table = by_unit.get(unit_id)
        if table is None or column not in table["columns"]:
            continue
        for row in table["rows"]:
            value = row.get(column)
            if value is None or value == "":
                continue
            found.setdefault(column, set()).add(_key(value))
    return {column: tuple(sorted(values)) for column, values in sorted(found.items())}


def _masks_to_witnesses(masks, tables, resource_id, initial, external):
    witnesses = []
    for mask in masks:
        refs = frozenset(
            (resource_id, tables[index]["unit_id"])
            for index in range(len(tables))
            if mask >> index & 1
        )
        unit_ids = [unit_id for _resource, unit_id in refs]
        witnesses.append(KnowledgeWitness(
            refs, classify_units(unit_ids, initial, external)
        ))
    witnesses.sort(key=lambda item: (len(item.units), tuple(sorted(item.units))))
    return tuple(witnesses)


def _policy_target(tables, declared, resource_id, initial, external, scene_id):
    units = [table for table in tables if table["name"] in declared]
    if len(units) < 2:
        return None
    refs = frozenset((resource_id, table["unit_id"]) for table in units)
    witness = KnowledgeWitness(
        refs, classify_units((table["unit_id"] for table in units), initial, external)
    )
    return CandidateTarget(
        target_id=f"{scene_id}:policy",
        source=SOURCE_POLICY,
        table_unit="",
        column="",
        anchor_column="",
        witnesses=(witness,),
        leak_class=witness.leak_class,
        domain_size=None,
        status="policy",
    )


def generate_protection_plan(
    data_distribution: Mapping,
    defense: str,
    *,
    visible_fields: Iterable[tuple[str, str]] | None = None,
    initial_units: Iterable[str] | None = None,
    external_units: Iterable[str] | None = None,
    resource_id: str = "sl",
    scene_id: str = "scene",
) -> ProtectionPlan:
    """Minimal witnesses for every declared attribute the schema determines.

    ``visible_fields`` defaults to ``*_id`` columns on non-sensitive tables.
    ``initial_units`` and ``external_units`` are unit ids (``Agent.table``).
    Units that are not in the schema are ignored and counted.
    """
    started = time.perf_counter()
    tables = load_tables(data_distribution)
    names = {table["name"] for table in tables}
    declared = declared_names(defense, names)
    if not CLAIM.findall(defense or ""):
        parse_status = "no_clause"
    else:
        parse_status = "full" if declared else "unmatched"
    schema_units = {table["unit_id"] for table in tables}
    initial = {unit for unit in (initial_units or ()) if unit in schema_units}
    external = {
        unit for unit in (external_units or ())
        if unit in schema_units and unit not in initial
    }
    ignored_initial = len(set(initial_units or ())) - len(initial)
    ignored_external = len({
        unit for unit in (external_units or ()) if unit not in initial
    }) - len(external)
    visible = (
        frozenset(visible_fields)
        if visible_fields is not None
        else default_visible_fields(tables)
    )
    declared_units = tuple(
        table["unit_id"] for table in tables if table["name"] in set(declared)
    )
    truncated = len(tables) > MAX_TABLES
    probes = 0
    mask_evaluations = 0
    single_table = 0
    undetermined = 0
    targets: list[CandidateTarget] = []
    if declared and not truncated:
        id_joins = _join_columns(tables, ids_only=True)
        broad_joins = _join_columns(tables, ids_only=False)
        anchors = _anchor_values(tables, visible)
        declared_set = set(declared)
        for target_index, table in enumerate(tables):
            if table["name"] not in declared_set:
                continue
            for column in table["columns"]:
                if column.endswith("_id"):
                    continue
                domain = {
                    _key(row[column])
                    for row in table["rows"]
                    if column in row and row[column] is not None
                }
                if len(domain) < 2:
                    continue
                tau = max(math.log2(len(domain)) - 1, 0.5)
                for anchor_column, values in anchors.items():
                    for anchor_key in values:
                        seeds = {(anchor_column, anchor_key)}
                        seed_cols = frozenset({anchor_column})
                        everything = frozenset(range(len(tables)))
                        probes += 1
                        full = _reach(
                            tables, everything, id_joins, seeds, seed_cols,
                            target_index, column,
                        ) & domain
                        if len(full) != 1:
                            continue
                        leakage = _leakage(
                            tables, id_joins, seeds, seed_cols,
                            target_index, column, domain,
                        )
                        masks = _minimal_masks(leakage, len(tables), tau)
                        mask_evaluations += 1 << len(tables)
                        if not masks or min(mask.bit_count() for mask in masks) < 2:
                            single_table += 1
                            continue
                        broad = _leakage(
                            tables, broad_joins, seeds, seed_cols,
                            target_index, column, domain,
                        )
                        broad_masks = _minimal_masks(broad, len(tables), tau)
                        mask_evaluations += 1 << len(tables)
                        if broad_masks != masks:
                            undetermined += 1
                            continue
                        witnesses = _masks_to_witnesses(
                            masks, tables, resource_id, initial, external
                        )
                        token = hashlib.sha256(
                            f"{anchor_column}:{anchor_key}".encode()
                        ).hexdigest()[:16]
                        targets.append(CandidateTarget(
                            target_id=(
                                f"{scene_id}:attr:{table['unit_id']}:{column}:"
                                f"{anchor_column}:{token}"
                            ),
                            source=SOURCE_SCHEMA,
                            table_unit=table["unit_id"],
                            column=column,
                            anchor_column=anchor_column,
                            witnesses=witnesses,
                            leak_class=_target_class(
                                witness.leak_class for witness in witnesses
                            ),
                            domain_size=len(domain),
                            status="computed",
                        ))
    policy = None
    if not any(target.source == SOURCE_SCHEMA for target in targets):
        policy = _policy_target(
            tables, set(declared), resource_id, initial, external, scene_id
        )
        if policy is not None:
            targets.append(policy)
    targets.sort(key=lambda item: item.target_id)
    classes = Counter(target.leak_class for target in targets)
    sizes = Counter(
        len(witness.units) for target in targets for witness in target.witnesses
    )
    families = {
        tuple(sorted(target.witness_unit_sets())) for target in targets
    }
    complexity = {
        "tables": len(tables),
        "declared_tables": len(declared_units),
        "full_join_probes": probes,
        "mask_evaluations": mask_evaluations,
        "targets": len(targets),
        "schema_targets": sum(target.source == SOURCE_SCHEMA for target in targets),
        "policy_targets": sum(target.source == SOURCE_POLICY for target in targets),
        "distinct_witness_families": len(families),
        "system_new": classes[CLASS_SYSTEM],
        "initial_held": classes[CLASS_INITIAL],
        "external_propagation": classes[CLASS_EXTERNAL],
        "single_table_excluded": single_table,
        "undetermined_excluded": undetermined,
        "witness_size_histogram": {str(k): sizes[k] for k in sorted(sizes)},
        "ignored_initial_units": ignored_initial,
        "ignored_external_units": ignored_external,
        "truncated": truncated,
        "seconds": round(time.perf_counter() - started, 6),
    }
    return ProtectionPlan(
        scene_id=str(scene_id),
        resource_id=resource_id,
        parse_status=parse_status,
        declared_names=declared,
        declared_units=declared_units,
        initial_units=tuple(sorted(initial)),
        external_units=tuple(sorted(external)),
        targets=tuple(targets),
        single_table_excluded=single_table,
        undetermined_excluded=undetermined,
        truncated=truncated,
        complexity=complexity,
    )


def from_scenario_record(record: Mapping, **kwargs) -> ProtectionPlan:
    """Read only the owner line and the database. Extra keys are not used."""
    scene = kwargs.pop("scene_id", None)
    if scene is None and "scene" in record:
        scene = str(record["scene"])
    return generate_protection_plan(
        record["data_distribution"],
        record.get("defense", ""),
        scene_id=scene or "scene",
        **kwargs,
    )


def gate_targets(
    plan: ProtectionPlan,
    *,
    owner_principal_id: str = "owner",
    org_id: str = "org",
) -> tuple[ProtectedTarget, ...]:
    """System-new targets only, as kernel ``ProtectedTarget`` values.

    Initial holdings and external propagation are omitted. Registering them
    makes ``check_release`` refuse a release that merely mentions a witness
    the recipient already completed.
    """
    built = []
    for target in plan.targets_of_class(CLASS_SYSTEM):
        domain = target.domain_size if target.domain_size and target.domain_size >= 2 else None
        built.append(ProtectedTarget(
            target.target_id,
            owner_principal_id,
            org_id,
            tuple(witness.units for witness in target.witnesses),
            kind="student_attribute",
            domain_size=domain,
        ))
    return tuple(built)


def knowledge_units(plan: ProtectionPlan) -> frozenset[UnitRef]:
    """Units the recipient already holds: initial holdings plus external ones."""
    held = set(plan.initial_units) | set(plan.external_units)
    return frozenset((plan.resource_id, unit_id) for unit_id in held)
