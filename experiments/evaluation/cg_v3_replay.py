"""JSONL replay helpers for deterministic CG V3 episodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .cg_v3_harness import CGV3Harness
from .cg_v3_manifest import build_manifest
from .cg_v3_schemas import CGInput


def replay_jsonl(
    input_path: str | Path,
    output_path: str | Path,
    *,
    mode: str = "full_cg_v3",
    privacy_max: float = 1.0,
    copyright_max: float = 1.0,
    seed: int = 0,
) -> dict[str, Any]:
    source = Path(input_path)
    output = Path(output_path)
    harness = CGV3Harness(mode=mode, privacy_max=privacy_max, copyright_max=copyright_max)
    count = 0
    with source.open("r", encoding="utf-8") as reader, output.open("w", encoding="utf-8") as writer:
        for line in reader:
            if not line.strip():
                continue
            request = CGInput.from_mapping(json.loads(line))
            result = harness.run(request).to_dict()
            result["input_hash"] = _input_hash(request)
            result["controller_mode"] = mode
            writer.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    manifest = build_manifest(
        project_root=Path(__file__).resolve().parents[2],
        mode=mode,
        config={"privacy_max": privacy_max, "copyright_max": copyright_max},
        input_paths=[source],
        seed=seed,
    )
    manifest["episode_count"] = count
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"episodes": count, "output": str(output), "manifest": str(manifest_path)}


def _input_hash(request: CGInput) -> str:
    encoded = json.dumps(request.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    import hashlib

    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay CG V3 JSONL episodes")
    parser.add_argument("input_path")
    parser.add_argument("output_path")
    parser.add_argument("--mode", choices=sorted(CGV3Harness.MODES), default="full_cg_v3")
    parser.add_argument("--privacy-max", type=float, default=1.0)
    parser.add_argument("--copyright-max", type=float, default=1.0)
    args = parser.parse_args()
    print(json.dumps(replay_jsonl(
        args.input_path,
        args.output_path,
        mode=args.mode,
        privacy_max=args.privacy_max,
        copyright_max=args.copyright_max,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
