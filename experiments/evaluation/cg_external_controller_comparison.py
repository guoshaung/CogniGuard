from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from cogniguard.protection.cg.nemo_guardrails_adapter import NeMoGuardrailsAdapter
from experiments.evaluation.cg_v3_metrics import compute_mode_metrics
from experiments.evaluation.cg_v3_pilot import _run_mode, load_episodes
from experiments.common.sequential_suite_graph import run_sequential_suite


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "experiments" / "datasets" / "cg_v3_integrated" / "episodes.jsonl"
OUTPUT = ROOT / "experiments" / "results" / "cg_external_controller_dev"


CONTROLLERS = {
    "nemo_base": "no_cg",
    "nemo_independent": "independent_policy",
    "nemo_static": "static_cg",
    "nemo_budget": "budget_only",
    "nemo_agentspec_style": "static_cg",
    "nemo_guardagent_style": "independent_policy",
    "nemo_full_cg": "full_cg_v3",
}


def _apply_shared_nemo(results: list[dict[str, Any]], episodes: list[dict[str, Any]], adapter: NeMoGuardrailsAdapter) -> None:
    specs = {str(ep["episode_id"]): {str(r["round_id"]): r for r in ep["round_sequence"]} for ep in episodes}
    for episode in results:
        for row in episode["rounds"]:
            spec = specs[str(episode["episode_id"])][str(row["round_id"])]
            decision = adapter.check_user_input(str(spec.get("q_t", "")), {"scenario": episode["scenario_type"]})
            row["nemo_decision"] = decision["decision"]
            row["nemo_policy"] = decision["matched_policy"]
            if decision["decision"] == "block":
                row.update({"actions": ["nemo_block"], "actual_student_fields": [], "actual_allowed_chunks": [], "execution_result": "block", "normal_task_completion": False, "privacy_cost": 0.0, "copyright_cost": 0.0})


def _apply_agentspec(results: list[dict[str, Any]]) -> None:
    """AgentSpec-style DSL adapter: deterministic trigger/predicate/action rules."""
    for episode in results:
        for row in episode["rounds"]:
            risk = max((float(v) for v in row.get("risk_before", {}).values()), default=0.0)
            if risk >= 0.75 or not row.get("audit_valid", True):
                row.update({"actions": ["dsl_block"], "actual_student_fields": [], "actual_allowed_chunks": [], "execution_result": "block", "normal_task_completion": False, "privacy_cost": 0.0, "copyright_cost": 0.0})
            elif risk >= 0.45:
                row["actions"] = ["dsl_sanitize"]
                row["actual_student_fields"] = row.get("actual_student_fields", [])[:1]
                row["actual_allowed_chunks"] = row.get("actual_allowed_chunks", [])[:1]


def _apply_guardagent(results: list[dict[str, Any]]) -> None:
    """GuardAgent-style deterministic judge adapter; not the official LLM method."""
    for episode in results:
        previous_risk = 0.0
        for row in episode["rounds"]:
            risk = max((float(v) for v in row.get("risk_before", {}).values()), default=0.0)
            judge = 0.65 * risk + 0.35 * previous_risk
            row["guardagent_judge_score"] = judge
            if judge >= 0.62:
                row.update({"actions": ["judge_refuse"], "actual_student_fields": [], "actual_allowed_chunks": [], "execution_result": "refuse", "normal_task_completion": False, "privacy_cost": 0.0, "copyright_cost": 0.0})
            elif judge >= 0.35:
                row["actions"] = ["judge_rewrite"]
                row["actual_student_fields"] = row.get("actual_student_fields", [])[:1]
                row["actual_allowed_chunks"] = []
            previous_risk = risk


def run() -> dict[str, Any]:
    episodes = load_episodes(DATASET)
    adapter = NeMoGuardrailsAdapter(str(ROOT / "protection" / "cg_guardrails"), enabled=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    def run_controller(name, mode):
        results = _run_mode(mode, deepcopy(episodes), strict_execution_contract=True)
        _apply_shared_nemo(results, episodes, adapter)
        if name == "nemo_agentspec_style":
            _apply_agentspec(results)
        elif name == "nemo_guardagent_style":
            _apply_guardagent(results)
        (OUTPUT / f"{name}.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in results), encoding="utf-8")
        return results
    all_results = run_sequential_suite([
        (name, lambda name=name, mode=mode: run_controller(name, mode))
        for name, mode in CONTROLLERS.items()
    ])
    summaries = {name: compute_mode_metrics(name, rows) for name, rows in all_results.items()}
    (OUTPUT / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {"status": "DEVELOPMENT_ONLY", "shared_backbone": "NeMo-compatible deterministic adapter", "official_nemoguardrails_runtime": adapter.runtime_available, "controllers": CONTROLLERS, "episodes": len(episodes), "rounds_per_controller": sum(len(ep["rounds"]) for ep in next(iter(all_results.values()))), "elapsed_ms": (time.perf_counter() - started) * 1000, "agent_spec_status": "style_adapter_not_official", "guard_agent_status": "style_adapter_not_official"}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": manifest, "summaries": summaries}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
