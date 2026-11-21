"""离线演示、独立评估与隔离的真实模型攻击实验入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.paths import PROJECT_ROOT as ROOT

WORKFLOW_COMMANDS = (
    "experiments",
    "matrix",
    "teachers",
    "graph",
    "benchmarks",
    "langsmith",
    "tools",
)


def main():
    from cogniguard.runtime.mode import _load_env_file

    _load_env_file()
    if len(sys.argv) > 1 and sys.argv[1] in WORKFLOW_COMMANDS:
        from cogniguard.workflows.__main__ import main as workflow_main

        return workflow_main()
    parser = argparse.ArgumentParser(
        prog="cogniguard",
        description="CogniGuard：安全保护、LangGraph 编排、研究评估与安全观测",
        epilog="查看工作流或监控参数：python -m cogniguard graph --help / langsmith --help",
    )
    parser.add_argument(
        "command",
        choices=[
            "demo",
            "evaluate",
            "redteam",
            "injecagent",
            "teaching",
            "multiagent",
            "cgce2e",
            "privacyattack",
            "factuality",
            "supplychain",
            "promptleak",
            "toolgov",
            "memorypoison",
            *WORKFLOW_COMMANDS,
        ],
        nargs="?",
        default="demo",
    )
    parser.add_argument("--config", type=Path, default=ROOT / "configs/focused.yaml")
    parser.add_argument(
        "--profiles", type=Path, default=ROOT / "protection/student_profile/data/profiles.jsonl"
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT / "protection/student_profile/data/student_questions.jsonl",
    )
    parser.add_argument(
        "--resources",
        type=Path,
        default=ROOT / "protection/teacher_resource/data/teacher_resources.jsonl",
    )
    parser.add_argument("--case-index", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="显示包含来源证据的完整 JSON")
    parser.add_argument("--output", type=Path, help="评估输出目录，必须不存在")
    parser.add_argument("--model", help="真实模型实验的模型名；默认读取现有 MIMO_MODEL")
    parser.add_argument(
        "--limit", type=int, default=12, help="redteam 场景数，1 到 12；teaching 为 1 到 10"
    )
    parser.add_argument("--workers", type=int, default=2, help="真实模型实验并发调用数，1 到 4")
    parser.add_argument("--dry-run", action="store_true", help="只保存攻击实验计划，不调用模型")
    parser.add_argument(
        "--allow-model-calls", action="store_true", help="显式允许真实模型调用及可能产生的费用"
    )
    parser.add_argument(
        "--no-proxy", action="store_true", help="本次模型调用直连服务，不使用系统代理"
    )
    parser.add_argument(
        "--per-kind", type=int, default=6, help="injecagent 每类官方攻击抽样数，1 到 17"
    )
    parser.add_argument("--seed", type=int, default=20261011, help="injecagent 固定分层抽样种子")
    args = parser.parse_args()
    real_model_commands = {
        "redteam",
        "injecagent",
        "teaching",
        "multiagent",
        "factuality",
        "promptleak",
        "toolgov",
        "memorypoison",
    }
    if args.command in real_model_commands and not args.dry_run and not args.allow_model_calls:
        parser.error("真实模型实验须显式添加 --allow-model-calls；先用 --dry-run 验收计划")
    if args.command == "teaching":
        from experiments.focused.teaching_injection.runner import run

        # teaching 的样例数固定，limit 默认 None 表示全部；仅当用户显式传入时才裁剪。
        limit = args.limit if args.limit != 12 else None
        print(run(args.output, args.model, limit, args.workers, args.dry_run, args.no_proxy))
        return
    if args.command == "memorypoison":
        from experiments.focused.memorypoison.runner import run

        out, _ = run(args.output, args.model, args.workers, args.dry_run, args.no_proxy)
        print(out)
        return
    if args.command == "toolgov":
        from experiments.focused.toolgov.runner import run

        out, _ = run(args.output, args.model, args.workers, args.dry_run, args.no_proxy)
        print(out)
        return
    if args.command == "promptleak":
        from experiments.focused.promptleak.runner import run

        out, _ = run(args.output, args.model, args.workers, args.dry_run, args.no_proxy)
        print(out)
        return
    if args.command == "supplychain":
        from experiments.focused.supplychain.runner import run

        out, _ = run(args.output)
        print(out)
        return
    if args.command == "factuality":
        from experiments.focused.factuality.runner import run

        out = run(args.output, args.model, args.workers, args.dry_run, args.no_proxy)
        print(out if args.dry_run else out[0])
        return
    if args.command == "privacyattack":
        from experiments.focused.privacy_attack.runner import run

        out, _ = run(args.output)
        print(out)
        return
    if args.command == "cgce2e":
        from experiments.focused.cgc_e2e.runner import run

        out, _ = run(args.output)
        print(out)
        return
    if args.command == "multiagent":
        from experiments.focused.multiagent.runner import run

        limit = args.limit if args.limit != 12 else None
        print(run(args.output, args.model, limit, args.workers, args.dry_run, args.no_proxy))
        return
    if args.command == "injecagent":
        from experiments.focused.injecagent.runner import run

        print(
            run(
                args.per_kind,
                args.seed,
                args.workers,
                args.no_proxy,
                args.model,
                args.output,
                args.dry_run,
            )
        )
        return
    if args.command == "redteam":
        from experiments.focused.redteam.runner import run

        print(run(args.output, args.model, args.limit, args.workers, args.dry_run, args.no_proxy))
        return
    if args.command == "evaluate":
        from experiments.focused.evaluate import evaluate

        print(evaluate(args.config, args.profiles, args.questions, args.resources, args.output))
        return
    from cogniguard.integrations.education import AccessScope, ProtectionPipeline
    from cogniguard.observability import LangSmithMonitor
    from core.inputs import load_inputs

    config, profiles, questions, resources = load_inputs(
        args.config, args.profiles, args.questions, args.resources
    )
    if not 0 <= args.case_index < len(questions):
        parser.error(f"--case-index 应在 0 到 {len(questions) - 1} 之间")
    question = questions[args.case_index]
    # 离线数据集的可信调用方；在线服务必须从已鉴权会话构建范围。
    result = ProtectionPipeline(config, resources, monitor=LangSmithMonitor.from_environment()).run(
        profiles[question["student_id"]], question, access=AccessScope(question["student_id"])
    )
    print("离线规则演示；不是大模型实测结果。\n")
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"问题：{result.task.question}\n\n最小画像：\n{result.context_card}")
        print(f"\n资源返回方式：{result.controlled.mode if result.controlled else '无需资源'}")
        print(f"\n教学草稿：\n{result.answer}")
        if result.controlled:
            print(f"\n资源来源：{result.controlled.resource.resource_id}")
        print("\n完整决策证据：添加 --json 查看")


if __name__ == "__main__":
    raise SystemExit(main())
