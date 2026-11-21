from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aggregate_results import aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute cumulative metrics from frozen raw outputs.")
    parser.add_argument("result_root", type=Path)
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    fixture = args.result_root / "runtime_fixture"
    report = aggregate(
        args.result_root,
        args.source_root,
        fixture,
        args.result_root / "development_pilot_report.md",
        args.result_root / "RUN_READINESS.md",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
