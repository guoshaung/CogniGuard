"""Fixed student split. Who receives which unit does not depend on measured costs."""

from __future__ import annotations

from experiments.ocelot_edu_20261122_real.ocelot_edu.assets import Package
from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import N_STUDENTS, TURNS

# One private unit per student. The same map is used in every package.
ASSIGN = {0: "U4", 1: "U5", 2: "U9", 3: "U1", 4: "U8", 5: "U7"}
PUBLIC_CYCLE = ("U2", "U3", "U6")
COALITIONS = (
    {"id": "k2-expr", "k": 2, "members": (0, 1), "layers": ("表达",)},
    {"id": "k2-diag", "k": 2, "members": (3, 4), "layers": ("诊断映射",)},
    {"id": "k3-seq", "k": 3, "members": (0, 1, 2), "layers": ("顺序",)},
    {"id": "k5", "k": 5, "members": (0, 1, 2, 3, 4), "layers": ("表达", "诊断映射", "顺序")},
)


def iter_turns(package: Package):
    for student in range(N_STUDENTS):
        private_id = ASSIGN.get(student)
        for turn in range(TURNS):
            atoms = []
            if turn == 0 and private_id is not None:
                atoms.append(_atom(package, "U2", utility=True))
                atoms.append(_atom(package, private_id, utility=False))
                role = "private"
            else:
                unit_id = PUBLIC_CYCLE[(turn + student) % len(PUBLIC_CYCLE)]
                atoms.append(_atom(package, unit_id, utility=True))
                role = "public"
            yield {
                "turn_id": f"{package.package_id}-s{student:02d}-t{turn:02d}",
                "package_id": package.package_id,
                "student": student,
                "turn": turn,
                "role": role,
                "atoms": atoms,
            }


def _atom(package: Package, unit_id: str, utility: bool) -> dict:
    unit = package.unit(unit_id)
    return {
        "unit_id": unit.unit_id,
        "text": unit.content,
        "utility": utility,
        "protected": unit.protected,
        "layer_field": _layer_field(package, unit_id),
    }


def _layer_field(package: Package, unit_id: str) -> str | None:
    for target in package.targets:
        if unit_id in target.unit_ids:
            return unit_id
    return None


def holder(unit_id: str) -> int | None:
    for student, assigned in ASSIGN.items():
        if assigned == unit_id:
            return student
    return None
