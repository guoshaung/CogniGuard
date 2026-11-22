"""Read the external asset pack. Nothing from the pack is written back out."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import ASSET_SHA256, LAYER_OF_TYPE
from experiments.ocelot_edu_20261122_real.ocelot_edu.textutil import norm

REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parents[1]


def asset_root() -> Path:
    override = os.environ.get("OCELOT_ASSET_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (REPO.parent / "C2RAG_5_Pedagogical_Assets_Pilot_v1").resolve()


@dataclass(frozen=True)
class UnitRec:
    package_id: str
    unit_id: str
    role: str
    visibility: str
    content: str

    @property
    def protected(self) -> bool:
        return self.visibility == "POLICY_PROTECTED"

    def __repr__(self) -> str:
        return f"UnitRec({self.package_id},{self.unit_id},{self.role},{self.visibility},chars={len(self.content)})"


@dataclass(frozen=True)
class TargetRec:
    package_id: str
    target_id: str
    type: str
    layer: str
    unit_ids: tuple[str, ...]
    success_condition: str
    exclusions: str

    def __repr__(self) -> str:
        return f"TargetRec({self.package_id},{self.target_id},{self.layer},units={self.unit_ids})"


@dataclass(frozen=True)
class Package:
    package_id: str
    domain: str
    units: tuple[UnitRec, ...]
    targets: tuple[TargetRec, ...]
    public_knowledge: tuple[str, ...]
    leakage_unit_ids: tuple[str, ...]

    def unit(self, unit_id: str) -> UnitRec:
        for item in self.units:
            if item.unit_id == unit_id:
                return item
        raise KeyError(unit_id)

    def __repr__(self) -> str:
        return f"Package({self.package_id},{self.domain},units={len(self.units)},targets={len(self.targets)})"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def assert_pack(root: Path | None = None) -> Path:
    root = root or asset_root()
    script = root / "validate_assets.py"
    proc = subprocess.run(
        [sys.executable, "-I", str(script), str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip().startswith("PASS"):
        raise RuntimeError((proc.stdout + proc.stderr)[:500])
    for name, expected in ASSET_SHA256.items():
        got = _sha256(root / name)
        if got != expected:
            raise RuntimeError(f"asset hash mismatch for {name}")
    return root


_CACHE: dict[str, tuple] = {}


def load_packages(root: Path | None = None) -> tuple[Package, ...]:
    root = (root or asset_root()).resolve()
    cached = _CACHE.get(str(root))
    if cached is not None:
        return cached
    assert_pack(root)
    rows = [
        json.loads(line)
        for line in (root / "pedagogical_assets_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    packages = []
    for row in rows:
        units = tuple(
            UnitRec(
                package_id=row["package_id"],
                unit_id=unit["unit_id"],
                role=unit["role"],
                visibility=unit["visibility"],
                content=unit["content"],
            )
            for unit in row["units"]
        )
        targets = []
        for target in row["protected_targets"]:
            kind = target["type"]
            if kind not in LAYER_OF_TYPE:
                raise RuntimeError(f"unknown target type {kind}")
            targets.append(
                TargetRec(
                    package_id=row["package_id"],
                    target_id=target["target_id"],
                    type=kind,
                    layer=LAYER_OF_TYPE[kind],
                    unit_ids=tuple(target["unit_ids"]),
                    success_condition=target["success_condition"],
                    exclusions=target["exclusions"],
                )
            )
        leakage = tuple(row["evaluation_protocol"]["leakage_target_units"])
        packages.append(
            Package(
                package_id=row["package_id"],
                domain=row["domain"],
                units=units,
                targets=tuple(targets),
                public_knowledge=tuple(row["public_knowledge"]),
                leakage_unit_ids=leakage,
            )
        )
    loaded = tuple(packages)
    _CACHE[str(root)] = loaded
    return loaded


def secret_strings(packages: tuple[Package, ...] | None = None) -> tuple[str, ...]:
    """Strings that must not be written into the repository."""
    if packages is None and "_secrets" in _CACHE:
        return _CACHE["_secrets"]
    if packages is None:
        load_packages()
    found: list[str] = []
    root = asset_root()
    for name in ("pedagogical_assets_v1.jsonl", "public_only_baseline_v1.jsonl", "seed_queries_v1.jsonl"):
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            _collect_strings(json.loads(line), found)
    for row in json.loads((root / "sanity_checks.json").read_text(encoding="utf-8")).get("sanity_checks", {}).values():
        _collect_strings(row, found)
    # Keep only strings long enough to be prose rather than an id.
    out = []
    seen = set()
    for item in found:
        if not isinstance(item, str):
            continue
        key = norm(item)
        if len(key) < 24 or key in seen:
            continue
        if not any("\u4e00" <= ch <= "\u9fff" for ch in item):
            continue
        seen.add(key)
        out.append(item)
    loaded = tuple(out)
    if packages is None:
        _CACHE["_secrets"] = loaded
    return loaded


def _collect_strings(obj, found: list[str]) -> None:
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            _collect_strings(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _collect_strings(value, found)


def assert_no_secret(obj, secrets: tuple[str, ...] | None = None) -> None:
    blob = norm(json.dumps(obj, ensure_ascii=False))
    for secret in secrets if secrets is not None else secret_strings():
        key = norm(secret)
        if len(key) >= 24 and key in blob:
            raise RuntimeError("refusing to write asset text into the repository")
