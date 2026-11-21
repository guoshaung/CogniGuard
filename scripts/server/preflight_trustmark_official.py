#!/usr/bin/env python3
"""Offline/fail-closed preflight for the optional official TrustMark baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from protection.supporting.image_watermark.experiments.trustmark_official_adapter import (  # noqa: E402
    TrustMarkAdapterError,
    TrustMarkOfficialAdapter,
    TrustMarkSettings,
    preflight_official_install,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="TrustMark baseline YAML.")
    parser.add_argument(
        "--load-model",
        action="store_true",
        help="Also instantiate the exact official encoder/decoder after asset verification.",
    )
    parser.add_argument("--output", help="Optional JSON report path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    config_path = Path(args.config).expanduser().resolve()
    output = Path(args.output).expanduser().resolve() if args.output else None
    if output is not None and output.exists():
        print(
            f"TrustMark official preflight refused to overwrite: {output}",
            file=sys.stderr,
        )
        return 2
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(config, dict):
            raise TrustMarkAdapterError("Configuration root must be a mapping.")
        settings = TrustMarkSettings.from_mapping(config.get("method"))
        report = preflight_official_install(settings)
        report["preflight_script"] = {
            "path": str(Path(__file__).resolve()),
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        if args.load_model:
            adapter = TrustMarkOfficialAdapter(settings)
            report["model_load"] = adapter.runtime_metadata["runtime"]
    except (OSError, yaml.YAMLError, TrustMarkAdapterError) as exc:
        print(f"TrustMark official preflight failed closed: {exc}", file=sys.stderr)
        return 2
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = (
            output.parent / f".{output.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
        )
        try:
            temporary.write_text(serialized, encoding="utf-8")
            if output.exists():
                raise FileExistsError(f"Output appeared during publish: {output}")
            temporary.replace(output)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            print(
                f"TrustMark official preflight publish failed: {exc}", file=sys.stderr
            )
            return 2
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
