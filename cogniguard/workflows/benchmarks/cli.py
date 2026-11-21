import json
import subprocess
import sys

from ..experiments import ROOT, isolated_env
from .corpus import SOURCES, prepare_corpus
from .plan import build_plan, load_plan
from .runner import run_benchmark


def dispatch(args):
    command = args.benchmark_command
    if command == "sources":
        result = {
            "registered": SOURCES,
            "not_auto_enabled": {
                "allenai/wildjailbreak": "gated; user must personally accept access conditions"
            },
        }
    elif command == "prepare":
        lock = prepare_corpus(
            args.output, allow_download=args.allow_download, no_proxy=args.no_proxy
        )
        result = {
            "output": str(args.output),
            "rows": lock["row_count"],
            "provenance": lock["provenance"],
            "scripts_executed": False,
            "model_calls": 0,
        }
    elif command == "plan":
        plan = build_plan(
            args.corpus,
            args.output,
            team_name=args.team,
            sources=args.sources,
            entries=args.entries,
            per_source=args.per_source,
            seed=args.seed,
            partition=args.partition,
            max_calls=args.max_calls,
            max_payload_chars=args.max_payload_chars,
        )
        result = {
            "output": str(args.output),
            "selected_cases": plan["selected_cases"],
            "trials": len(plan["trials"]),
            "model_calls_upper_bound": plan["model_calls_upper_bound"],
            "max_model_calls": plan["max_model_calls"],
        }
    else:
        mode = (
            "offline_smoke" if args.offline_smoke else "real_model" if args.execute else "plan_only"
        )
        frozen, _, _, _ = load_plan(args.plan)
        request = {
            "plan_dir": str(args.plan.resolve()),
            "output": str(args.output.resolve()),
            "mode": mode,
            "allow_model_calls": args.allow_model_calls,
            "model_name": args.model,
            "no_proxy": args.no_proxy,
            "max_calls": args.max_calls,
        }
        # Python's hash seed must be set before the interpreter starts.
        proc = subprocess.run(
            [sys.executable, "-m", "cogniguard.workflows", "_benchmark_worker"],
            input=json.dumps(request),
            cwd=ROOT,
            env=isolated_env(frozen["seed"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode:
            print(
                json.dumps(
                    {
                        "status": "WORKER_FAILED",
                        "exit_code": proc.returncode,
                        "note": "No raw child stderr is published; inspect the local output artifacts.",
                    }
                )
            )
            return proc.returncode
        result = json.loads(proc.stdout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return (
        1
        if (
            result.get("status") == "PREFLIGHT_FAILED"
            or result.get("execution_errors", 0)
            or result.get("budget_exhausted_trials", 0)
        )
        else 0
    )


def worker_dispatch():
    request = json.loads(sys.stdin.read())
    allowed = {
        "plan_dir",
        "output",
        "mode",
        "allow_model_calls",
        "model_name",
        "no_proxy",
        "max_calls",
    }
    if not isinstance(request, dict) or set(request) != allowed:
        raise ValueError("Invalid benchmark worker request")
    result = run_benchmark(**request)
    print(json.dumps(result, ensure_ascii=False))
    return 0
