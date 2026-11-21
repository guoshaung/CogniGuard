"""Minimal deterministic CG V3 experiment kernel.

This module is an experiment adapter. It does not replace the production
controller or modify the classroom/runtime paths.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from cogniguard.agents.agent_orchestrator import CGController
from cogniguard.protection.cg.protocol import CGDecision, stable_hash

from .cg_v3_budget import DualBudgetLedger
from .cg_v3_execution import attach_allowed_payload, execute_plan
from .cg_v3_policy_composer import (
    ComposerConfig,
    _allowed_fields,
    _costs,
    _has_copy_restriction,
    candidate_summary,
    compose_candidates,
    select_plan,
)
from .cg_v3_schemas import ActionPlan, CGInput, CGOutput, CGState
from .cg_v3_state import derive_risks, update_state


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class CGV3Harness:
    """Run static, budget-only, or full experimental controller modes."""

    MODES = {"no_cg", "independent_policy", "static_cg", "budget_only", "full_cg_v3"}

    def __init__(
        self,
        mode: str = "full_cg_v3",
        *,
        privacy_max: float = 1.0,
        copyright_max: float = 1.0,
        composer_config: ComposerConfig | None = None,
        controller: CGController | None = None,
        strict_execution_contract: bool = False,
    ) -> None:
        if mode not in self.MODES:
            raise ValueError(f"unsupported CG V3 mode: {mode}")
        self.mode = mode
        self.strict_execution_contract = strict_execution_contract
        self.config = composer_config or ComposerConfig()
        self.ledger = DualBudgetLedger(privacy_max=privacy_max, copyright_max=copyright_max)
        self.controller = controller or CGController(
            max_disclosure_score=1.0,
            cumulative_privacy_budget=privacy_max,
            session_privacy_budget=privacy_max,
        )
        self._audit_heads: dict[str, str] = {}

    def _validate_capability(self, request: CGInput) -> tuple[bool, str, dict[str, Any]]:
        context = request.capability_context
        sender = str(context.get("sender", "MM-FOPD"))
        receiver = str(context.get("receiver", "profile_diagnosis_agent"))
        message_type = str(context.get("message_type", "diagnosis_request"))
        allowed, reason, required = self.controller.capability_registry.route_allowed(
            sender, receiver, message_type
        )
        purpose = str(context.get("purpose", "legitimate_educational_interest"))
        if purpose not in {"legitimate_educational_interest", "audit_only"}:
            allowed = False
            reason = f"purpose is not allowed by the experimental capability contract: {purpose}"
        details = {
            "sender": sender,
            "receiver": receiver,
            "message_type": message_type,
            "purpose": purpose,
            "required_capabilities": list(required),
        }
        return allowed, reason, details

    def _risk_snapshot(
        self,
        request: CGInput,
        state: CGState,
        *,
        include_audit_feedback: bool = True,
    ) -> dict[str, float]:
        risks = derive_risks(request, state)
        if include_audit_feedback and request.previous_audit_hash != self._audit_heads.get(request.session_id, "GENESIS"):
            risks["audit"] = max(risks["audit"], 0.9)
        score, breakdown = self.controller.risk_scorer.score(
            request.C_u_t,
            str(request.capability_context.get("receiver", "profile_diagnosis_agent")),
            str(request.capability_context.get("purpose", "legitimate_educational_interest")),
        )
        risks["privacy"] = round(min(1.0, max(risks["privacy"], score)), 8)
        request.provenance_evidence.setdefault("protocol_risk_breakdown", breakdown)
        return risks

    def _static_plan(self, request: CGInput, state: CGState, privacy_before: float, copyright_before: float) -> ActionPlan:
        """Call the existing fixed policy engine; this is not a second static policy."""
        from cogniguard.supporting.contrasts.closed_loop import (
            AuditSignal,
            AuditStatus,
            MinimalContextCard,
            PolicyDecision,
            ResourceFeedback,
            ReturnMode,
            RiskLevel,
        )
        from cogniguard.protection.cg.policy_engine import CGPolicyEngine

        context_card = MinimalContextCard(
            card_id=f"v3_{request.round_id}",
            student_hash=hashlib.sha256(request.student_id.encode("utf-8")).hexdigest()[:16],
            task_id=request.round_id,
            knowledge_point=str(request.C_u_t.get("knowledge_point", request.q_t)),
            student_level=str(request.C_u_t.get("student_level", "unknown")),
            mastery_summary=str(request.C_u_t.get("mastery_summary", "minimal")),
            ability_summary=str(request.C_u_t.get("ability_summary", "minimal")),
            learning_behavior_summary=str(request.C_u_t.get("learning_behavior_summary", "minimal")),
            recommended_strategy=str(request.C_u_t.get("recommended_strategy", "guided")),
            resource_need=str(request.C_u_t.get("resource_need", request.q_t)),
            modality_sensitivity=dict(request.C_u_t.get("modality_sensitivity", {"text": 0.0})),
        )
        resource_feedback = ResourceFeedback(
            task_id=request.round_id,
            resource_id=request.resource_id,
            chunk_id=(request.chunk_ids or ["<resource>"])[0],
            resource_difficulty=str(request.CR_t.get("resource_difficulty", "unknown")),
            knowledge_coverage=float(request.CR_t.get("knowledge_coverage", 0.5)),
            return_mode=ReturnMode.SUMMARY,
            variant_performance={},
            resource_fit_score=float(request.CR_t.get("resource_fit_score", 0.5)),
            exposure_score=float(request.CR_t.get("exposure_score", request.Pi_copy.get("exposure_score", 0.0))),
        )
        audit_signal = AuditSignal(
            answer_id=request.round_id,
            watermark_id=str(request.provenance_evidence.get("watermark_id", "")),
            resource_trace_hash=str(request.provenance_evidence.get("resource_trace_hash", "")),
            leakage_risk=RiskLevel.LOW,
            similarity_risk=float(request.CR_t.get("exposure_score", 0.0)),
            multi_turn_reconstruction_risk=min(1.0, state.semantic_repetition * 0.2),
            policy_decision=PolicyDecision.ALLOW,
            audit_status=AuditStatus.NORMAL,
        )
        decision = CGPolicyEngine(policy_log_path=os.devnull).evaluate(
            context_card=context_card,
            resource_feedback=resource_feedback,
            audit_signal=audit_signal,
            action="v3_static_baseline",
            sender_layer="student_profile",
            receiver_layer="cg",
        )
        if not decision.allow or decision.refuse:
            actions = ["refuse", "audit_escalation"]
        elif decision.degrade:
            actions = ["degrade", "audit_escalation"]
        elif decision.sanitize:
            actions = ["mask"]
        elif decision.audit_required:
            actions = ["controlled_excerpt", "watermark"]
        else:
            actions = ["allow"]
        privacy_cost, copyright_cost = _costs(request, tuple(actions), self.config)
        return ActionPlan(
            selected_actions=actions,
            affected_fields=list(request.C_u_t),
            affected_resources=[request.resource_id, *request.chunk_ids],
            parameters={"source_policy_engine": "CGPolicyEngine"},
            decision_reason=f"existing static policy engine: {decision.reason}",
            risk_before=self._risk_snapshot(request, state, include_audit_feedback=False),
            expected_risk_after=self._risk_snapshot(request, state, include_audit_feedback=False),
            privacy_cost=privacy_cost,
            copyright_cost=copyright_cost,
            privacy_budget_before=privacy_before,
            privacy_budget_after=max(0.0, self.ledger.privacy_max - privacy_before - privacy_cost),
            copyright_budget_before=copyright_before,
            copyright_budget_after=max(0.0, self.ledger.copyright_max - copyright_before - copyright_cost),
            audit_evidence_required=["action_plan", "actual_disclosure", "audit_hash"],
        )

    def _budget_only_plan(self, request: CGInput, state: CGState, privacy_before: float, copyright_before: float) -> ActionPlan:
        privacy_cost, copyright_cost = _costs(request, ("allow",), self.config)
        if privacy_before + privacy_cost > self.ledger.privacy_max or copyright_before + copyright_cost > self.ledger.copyright_max:
            actions = ("degrade", "audit_escalation")
            degraded_privacy, degraded_copyright = _costs(request, actions, self.config)
            if privacy_before + degraded_privacy > self.ledger.privacy_max or copyright_before + degraded_copyright > self.ledger.copyright_max:
                actions = ("refuse", "audit_escalation")
        else:
            actions = ("allow",)
        privacy_cost, copyright_cost = _costs(request, actions, self.config)
        risks = self._risk_snapshot(request, state, include_audit_feedback=False)
        return ActionPlan(
            selected_actions=list(actions),
            affected_fields=list(request.C_u_t),
            affected_resources=[request.resource_id, *request.chunk_ids],
            parameters={"mode": "budget_only"},
            decision_reason="budget-only baseline; history, trust and candidate composition disabled",
            risk_before=risks,
            expected_risk_after=risks,
            privacy_cost=privacy_cost,
            copyright_cost=copyright_cost,
            privacy_budget_before=privacy_before,
            privacy_budget_after=max(0.0, self.ledger.privacy_max - privacy_before - privacy_cost),
            copyright_budget_before=copyright_before,
            copyright_budget_after=max(0.0, self.ledger.copyright_max - copyright_before - copyright_cost),
            audit_evidence_required=["action_plan", "actual_disclosure", "audit_hash"],
        )

    def _no_cg_plan(self, request: CGInput, privacy_before: float, copyright_before: float) -> ActionPlan:
        privacy_cost, copyright_cost = _costs(request, ("allow",), self.config)
        return ActionPlan(
            selected_actions=["allow"],
            affected_fields=list(request.C_u_t),
            affected_resources=[request.resource_id, *request.chunk_ids],
            parameters={"mode": "no_cg", "permissive": True},
            decision_reason="No-CG permissive lower-bound baseline; ledger observes only",
            risk_before={"privacy": 0.0, "copyright": 0.0, "audit": 0.0},
            expected_risk_after={"privacy": 0.0, "copyright": 0.0, "audit": 0.0},
            privacy_cost=privacy_cost,
            copyright_cost=copyright_cost,
            privacy_budget_before=privacy_before,
            privacy_budget_after=max(0.0, self.ledger.privacy_max - privacy_before - privacy_cost),
            copyright_budget_before=copyright_before,
            copyright_budget_after=max(0.0, self.ledger.copyright_max - copyright_before - copyright_cost),
            audit_evidence_required=["action_plan", "actual_disclosure", "audit_hash"],
        )

    def _independent_plan(self, request: CGInput, privacy_before: float, copyright_before: float) -> tuple[ActionPlan, list[dict[str, Any]]]:
        allowed_fields = _allowed_fields(request)
        privacy_restricted = set(request.C_u_t) - set(allowed_fields) or set(request.Pi_priv.get("forbidden_fields", [])).intersection(request.C_u_t)
        privacy_actions = ("minimize",) if privacy_restricted else ("allow",)
        if not allowed_fields and request.C_u_t:
            privacy_actions = ("refuse", "audit_escalation")
        copyright_restricted = _has_copy_restriction(request)
        copyright_actions = ("controlled_excerpt", "watermark") if copyright_restricted else ("allow",)
        privacy_projection = _costs(request, tuple(privacy_actions), self.config)[0]
        copyright_projection = _costs(request, tuple(copyright_actions), self.config)[1]
        if privacy_before + privacy_projection > self.ledger.privacy_max + 1e-9:
            privacy_actions = ("refuse", "audit_escalation")
        if copyright_before + copyright_projection > self.ledger.copyright_max + 1e-9:
            copyright_actions = ("refuse", "audit_escalation")
        actions = list(dict.fromkeys([*privacy_actions, *copyright_actions]))
        privacy_cost, copyright_cost = _costs(request, tuple(actions), self.config)
        plan = ActionPlan(
            selected_actions=actions,
            affected_fields=allowed_fields,
            affected_resources=[request.resource_id, *request.chunk_ids],
            parameters={
                "mode": "independent_policy",
                "privacy_branch": list(privacy_actions),
                "copyright_branch": list(copyright_actions),
                "merge_rule": "union domain transforms; refuse dominates",
            },
            decision_reason="independent privacy/copyright branches with fixed merge rule",
            risk_before={
                "privacy": 1.0 if privacy_restricted else 0.0,
                "copyright": float(request.CR_t.get("exposure_score", request.Pi_copy.get("exposure_score", 0.0))),
                "audit": 0.0,
            },
            expected_risk_after={"privacy": 0.0 if "refuse" in actions else 0.5, "copyright": 0.0 if "refuse" in actions else 0.5, "audit": 0.0},
            privacy_cost=privacy_cost,
            copyright_cost=copyright_cost,
            privacy_budget_before=privacy_before,
            privacy_budget_after=max(0.0, self.ledger.privacy_max - privacy_before - privacy_cost),
            copyright_budget_before=copyright_before,
            copyright_budget_after=max(0.0, self.ledger.copyright_max - copyright_before - copyright_cost),
            audit_evidence_required=["action_plan", "actual_disclosure", "audit_hash"],
        )
        candidates = [
            {"actions": list(privacy_actions), "score": 0.0, "feasible": True, "selected": False, "source": "independent_privacy_policy"},
            {"actions": list(copyright_actions), "score": 0.0, "feasible": True, "selected": False, "source": "independent_copyright_policy"},
            {"actions": actions, "score": 0.0, "feasible": True, "selected": True, "source": "fixed_merge_rule"},
        ]
        return plan, candidates

    @staticmethod
    def _mechanism_snapshot(mode: str) -> dict[str, bool]:
        return {
            "privacy_policy_enabled": mode in {"independent_policy", "static_cg", "full_cg_v3"},
            "copyright_policy_enabled": mode in {"independent_policy", "static_cg", "full_cg_v3"},
            "joint_composer_enabled": mode == "full_cg_v3",
            "privacy_budget_enabled": mode in {"independent_policy", "budget_only", "full_cg_v3"},
            "copyright_budget_enabled": mode in {"independent_policy", "budget_only", "full_cg_v3"},
            "history_enabled": mode == "full_cg_v3",
            "trust_enabled": mode == "full_cg_v3",
            "provenance_enabled": mode == "full_cg_v3",
            "audit_feedback_enabled": mode == "full_cg_v3",
            "dynamic_action_scoring_enabled": mode == "full_cg_v3",
            "execution_contract_enabled": True,
        }

    def _append_audit(self, request: CGInput, plan: ActionPlan, actual: Mapping[str, Any], audit_valid: bool) -> tuple[dict[str, Any], str]:
        previous_hash = self._audit_heads.get(request.session_id, "GENESIS")
        protocol_decision = CGDecision.DENY if {"block", "refuse"}.intersection(plan.selected_actions) else CGDecision.DEGRADE if "degrade" in plan.selected_actions else CGDecision.ALLOW
        message = self.controller.build_message(
            sender="CGController",
            receiver="HSW-ST",
            message_type="final_answer_audit",
            payload={
                "round_id": request.round_id,
                "student_fields": sorted(actual.get("student_fields", [])),
                "resource_ids": sorted(actual.get("resource_ids", [])),
                "action": plan.selected_actions,
            },
            privacy_level="experiment_summary",
            round_id=request.round_id,
            purpose="audit_only",
        )
        self.controller.audit_chain.append(
            event_type="cg_v3_execution",
            message=message,
            decision=protocol_decision,
            reason=plan.decision_reason,
            policy_id="cg.v3.experiment_adapter",
            risk_score=max(plan.risk_before.values()),
        )
        record = {
            "session_id": request.session_id,
            "round_id": request.round_id,
            "previous_hash": previous_hash,
            "action": list(plan.selected_actions),
            "actual_student_fields": sorted(actual.get("student_fields", [])),
            "actual_resource_ids": sorted(actual.get("resource_ids", [])),
            "privacy_cost": actual.get("privacy_cost", 0.0),
            "copyright_cost": actual.get("copyright_cost", 0.0),
            "projected_privacy_cost": actual.get("projected_privacy_cost", plan.projected_privacy_cost),
            "projected_copyright_cost": actual.get("projected_copyright_cost", plan.projected_copyright_cost),
            "reserved_privacy_cost": actual.get("reserved_privacy_cost", 0.0),
            "reserved_copyright_cost": actual.get("reserved_copyright_cost", 0.0),
            "committed_privacy_cost": actual.get("committed_privacy_cost", actual.get("privacy_cost", 0.0)),
            "committed_copyright_cost": actual.get("committed_copyright_cost", actual.get("copyright_cost", 0.0)),
            "actual_privacy_disclosure": actual.get("actual_privacy_disclosure", {}),
            "actual_copyright_disclosure": actual.get("actual_copyright_disclosure", {}),
            "output_violation": actual.get("output_violation", False),
            "rolled_back": actual.get("rolled_back", False),
            "budget_violation": bool(
                float(actual.get("privacy_cost", 0.0)) > self.ledger.privacy_max - plan.privacy_budget_before + 1e-9
                or float(actual.get("copyright_cost", 0.0)) > self.ledger.copyright_max - plan.copyright_budget_before + 1e-9
            ),
            "audit_valid": audit_valid,
            "protocol_chain_valid": self.controller.verify_audit_chain(),
        }
        current_hash = stable_hash(record)
        self._audit_heads[request.session_id] = current_hash
        record["current_hash"] = current_hash
        return record, current_hash

    def run(
        self,
        request: CGInput | Mapping[str, Any],
        *,
        actual_student_context: Mapping[str, Any] | None = None,
        actual_teacher_resource: Mapping[str, Any] | None = None,
        attack_indicators: list[str] | None = None,
    ) -> CGOutput:
        from .cg_v3_graph import run_cg_graph
        return run_cg_graph(
            self, request,
            actual_student_context=actual_student_context,
            actual_teacher_resource=actual_teacher_resource,
            attack_indicators=attack_indicators,
        )

    def _run_steps(
        self,
        request: CGInput | Mapping[str, Any],
        *,
        actual_student_context: Mapping[str, Any] | None = None,
        actual_teacher_resource: Mapping[str, Any] | None = None,
        attack_indicators: list[str] | None = None,
    ):
        request = request if isinstance(request, CGInput) else CGInput.from_mapping(request)
        previous = CGState.from_mapping(request.previous_state)
        current_head = self._audit_heads.get(request.session_id, "GENESIS")
        audit_valid = request.previous_audit_hash == current_head
        self.controller.session_id = request.session_id
        self.controller.student_id = request.student_id
        if self.mode == "no_cg":
            capability_allowed = True
            capability_reason = "No-CG capability bypass"
            capability_details = {
                "sender": str(request.capability_context.get("sender", "MM-FOPD")),
                "receiver": str(request.capability_context.get("receiver", "profile_diagnosis_agent")),
                "message_type": str(request.capability_context.get("message_type", "diagnosis_request")),
                "purpose": str(request.capability_context.get("purpose", "legitimate_educational_interest")),
                "required_capabilities": [],
            }
        else:
            capability_allowed, capability_reason, capability_details = self._validate_capability(request)
        request.capability_context = {**request.capability_context, **capability_details, "allowed": capability_allowed}
        execution_request = request
        if self.mode == "no_cg":
            execution_request = CGInput.from_mapping({
                **request.to_dict(),
                "Pi_priv": {"allowed_fields": list(request.C_u_t)},
                "Pi_copy": {"allow_original": True},
            })
        yield "authorize"

        privacy_projection = self.ledger.project_privacy(request.student_id, request.session_id, request.round_id, 0.0)
        copyright_projection = self.ledger.project_copyright(request.resource_id, request.chunk_ids, request.session_id, 0.0)
        decision_uses_history = self.mode == "full_cg_v3"
        decision_uses_audit_feedback = self.mode == "full_cg_v3"
        state_for_decision = (
            CGState.from_mapping(previous.to_dict())
            if decision_uses_history
            else CGState()
        )
        if decision_uses_audit_feedback and not audit_valid:
            state_for_decision.audit_risk = max(state_for_decision.audit_risk, 0.95)
        if not capability_allowed:
            state_for_decision.audit_risk = max(state_for_decision.audit_risk, 0.9)
        yield "project_budgets"

        if self.mode == "no_cg":
            plan = self._no_cg_plan(execution_request, privacy_projection.before, copyright_projection.before)
            candidates = [{"actions": plan.selected_actions, "score": 0.0, "feasible": True, "selected": True, "source": "permissive_no_cg"}]
        elif self.mode == "independent_policy":
            plan, candidates = self._independent_plan(request, privacy_projection.before, copyright_projection.before)
        elif self.mode == "static_cg":
            plan = self._static_plan(request, state_for_decision, privacy_projection.before, copyright_projection.before)
            candidates = [{"actions": plan.selected_actions, "score": plan.score, "feasible": True, "selected": True, "source": "CGPolicyEngine", "score_breakdown": plan.score_breakdown}]
        elif self.mode == "budget_only":
            plan = self._budget_only_plan(request, state_for_decision, privacy_projection.before, copyright_projection.before)
            candidates = [{"actions": plan.selected_actions, "score": plan.score, "feasible": True, "selected": True, "source": "DualBudgetLedger"}]
        else:
            candidates_by_score = compose_candidates(request, state_for_decision, privacy_projection, copyright_projection, self.config)
            if not capability_allowed:
                for candidate in candidates_by_score:
                    if candidate.selected_actions != ["block"]:
                        candidate.feasible = False
                        candidate.score = float("-inf")
                        candidate.infeasible_reason = capability_reason
            plan = select_plan(candidates_by_score)
            candidates = candidate_summary(candidates_by_score, plan)

        if not capability_allowed:
            plan.selected_actions = ["block"]
            plan.decision_reason = f"capability registry denied route: {capability_reason}"
        if decision_uses_audit_feedback and not audit_valid and "audit_escalation" not in plan.selected_actions:
            plan.selected_actions = ["refuse", "audit_escalation"]
            plan.decision_reason = "previous audit hash does not match the session chain head"

        projected_privacy_cost = plan.privacy_cost
        projected_copyright_cost = plan.copyright_cost
        plan.projected_privacy_cost = projected_privacy_cost
        plan.projected_copyright_cost = projected_copyright_cost
        attach_allowed_payload(execution_request, plan)
        yield "select_plan"
        measurement = execute_plan(
            execution_request,
            plan,
            self.config,
            privacy_remaining=self.ledger.privacy_max - privacy_projection.before,
            copyright_remaining=self.ledger.copyright_max - copyright_projection.before,
            supplied_student_context=actual_student_context,
            supplied_teacher_resource=actual_teacher_resource,
            allow_static_budget_violation=self.mode in {"static_cg", "no_cg"},
            strict_output_enforcement=self.strict_execution_contract,
        )
        if measurement.effective_actions != plan.selected_actions:
            plan.selected_actions = list(measurement.effective_actions)
            plan.decision_reason = f"execution contract fallback: {measurement.fallback_reason}"
            projected_privacy_cost, projected_copyright_cost = _costs(
                execution_request, tuple(plan.selected_actions), self.config
            )
            plan.projected_privacy_cost = projected_privacy_cost
            plan.projected_copyright_cost = projected_copyright_cost
            plan.privacy_cost = projected_privacy_cost
            plan.copyright_cost = projected_copyright_cost
            attach_allowed_payload(execution_request, plan)
        yield "execute"
        actual_privacy_cost = measurement.actual_privacy_cost
        actual_copy_cost = measurement.actual_copyright_cost
        privacy_after = self.ledger.commit_privacy(
            request.student_id, request.session_id, request.round_id, actual_privacy_cost
        )
        copyright_after = self.ledger.commit_copyright(
            request.resource_id, request.chunk_ids, request.session_id, actual_copy_cost
        )
        snapshot = self.ledger.snapshot(
            request.student_id, request.session_id, request.round_id, request.resource_id, request.chunk_ids
        )
        reserved_privacy_cost = projected_privacy_cost if projected_privacy_cost <= self.ledger.privacy_max - privacy_projection.before + 1e-9 else 0.0
        reserved_copyright_cost = projected_copyright_cost if projected_copyright_cost <= self.ledger.copyright_max - copyright_projection.before + 1e-9 else 0.0
        actual = {
            "student_fields": measurement.actual_student_fields,
            "resource_ids": [request.resource_id] if measurement.teacher_resource else [],
            "privacy_cost": actual_privacy_cost,
            "copyright_cost": actual_copy_cost,
            "projected_privacy_cost": projected_privacy_cost,
            "projected_copyright_cost": projected_copyright_cost,
            "reserved_privacy_cost": reserved_privacy_cost,
            "reserved_copyright_cost": reserved_copyright_cost,
            "committed_privacy_cost": actual_privacy_cost,
            "committed_copyright_cost": actual_copy_cost,
            "actual_privacy_disclosure": measurement.actual_privacy_disclosure,
            "actual_copyright_disclosure": measurement.actual_copyright_disclosure,
            "output_violation": measurement.output_violation,
            "rolled_back": measurement.rolled_back,
        }
        yield "commit"
        audit_record, audit_hash = self._append_audit(request, plan, actual, audit_valid)
        updated = update_state(
            request,
            previous,
            privacy_exposure=actual_privacy_cost,
            copyright_exposure=actual_copy_cost,
            budget_snapshot=snapshot,
            audit_valid=audit_valid,
            attack_indicators=attack_indicators or [],
        )
        updated.previous_actions = [*previous.previous_actions, list(plan.selected_actions)][-8:]
        updated.last_semantic_intent = updated.last_semantic_intent
        audit_record["trust_before"] = previous.trust_score
        audit_record["trust_after"] = updated.trust_score
        audit_record["risk_before"] = plan.risk_before
        audit_record["risk_after"] = {
            "privacy": updated.privacy_risk,
            "copyright": updated.copyright_risk,
            "audit": updated.audit_risk,
        }
        execution_result = "block" if "block" in plan.selected_actions else "refuse" if "refuse" in plan.selected_actions else "degrade" if "degrade" in plan.selected_actions else "allow"
        plan.privacy_budget_after = privacy_after.maximum - privacy_after.after
        plan.copyright_budget_after = copyright_after.maximum - copyright_after.after
        plan.privacy_cost = actual_privacy_cost
        plan.copyright_cost = actual_copy_cost
        plan.privacy_budget_before = privacy_after.before
        plan.copyright_budget_before = copyright_after.before
        joint_constraints = None
        if self.mode not in {"no_cg", "independent_policy"}:
            joint_constraints = {
                "privacy": request.Pi_priv,
                "copyright": request.Pi_copy,
                "allowed_student_fields": measurement.actual_privacy_disclosure.get("fields", []),
                "allowed_resource_keys": sorted(measurement.teacher_resource),
                "allowed_chunks": measurement.actual_copyright_disclosure.get("chunks", []),
                "return_mode": measurement.actual_copyright_disclosure.get("return_mode", "none"),
                "verbatim_ratio": measurement.actual_copyright_disclosure.get("verbatim_ratio", 0.0),
            }
        yield "audit_feedback"
        return CGOutput(
            Pi_joint={
                "mode": self.mode,
                "privacy_policy": request.Pi_priv,
                "copyright_policy": request.Pi_copy,
                "capability_allowed": capability_allowed,
                "audit_valid": audit_valid,
                "dynamic_composer_used": self.mode == "full_cg_v3",
                "history_feedback_used": decision_uses_history,
                "trust_feedback_used": decision_uses_history,
                "audit_feedback_used": decision_uses_audit_feedback,
                "composer_generated_constraints": joint_constraints,
                "pi_joint": joint_constraints if self.mode == "full_cg_v3" else None,
                "mechanism_snapshot": self._mechanism_snapshot(self.mode),
            },
            action_plan=plan,
            allowed_student_context=measurement.student_context,
            allowed_teacher_resource=measurement.teacher_resource,
            updated_state=updated,
            audit_record=audit_record,
            audit_hash=audit_hash,
            execution_result=execution_result,
            candidate_plans=candidates,
        )

    def export_snapshot(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": self.config.to_dict(),
            "budget_ledger": self.ledger.export_snapshot(),
            "audit_heads": dict(self._audit_heads),
            "protocol_audit_chain_verified": self.controller.verify_audit_chain(),
        }


def run_episode(
    requests: list[CGInput | Mapping[str, Any]],
    *,
    mode: str = "full_cg_v3",
    privacy_max: float = 1.0,
    copyright_max: float = 1.0,
) -> list[dict[str, Any]]:
    harness = CGV3Harness(mode=mode, privacy_max=privacy_max, copyright_max=copyright_max)
    results: list[dict[str, Any]] = []
    for request in requests:
        output = harness.run(request)
        data = output.to_dict()
        data["input_hash"] = _json_hash(request.to_dict() if isinstance(request, CGInput) else dict(request))
        data["controller_mode"] = mode
        results.append(data)
    return results
