"""离线验收入口：python -m experiments.teacher_security.offline_runner --output 新目录"""
import argparse
import json
from pathlib import Path
from .runner import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="教学安全实验：离线全矩阵验收")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False, indent=2))
