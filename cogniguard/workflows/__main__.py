from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    from cogniguard.observability import LangSmithMonitor, configuration_status
    from cogniguard.runtime.mode import _load_env_file

    _load_env_file()

    from .experiments import ROOT, Job, pipeline_worker, run_matrix

    parser = argparse.ArgumentParser(description="CogniGuard LangGraph experiment runtime")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--case-index", type=int, default=0)
    demo.add_argument("--langsmith", action="store_true")
    demo.add_argument(
        "--governance",
        action="store_true",
        help="Enable existing LifecycleGuard; non-allow fails closed",
    )
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--plan", type=Path, default=ROOT / "configs/langgraph-experiments.yaml")
    matrix.add_argument("--output", type=Path, required=True)
    matrix.add_argument(
        "--execute", action="store_true", help="Without this, only validate/materialize plans"
    )
    matrix.add_argument(
        "--allow-model-calls", action="store_true", help="Also allow paid/cloud model adapters"
    )
    matrix.add_argument("--langsmith", action="store_true")
    draw = sub.add_parser("graph")
    draw.add_argument("--kind", choices=("pipeline", "experiments", "teachers"), default="pipeline")
    draw.add_argument("--team", default="committee")
    teachers = sub.add_parser("teachers")
    teachers.add_argument("--list", action="store_true")
    teachers.add_argument("--team", default="committee")
    teachers.add_argument("--trust-mode", choices=("enforce", "observe_only"), default="enforce")
    teachers.add_argument("--output", type=Path)
    teachers.add_argument("--workers", type=int, default=4)
    teachers.add_argument("--seed", type=int, default=20261013)
    teachers.add_argument("--langsmith", action="store_true")
    benchmark = sub.add_parser("benchmarks")
    langsmith_cli = sub.add_parser(
        "langsmith", help="Inspect or safely smoke-test metrics-only monitoring"
    )
    langsmith_sub = langsmith_cli.add_subparsers(dest="langsmith_command", required=True)
    langsmith_sub.add_parser(
        "status", help="Read configuration presence without exposing credentials"
    )
    langsmith_smoke = langsmith_sub.add_parser("smoke", help="Send one synthetic metrics-only span")
    langsmith_smoke.add_argument(
        "--submit", action="store_true", help="Without this flag, only show a no-network plan"
    )
    bench_sub = benchmark.add_subparsers(dest="benchmark_command", required=True)
    bench_sub.add_parser("sources")
    prepare = bench_sub.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--allow-download", action="store_true")
    prepare.add_argument("--no-proxy", action="store_true")
    plan = bench_sub.add_parser("plan")
    plan.add_argument("--corpus", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--team", default="serial_coaching")
    plan.add_argument("--sources", nargs="+", default=["hf_wild", "injecagent_dh", "injecagent_ds"])
    plan.add_argument(
        "--entries",
        nargs="+",
        choices=("producer_context", "relay_tamper", "direct_user"),
        default=["producer_context", "relay_tamper"],
    )
    plan.add_argument("--per-source", type=int, default=1)
    plan.add_argument("--seed", type=int, default=20261013)
    plan.add_argument("--partition", choices=("heldout", "development"), default="heldout")
    plan.add_argument("--max-calls", type=int, default=120)
    plan.add_argument("--max-payload-chars", type=int, default=1600)
    run_bench = bench_sub.add_parser("run")
    run_bench.add_argument("--plan", type=Path, required=True)
    run_bench.add_argument("--output", type=Path, required=True)
    run_mode = run_bench.add_mutually_exclusive_group()
    run_mode.add_argument("--offline-smoke", action="store_true")
    run_mode.add_argument("--execute", action="store_true")
    run_bench.add_argument("--allow-model-calls", action="store_true")
    run_bench.add_argument("--max-calls", type=int)
    run_bench.add_argument("--model")
    run_bench.add_argument("--no-proxy", action="store_true")
    tool_cli = sub.add_parser("tools", help="Graph-schedule first-party one-off research tools")
    tool_sub = tool_cli.add_subparsers(dest="tool_command", required=True)
    tool_sub.add_parser("list", help="Discover first-party CLI tools without importing them")
    tool_run = tool_sub.add_parser("run", help="Plan by default; --execute runs the selected tool")
    tool_run.add_argument("--name", required=True, help="Dotted first-party module name")
    tool_run.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Fresh directory under experiments/results/langgraph_tool_jobs",
    )
    tool_run.add_argument("--execute", action="store_true")
    tool_run.add_argument("--allow-model-calls", action="store_true")
    tool_run.add_argument("--allow-network", action="store_true")
    tool_run.add_argument("--allow-unreviewed", action="store_true")
    tool_run.add_argument(
        "--allow-default-output",
        action="store_true",
        help="Explicitly accept the script's historical default output path",
    )
    tool_run.add_argument("--timeout-seconds", type=int, default=300)
    tool_run.add_argument("--seed", type=int, default=20261013)
    tool_run.add_argument("--langsmith", action="store_true")
    tool_run.add_argument("script_args", nargs=argparse.REMAINDER)
    experiment_cli = sub.add_parser(
        "experiments", help="All first-party experiments in one grouped inventory"
    )
    experiment_sub = experiment_cli.add_subparsers(dest="experiment_command", required=True)
    experiment_list = experiment_sub.add_parser("list", help="Browse all entries by domain")
    experiment_list.add_argument(
        "--all", action="store_true", help="Include compatible and unavailable entries"
    )
    experiment_list.add_argument(
        "--family",
        choices=(
            "privacy",
            "copyright",
            "text-watermark",
            "image-watermark",
            "safety-control",
            "datasets",
            "cross-module",
            "operations",
        ),
    )
    experiment_list.add_argument("--json", action="store_true", help="Machine-readable inventory")
    experiment_show = experiment_sub.add_parser(
        "show", help="Inspect one entry before planning/running"
    )
    experiment_show.add_argument("--name", required=True)
    for verb in ("plan", "run"):
        selected = experiment_sub.add_parser(verb, help="Run the chosen LangGraph experiment lane")
        selected.add_argument("--name", required=True)
        selected.add_argument("--output", type=Path, required=True)
        selected.add_argument("--plan", type=Path, help="Only for comparison-matrix")
        selected.add_argument("--allow-model-calls", action="store_true")
        selected.add_argument("--allow-network", action="store_true")
        selected.add_argument("--allow-unreviewed", action="store_true")
        selected.add_argument("--allow-default-output", action="store_true")
        selected.add_argument("--timeout-seconds", type=int, default=300)
        selected.add_argument("--seed", type=int, default=20261013)
        selected.add_argument("--langsmith", action="store_true")
        selected.add_argument(
            "script_args",
            nargs=argparse.REMAINDER,
            help="Compatible entries only: pass historical script arguments after --",
        )
    sub.add_parser("_benchmark_worker")
    worker = sub.add_parser("_worker")
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--langsmith", action="store_true")
    args = parser.parse_args()
    if args.command == "experiments":
        from .experiment_catalog import (
            describe_experiment,
            format_inventory,
            inventory_summary,
            list_experiments,
            run_experiment,
        )

        if args.experiment_command == "list":
            rows = list_experiments(family=args.family)
            if args.json:
                selected = rows if args.all else [row for row in rows if row["tier"] == "managed"]
                print(
                    json.dumps(
                        {
                            **inventory_summary(rows),
                            "displayed_count": len(selected),
                            "experiments": selected,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(format_inventory(rows, show_all=args.all))
            return 0
        if args.experiment_command == "show":
            try:
                entry = describe_experiment(args.name)
            except ValueError as exc:
                parser.error(str(exc))
            print(json.dumps({"schema_version": 1, "entry": entry}, ensure_ascii=False, indent=2))
            return 0
        forwarded = args.script_args[1:] if args.script_args[:1] == ["--"] else args.script_args
        try:
            result = run_experiment(
                args.name,
                args.output,
                execute=args.experiment_command == "run",
                plan=args.plan,
                allow_model_calls=args.allow_model_calls,
                allow_network=args.allow_network,
                allow_unreviewed=args.allow_unreviewed,
                allow_default_output=args.allow_default_output,
                timeout_seconds=args.timeout_seconds,
                seed=args.seed,
                script_args=tuple(forwarded),
                langsmith=args.langsmith,
            )
        except (ValueError, PermissionError, FileExistsError, RuntimeError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"PLANNED", "COMPLETED"} else 1
    if args.command == "langsmith":
        configuration = configuration_status()
        status = {
            **configuration,
            "privacy_mode": configuration["content_policy"],
            "native_graph_tracing": "disabled",
        }
        if args.langsmith_command == "status":
            print(json.dumps(status, ensure_ascii=False, indent=2))
            return 0
        if not args.submit:
            print(
                json.dumps({**status, "status": "PLANNED_NO_NETWORK"}, ensure_ascii=False, indent=2)
            )
            return 0
        if not configuration["credential_present"]:
            print(
                json.dumps({**status, "status": "CREDENTIAL_MISSING"}, ensure_ascii=False, indent=2)
            )
            return 1
        from cogniguard.observability.telemetry import SafeTelemetry

        try:
            monitor = LangSmithMonitor(enabled=True)
        except Exception:
            print(json.dumps({**status, "status": "client_init_failed"}, indent=2))
            return 1
        recorder = SafeTelemetry()
        with recorder.span("monitor_smoke") as metrics:
            metrics["validated"] = 1
        monitor.export(recorder)
        print(
            json.dumps(
                {**status, **monitor.summary(), "run_id": recorder.run_id},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if monitor.last_status == "submitted" else 1
    if args.command == "tools":
        from .tool_jobs import ToolRequest, list_tools, run_tool_job

        if args.tool_command == "list":
            items = list_tools()
            unavailable = sum(item["risk"] == "unavailable_archive" for item in items)
            print(
                json.dumps(
                    {
                        "count": len(items),
                        "runnable_count": len(items) - unavailable,
                        "unavailable_archive_count": unavailable,
                        "tools": items,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        forwarded = args.script_args[1:] if args.script_args[:1] == ["--"] else args.script_args
        request = ToolRequest(
            module=args.name,
            args=tuple(forwarded),
            output=args.output,
            execute=args.execute,
            allow_model_calls=args.allow_model_calls,
            allow_network=args.allow_network,
            allow_unreviewed=args.allow_unreviewed,
            allow_default_output=args.allow_default_output,
            timeout_seconds=args.timeout_seconds,
            seed=args.seed,
        )
        try:
            result = run_tool_job(request, monitor=LangSmithMonitor(enabled=args.langsmith))
        except (ValueError, PermissionError, FileExistsError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"PLANNED", "COMPLETED"} else 1
    if args.command == "_benchmark_worker":
        from .benchmarks.cli import worker_dispatch

        return worker_dispatch()
    if args.command == "benchmarks":
        from .benchmarks.cli import dispatch

        return dispatch(args)
    if args.command == "_worker":
        job = Job(**json.loads(sys.stdin.read()))
        if job.adapter == "teacher_dag":
            from .teachers.runner import teacher_worker

            teacher_worker(job, args.output, monitor=LangSmithMonitor(enabled=args.langsmith))
        else:
            pipeline_worker(job, args.output)
        return 0
    if args.command == "graph":
        from .experiments import build_experiment_graph
        from .pipeline import build_graph

        if args.kind == "teachers":
            from .teachers.catalog import PromptLibrary, TeamCatalog
            from .teachers.dag import build_teacher_graph

            library = PromptLibrary(ROOT / "configs/teacher-prompts.yaml")
            graph = build_teacher_graph(
                TeamCatalog(ROOT / "configs/teacher-teams.yaml", library).get(args.team)
            )
        else:
            graph = build_graph() if args.kind == "pipeline" else build_experiment_graph()
        print(graph.get_graph().draw_mermaid())
        return 0
    if args.command == "teachers":
        from .experiments import isolated_env
        from .teachers.catalog import PromptLibrary, TeamCatalog

        library = PromptLibrary(ROOT / "configs/teacher-prompts.yaml")
        catalog = TeamCatalog(ROOT / "configs/teacher-teams.yaml", library)
        if args.list:
            print(
                json.dumps(
                    {
                        "prompts": library.inventory(),
                        "teams": [
                            {
                                "name": t.name,
                                "teachers": len(t.nodes),
                                "edges": len(t.edges),
                                "output": t.output,
                            }
                            for t in catalog.teams.values()
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.output is None:
            parser.error("teachers requires --output (or --list)")
        catalog.get(args.team)
        job = Job(
            0,
            "teacher_dag",
            "teacher_dag",
            args.seed,
            False,
            str(ROOT / "configs/focused.yaml"),
            str(ROOT / "protection/student_profile/data/profiles.jsonl"),
            str(ROOT / "protection/student_profile/data/student_questions.jsonl"),
            str(ROOT / "protection/teacher_resource/data/teacher_resources.jsonl"),
            workers=args.workers,
            team=args.team,
            trust_mode=args.trust_mode,
            teacher_prompts=str(ROOT / "configs/teacher-prompts.yaml"),
            teacher_teams=str(ROOT / "configs/teacher-teams.yaml"),
            expected_prompt_sha256=library.sha256,
            expected_team_catalog_sha256=catalog.sha256,
        )
        job.validate()
        command = [
            sys.executable,
            "-m",
            "cogniguard.workflows",
            "_worker",
            "--output",
            str(args.output),
        ]
        if args.langsmith:
            command.append("--langsmith")
        proc = subprocess.run(
            command,
            input=json.dumps(job.to_dict()),
            text=True,
            cwd=ROOT,
            env=isolated_env(args.seed),
        )
        if proc.returncode:
            return proc.returncode
        print(args.output)
        return 0
    monitor = LangSmithMonitor(enabled=args.langsmith)
    if args.command == "matrix":
        summary = run_matrix(
            args.plan,
            args.output,
            execute=args.execute,
            allow_model_calls=args.allow_model_calls,
            monitor=monitor,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 1 if summary["failed_jobs"] else 0
    from core.access import AccessScope
    from core.inputs import load_inputs

    from .pipeline import LangGraphProtectionPipeline

    config, profiles, questions, resources = load_inputs(
        ROOT / "configs/focused.yaml",
        ROOT / "protection/student_profile/data/profiles.jsonl",
        ROOT / "protection/student_profile/data/student_questions.jsonl",
        ROOT / "protection/teacher_resource/data/teacher_resources.jsonl",
    )
    if not 0 <= args.case_index < len(questions):
        parser.error("case-index out of range")
    q = questions[args.case_index]
    guard = None
    if args.governance:
        from cogniguard.governance.capability import CapabilityGrant, CapabilityPolicy
        from cogniguard.governance.lifecycle import LifecycleGuard

        guard = LifecycleGuard(
            CapabilityPolicy(
                [
                    CapabilityGrant("service", target, frozenset({"education"}))
                    for target in ("teaching", "delivery")
                ]
            )
        )
    pipeline = LangGraphProtectionPipeline(config, resources, monitor=monitor, guard=guard)
    result = pipeline.run(profiles[q["student_id"]], q, access=AccessScope(q["student_id"]))
    print(
        json.dumps(
            {
                "orchestration": "langgraph",
                "execution_mode": "offline_rule_based",
                "result": result.to_dict(),
                "trace": pipeline.last_trace,
                "langsmith": monitor.last_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
