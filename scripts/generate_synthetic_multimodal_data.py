from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.data_generation import SyntheticStudentDataGenerator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic multimodal student data for CogniGuard."
    )
    parser.add_argument(
        "--output-root",
        default="data",
        help="Root folder for raw/ and processed/ outputs. Default: data",
    )
    parser.add_argument(
        "--student-count",
        type=int,
        default=30,
        help="Number of synthetic students to generate. Default: 30",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260526,
        help="Deterministic random seed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    generator = SyntheticStudentDataGenerator(
        output_root=Path(args.output_root),
        student_count=args.student_count,
        seed=args.seed,
    )
    manifest = generator.generate()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
