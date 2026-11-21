import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="CGC v3: protocol repair only; no full-scale expansion")
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--bundle", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from .runner import freeze as prepare, run as execute
    try:
        result = prepare(args.output) if args.command == "freeze" else execute(args.bundle, args.output)
    except Exception as exc:
        if args.output.is_dir() and not (args.output/"status.json").exists():
            from experiments.cgc_propagation_v2.dataset import write_json, now
            write_json(args.output/"status.json", {"status": "FAILED_INTERNAL_VALIDATION_NO_EXPANSION",
                       "error_class": type(exc).__name__, "created_at": now(), "no_expansion": True})
        raise
    print(json.dumps(result, ensure_ascii=True), flush=True)
    if args.command == "run" and not result["pilot_gate_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
