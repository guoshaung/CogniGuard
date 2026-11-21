"""Run the relevant pytest selection with all temporary files below var/."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.pycache_prefix = str(ROOT / "var/cache/python")


def main() -> int:
    import pytest

    args = sys.argv[1:]
    if args[:1] == ["test"]:
        args = args[1:]
    if not any(arg == "--basetemp" or arg.startswith("--basetemp=") for arg in args):
        temp_root = ROOT / "var/tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        args = ["--basetemp", str(temp_root / f"pytest-{uuid4().hex[:12]}"), *args]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
