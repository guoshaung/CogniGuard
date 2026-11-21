#!/usr/bin/env python3
"""Prove that isolated watermark environments render identical attacks.

Run ``emit`` once in the CogniGuard, TrustMark, and WAM environments, then run
``compare`` over the three reports.  The reports contain hashes only; canonical
attack images are never retained.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image

from protection.supporting.image_watermark.experiments.attacks import (
    apply_traditional_attack,
    expand_attack_specs,
)


SCHEMA = "cogniguard.traditional-attack-runtime-audit.v1"
CONSENSUS_SCHEMA = "cogniguard.traditional-attack-runtime-consensus.v1"


class AttackRuntimeAuditError(RuntimeError):
    pass


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _canonical_image() -> Image.Image:
    y, x = np.indices((96, 128), dtype=np.uint16)
    array = np.stack(
        (
            (x * 7 + y * 3 + 17) % 256,
            (x * 5 + y * 11 + (x // 9) * 19) % 256,
            ((x ^ y) * 13 + (y // 7) * 23) % 256,
        ),
        axis=-1,
    ).astype(np.uint8)
    return Image.fromarray(array, mode="RGB")


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def emit_report(config_path: Path, *, seed: int, label: str) -> dict[str, Any]:
    config_path = config_path.expanduser().resolve()
    config = yaml.safe_load(
        os.path.expandvars(config_path.read_text(encoding="utf-8"))
    ) or {}
    rows = list(((config.get("attacks") or {}).get("traditional") or []))
    specs = expand_attack_specs(rows)
    if not specs or any(spec.requires_aigc for spec in specs):
        raise AttackRuntimeAuditError(
            "A non-empty, purely traditional attack grid is required."
        )
    required = dict(
        ((config.get("experiment") or {}).get("required_attack_runtime") or {})
    )
    observed = {name: _package_version(name) for name in sorted(required)}
    mismatches = {
        name: {"expected": expected, "observed": observed.get(name)}
        for name, expected in sorted(required.items())
        if observed.get(name) != expected
    }
    if mismatches:
        raise AttackRuntimeAuditError(
            f"Required attack runtime does not match: {mismatches}"
        )

    canonical = _canonical_image()
    attack_rows: list[dict[str, Any]] = []
    for spec in specs:
        attack_id = str(spec.params.get("expanded_name") or spec.name)
        attacked, metadata = apply_traditional_attack(canonical, spec, seed=seed)
        pixels = np.asarray(attacked.convert("RGB"), dtype=np.uint8)
        attack_rows.append(
            {
                "attack_id": attack_id,
                "attack_name": spec.name,
                "attack_family": spec.family,
                "params": {
                    key: value
                    for key, value in spec.params.items()
                    if key != "expanded_name"
                },
                "truth_bbox": metadata.get("truth_bbox"),
                "width": attacked.width,
                "height": attacked.height,
                "pixel_sha256": _sha256_bytes(pixels.tobytes(order="C")),
                "png_sha256": _sha256_bytes(_png_bytes(attacked)),
            }
        )
    attack_path = Path(__file__).resolve().parents[2] / 'protection' / 'image_watermark' / "experiments" / "attacks.py"
    return {
        "schema_version": SCHEMA,
        "label": label,
        "python": sys.version,
        "platform": platform.platform(),
        "seed": seed,
        "config_path": str(config_path),
        "config_sha256": _sha256_file(config_path),
        "attack_implementation_path": str(attack_path),
        "attack_implementation_sha256": _sha256_file(attack_path),
        "required_packages": required,
        "observed_packages": {
            "numpy": _package_version("numpy"),
            "Pillow": _package_version("Pillow"),
        },
        "canonical_image": {
            "width": canonical.width,
            "height": canonical.height,
            "pixel_sha256": _sha256_bytes(
                np.asarray(canonical, dtype=np.uint8).tobytes(order="C")
            ),
        },
        "attack_count": len(attack_rows),
        "attacks": attack_rows,
    }


def compare_reports(paths: list[Path]) -> dict[str, Any]:
    if len(paths) < 2:
        raise AttackRuntimeAuditError("compare requires at least two reports.")
    reports: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA:
            raise AttackRuntimeAuditError(f"Invalid audit report: {path}")
        reports.append(payload)
    reference = reports[0]
    compared_fields = (
        "seed",
        "config_sha256",
        "attack_implementation_sha256",
        "required_packages",
        "observed_packages",
        "canonical_image",
        "attack_count",
        "attacks",
    )
    mismatches: list[dict[str, Any]] = []
    for report in reports[1:]:
        fields = [field for field in compared_fields if report.get(field) != reference.get(field)]
        if fields:
            mismatches.append(
                {
                    "reference": reference.get("label"),
                    "candidate": report.get("label"),
                    "fields": fields,
                }
            )
    if mismatches:
        raise AttackRuntimeAuditError(
            "Traditional attack runtimes are not byte-identical: "
            + json.dumps(mismatches, ensure_ascii=False, sort_keys=True)
        )
    return {
        "schema_version": CONSENSUS_SCHEMA,
        "status": "identical",
        "labels": [report.get("label") for report in reports],
        "report_sha256": [
            _sha256_file(path.expanduser().resolve()) for path in paths
        ],
        "seed": reference["seed"],
        "config_sha256": reference["config_sha256"],
        "attack_implementation_sha256": reference[
            "attack_implementation_sha256"
        ],
        "observed_packages": reference["observed_packages"],
        "attack_count": reference["attack_count"],
    }


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit = subparsers.add_parser("emit")
    emit.add_argument("--config", type=Path, required=True)
    emit.add_argument("--output", type=Path, required=True)
    emit.add_argument("--seed", type=int, default=20260802)
    emit.add_argument("--label", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--reports", type=Path, nargs="+", required=True)
    compare.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "emit":
        payload = emit_report(args.config, seed=args.seed, label=args.label)
    else:
        payload = compare_reports(args.reports)
    _write_new_json(args.output, payload)
    print(
        json.dumps(
            {
                "status": payload.get("status", "created"),
                "schema_version": payload["schema_version"],
                "output": str(args.output.expanduser().resolve()),
                "label": payload.get("label"),
                "attack_count": payload.get("attack_count"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
