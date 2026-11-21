"""python -B -m experiments.cgc_propagation_v2 --help"""
import argparse
import json
from pathlib import Path

from .dataset import ROOT


def main():
    parser = argparse.ArgumentParser(description="Isolated, audit-first CGC propagation experiment")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--cache", type=Path, default=ROOT / ".cache/qasc-real-v1")
    freeze.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--bundle", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--phase", choices=("pilot", "heldout"), default="pilot")
    run.add_argument("--max-calls", type=int, default=256)
    run.add_argument("--offline", action="store_true")
    run.add_argument("--pilot-result", type=Path)
    score = commands.add_parser("score")
    score.add_argument("--bundle", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    all_run = commands.add_parser("validated-real")
    all_run.add_argument("--bundle", type=Path, required=True)
    all_run.add_argument("--offline-result", type=Path, required=True)
    all_run.add_argument("--output", type=Path, required=True)
    all_run.add_argument("--total-max-calls", type=int, default=1400)
    args = parser.parse_args()
    if args.command == "freeze":
        from .dataset import freeze
        result = freeze(args.cache, args.output)
    elif args.command == "run":
        from .live import run
        run(args.bundle, args.output, args.phase, args.max_calls, args.offline, args.pilot_result)
        result = {"status": "FINISHED_EXECUTION_SCORE_NEXT"}
    elif args.command == "score":
        from .score import score
        result = score(args.bundle, args.output)
    else:
        from .dataset import now, sha, write_json
        from .live import run, check_frozen
        from .score import score
        cfg = check_frozen(args.bundle)
        offline = json.loads((args.offline_result / "summary.json").read_text(encoding="utf-8"))
        if (offline.get("execution") != "offline_fixture_not_model_performance" or not offline.get("flow_gate_passed")
                or offline.get("bundle_sha256") != sha((args.bundle / "frozen_config.json").read_bytes())):
            raise ValueError("Passing offline validation required for same frozen bundle")
        if args.total_max_calls < cfg["total_max_calls"] or args.total_max_calls > 1400:
            raise ValueError("Complete phase plan must fit authorized 1400-call ceiling")
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / "authorization.json", {"created_at_utc": now(), "authorized_total_max_calls": 1400,
                   "planned_calls": cfg["total_max_calls"], "no_retries": True})
        result = None
        for phase, limit in (("pilot", cfg["pilot_max_calls"]), ("heldout", cfg["total_max_calls"]-cfg["pilot_max_calls"])):
            out = args.output / phase
            try:
                run(args.bundle, out, phase, limit, pilot_result=args.output / "pilot" if phase == "heldout" else None)
            except Exception:
                # Preserve independently scored partial evidence on transport or runtime errors.
                if (out / "execution-status.json").exists():
                    result = score(args.bundle, out)
                write_json(args.output / "status.json", {"status": "STOPPED_ANOMALY_NO_EXPANSION", "phase": phase,
                           "partial_score": result})
                raise
            result = score(args.bundle, out)
            print(json.dumps({"phase": phase, **result}), flush=True)
            if not result["flow_gate_passed"]:
                write_json(args.output / "status.json", {"status": "STOPPED_ANOMALY_NO_EXPANSION", "phase": phase})
                raise RuntimeError("Independent score gate failed; heldout expansion forbidden")
        write_json(args.output / "status.json", {"status": "COMPLETED_REAL_PILOT_AND_HELDOUT", "planned_calls": cfg["total_max_calls"]})
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
