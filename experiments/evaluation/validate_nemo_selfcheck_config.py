"""Validate official NeMo self-check configuration without calling an LLM."""
from __future__ import annotations

import json
from pathlib import Path

from nemoguardrails import RailsConfig

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "protection/supporting/cg_guardrails"


def main() -> None:
    config = RailsConfig.from_path(str(CONFIG))
    payload = {
        "status": "config_validated",
        "runtime": "nemoguardrails",
        "self_check_input_prompt": any(p.task == "self_check_input" for p in config.prompts),
        "self_check_output_prompt": any(p.task == "self_check_output" for p in config.prompts),
        "note": "No LLM call was made; configure a supported model backend before benchmark execution.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
