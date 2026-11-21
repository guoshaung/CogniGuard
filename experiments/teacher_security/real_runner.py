"""真实模型入口：共享最多60次调用，包含消融、攻击协作和独立测试子集。"""
import argparse
import json
from pathlib import Path
from .runner import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="教学安全实验：真实模型受控试跑")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extension-of", type=Path,
                        help="固定补测该次已完成试跑的未覆盖正常题，合计仍限60次调用")
    args = parser.parse_args()
    if args.extension_of is not None:
        from .coverage import extend_normal_coverage
        result = extend_normal_coverage(args.extension_of, args.output)
    else:
        result = run(args.output, real=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
