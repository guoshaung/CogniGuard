#!/usr/bin/env python3
"""Recompute SHA-256 values and compare them with DATA_FREEZE.json."""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    freeze = json.loads((ROOT / "DATA_FREEZE.json").read_text())
    raw = ROOT / "data" / "oulad_raw"
    failed = False
    for item in freeze["files"]:
        path = raw / item["name"]
        digest = sha256(path)
        size = path.stat().st_size
        if digest != item["sha256"] or size != item["bytes"]:
            print(f"MISMATCH {item['name']} sha256={digest} bytes={size}")
            failed = True
        else:
            print(f"ok {item['name']}")
    for name, meta in freeze["documents"].items():
        path = ROOT / name
        digest = sha256(path)
        if digest != meta["sha256"]:
            print(f"MISMATCH {name} sha256={digest}")
            failed = True
        else:
            print(f"ok {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
