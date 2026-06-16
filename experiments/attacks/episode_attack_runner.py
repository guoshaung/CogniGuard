from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.scenario_loader import (
    build_episode_bundle,
    list_episode_samples,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class EpisodeAttackRunner:
    seed: int = 42

    def __post_init__(self) -> None:
        self.random = random.Random(self.seed)

    def run_episode(self, episode_id: str) -> dict[str, Any]:
        bundle = build_episode_bundle(episode_id)
        episode = bundle["episode"]
        profile = bundle["student_profile"]
        resource = bundle["teacher_resource"]
        attack_template = bundle["attack_template"]

        profile_card = profile.get("context_card", {})
        context_flow = episode.get("context_flow", {})
        expected_protection = episode.get("expected_protection", {})
        attack_type = attack_template.get("attack_type", "unknown")

        profile_exposure = min(
            float(expected_protection.get("max_profile_exposure", 0.25)),
            float(profile_card.get("disclosure_score", 0.25)),
        )
        resource_exposure = min(
            float(expected_protection.get("max_resource_exposure", 0.3)),
            float(context_flow.get("resource_to_audit", {}).get("exposure_score", 0.2)),
        )
        risk_level = str(profile.get("risk_level", "medium")).lower()
        risk_weight = {"low": 0.2, "medium": 0.5, "high": 0.8}.get(risk_level, 0.5)

        attack_success_probability = self._estimate_attack_success(
            attack_type=attack_type,
            risk_weight=risk_weight,
            profile_exposure=profile_exposure,
            resource_exposure=resource_exposure,
            tpcs_decision=str(expected_protection.get("tpcs_decision", "allow")),
        )
        attack_success = self.random.random() < attack_success_probability
        blocked = not attack_success_probability > 0.55
        audit_coverage = 1.0 if "audit" in attack_type or context_flow.get("audit_to_profile") else 0.92

        attacker_prompt = attack_template.get("prompt_template", "")
        rendered_prompt = attacker_prompt.format(
            context_card=profile_card,
            agent_output={
                "knowledge_points": profile.get("knowledge_points", []),
                "mastery_state": profile.get("mastery_state", {}),
            },
            resource_id=resource.get("resource_id"),
            chunk_id=resource.get("chunk_id"),
            injection_payload="[malicious override payload]",
            policy_budget=expected_protection,
            task_type=episode.get("scenario_type"),
            audit_mode=profile.get("recordable_scope", "bounded"),
        )

        trace = {
            "episode_id": episode_id,
            "attack_type": attack_type,
            "attacker_role": attack_template.get("attacker_role"),
            "target_layer": attack_template.get("target_layer"),
            "rendered_prompt": rendered_prompt,
            "student_to_resource": context_flow.get("student_to_resource", {}),
            "resource_to_audit": context_flow.get("resource_to_audit", {}),
            "audit_to_profile": context_flow.get("audit_to_profile", {}),
            "tpcs_decision": expected_protection.get("tpcs_decision"),
            "blocked": blocked,
            "attack_success": attack_success,
            "attack_success_probability": round(attack_success_probability, 4),
            "profile_exposure": round(profile_exposure, 4),
            "resource_exposure": round(resource_exposure, 4),
            "privacy_leakage": round(profile_exposure if attack_type != "copyright_extraction" else 0.04, 4),
            "copyright_leakage": round(resource_exposure if attack_type == "copyright_extraction" else 0.02, 4),
            "audit_coverage": audit_coverage,
            "multi_round_reconstruction_risk": round(min(0.95, resource_exposure + profile_exposure + risk_weight * 0.2), 4),
            "expected_protection": expected_protection,
            "evaluation_targets": episode.get("evaluation_targets", []),
        }
        return trace

    def run_all(self) -> dict[str, Any]:
        traces = [self.run_episode(ep["episode_id"]) for ep in list_episode_samples()]
        total = len(traces)
        successful = sum(1 for trace in traces if trace["attack_success"])
        blocked = sum(1 for trace in traces if trace["blocked"])
        privacy_leakage = sum(trace["privacy_leakage"] for trace in traces) / total if total else 0.0
        copyright_leakage = sum(trace["copyright_leakage"] for trace in traces) / total if total else 0.0
        audit_coverage = sum(trace["audit_coverage"] for trace in traces) / total if total else 0.0
        return {
            "summary": {
                "episodes": total,
                "attack_success_rate": round(successful / total, 4) if total else 0.0,
                "blocked_rate": round(blocked / total, 4) if total else 0.0,
                "privacy_leakage_rate": round(privacy_leakage, 4),
                "copyright_leakage_rate": round(copyright_leakage, 4),
                "audit_coverage_rate": round(audit_coverage, 4),
            },
            "traces": traces,
        }

    def save_results(self, output_path: str | Path | None = None) -> Path:
        if output_path is None:
            output_path = PROJECT_ROOT / "experiments" / "results" / "episode_attack_eval.json"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.run_all(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def _estimate_attack_success(
        self,
        *,
        attack_type: str,
        risk_weight: float,
        profile_exposure: float,
        resource_exposure: float,
        tpcs_decision: str,
    ) -> float:
        base = {
            "membership_inference": 0.28,
            "model_inversion": 0.22,
            "copyright_extraction": 0.18,
            "prompt_injection": 0.26,
            "audit_evasion": 0.2,
        }.get(attack_type, 0.24)
        decision_penalty = 0.18 if "refuse" in tpcs_decision else 0.12 if "degrade" in tpcs_decision else 0.05
        probability = base + profile_exposure * 0.45 + resource_exposure * 0.3 + risk_weight * 0.15 - decision_penalty
        return max(0.02, min(0.92, probability))


def main() -> None:
    runner = EpisodeAttackRunner()
    output_path = runner.save_results()
    print(f"Episode attack evaluation saved to: {output_path}")


if __name__ == "__main__":
    main()
