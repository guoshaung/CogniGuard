from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cogniguard.applications.education.cases import DemoCase

EventSink = Callable[[dict[str, Any]], None]


class DemoC2RAGService:
    """Small C2-RAG adapter used by the integrated dashboard demo."""

    def __init__(self, demo_case: DemoCase | None = None) -> None:
        self.demo_case = demo_case

    def retrieve(
        self,
        *,
        teaching_request: dict[str, Any],
        knowledge_point: str,
        allowed_return_modes: list[str],
        candidate_inspector: Callable | None = None,
    ) -> list[dict[str, Any]]:
        resource = dict(self.demo_case.teacher_resource or {}) if self.demo_case else {}
        if candidate_inspector is not None and resource:
            candidates = candidate_inspector([resource])
            if not candidates:
                return []
            resource = dict(candidates[0])
        copyright_level = _safe_float(resource.get("copyright_level"), 0.58)
        mode = _select_return_mode(copyright_level, allowed_return_modes)
        content = _controlled_content(
            knowledge_point=knowledge_point,
            return_mode=mode,
            teaching_request=teaching_request,
        )
        if candidate_inspector is not None:
            candidates = candidate_inspector(
                [
                    {
                        "resource_id": str(resource.get("resource_id") or "teacher_resource_demo"),
                        "chunk_id": str(resource.get("chunk_id") or "chunk_demo_001"),
                        "content": content,
                    }
                ]
            )
            if not candidates:
                return []
            content = str(candidates[0]["content"])
        # The demo domain adapter computes cost and bindings only after the
        # candidate has passed instruction isolation; the Agent never rehashes.
        exposure_cost = _exposure_cost(mode, copyright_level)
        source_trace = _demo_resource_source_trace(
            resource=resource,
            content=content,
            return_mode=mode,
            copyright_level=copyright_level,
            exposure_cost=exposure_cost,
        )
        return [
            {
                "resource_id": str(resource.get("resource_id") or "teacher_resource_demo"),
                "chunk_id": str(resource.get("chunk_id") or "chunk_demo_001"),
                "copyright_level": copyright_level,
                "return_mode": mode,
                "content": content,
                "exposure_cost": exposure_cost,
                "source_type": str(resource.get("source_type") or "teacher_resource_repository"),
                "license_type": str(resource.get("license_type") or "course_limited_license"),
                "source_trace_id": source_trace["source_trace_id"],
                "policy_reason": source_trace["policy_reason"],
                "retrieval_trace": source_trace["retrieval_trace"],
                "quote_span_hash": source_trace["quote_span_hash"],
                "controlled_output_hash": source_trace["controlled_output_hash"],
                "resource_provenance_commitment": source_trace["resource_provenance_commitment"],
                "source_trace": source_trace,
            }
        ]


class DemoHSWSTBinder:
    """Binds a final answer to a deterministic audit and watermark envelope."""

    def bind(
        self,
        *,
        teaching_answer: str,
        answer_id: str,
        profile_card_id: str,
        controlled_resource_snippets: list[dict[str, Any]],
        agent_call_logs: list[dict[str, Any]],
        communication_logs: list[dict[str, Any]],
        profile_update_logs: dict[str, Any],
    ) -> dict[str, Any]:
        timestamp = _utc_now()
        resource_bindings = [
            {
                "resource_id": item.get("resource_id"),
                "chunk_id": item.get("chunk_id"),
                "return_mode": item.get("return_mode"),
                "copyright_level": item.get("copyright_level"),
                "exposure_cost": item.get("exposure_cost"),
                "source_trace_id": item.get("source_trace_id"),
                "trace_owner": "C2-RAG",
                "resource_provenance_commitment": item.get("resource_provenance_commitment"),
                "quote_span_hash": item.get("quote_span_hash"),
                "policy_reason": item.get("policy_reason"),
            }
            for item in controlled_resource_snippets
        ]
        canonical = json.dumps(
            {
                "answer_id": answer_id,
                "profile_card_id": profile_card_id,
                "resource_bindings": resource_bindings,
                "answer": teaching_answer,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        audit_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        watermark_id = f"wm_demo_{audit_hash[:12]}"
        final_answer = teaching_answer.strip()
        if watermark_id not in final_answer:
            final_answer = f"{final_answer}\n\n[Audit watermark: {watermark_id}]"

        audit_trace = {
            "answer_id": answer_id,
            "watermark_id": watermark_id,
            "profile_card_id": profile_card_id,
            "resource_bindings": resource_bindings,
            "agent_call_logs": agent_call_logs,
            "communication_logs": communication_logs,
            "profile_update_logs": profile_update_logs,
            "audit_hash": audit_hash,
            "audit_status": "auditable_demo_watermark_bound",
            "timestamp": timestamp,
            "audit_complete": True,
        }
        return {
            "final_protected_answer": final_answer,
            "audit_trace": audit_trace,
        }


def run_case_study(
    data_root: str | Path = "data",
    case_index: int = 0,
    event_sink: EventSink | None = None,
    episode_id: str | None = None,
    *,
    session_token: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    from cogniguard.runtime.gateway import get_gateway
    from cogniguard.workflows.education.case_study import run_demo_graph

    result = get_gateway().run(
        "case",
        {"case_index": case_index, "episode_id": episode_id},
        lambda frame: run_demo_graph(data_root, case_index, None, episode_id),
        session_token=session_token,
        request_id=request_id,
    )
    if event_sink is not None:
        for step in result.get("workflow_steps", []):
            event_sink({"type": "workflow_step", "step": step})
    return result


run_demo = run_case_study


def _build_workflow_steps(
    *,
    demo_case: DemoCase,
    flow: dict[str, Any],
    final_answer: str,
    audit_trace: dict[str, Any],
    runtime_status: dict[str, Any],
    protection_logs: dict[str, Any],
) -> list[dict[str, Any]]:
    nemo_decision = "allow" if runtime_status.get("nemo_guardrails_enabled") else "not_enabled"
    return [
        _step(
            1,
            "Raw Multimodal Intake",
            "MM-FOPD",
            demo_case.raw_data_summary,
            {"raw_payload_sent_to_agents": False},
            "allow",
            nemo_decision,
            0.1,
        ),
        _step(
            2,
            "Enhanced FOPD Profile Encoding",
            "Enhanced MM-FOPD",
            demo_case.abstract_profile or {},
            flow["profile_encoding"],
            "allow",
            nemo_decision,
            0.16,
        ),
        _step(
            3,
            "Minimum Context Card",
            "MM-FOPD",
            "abstract profile bundle",
            flow["context_card"],
            "allow",
            nemo_decision,
            0.18,
        ),
        _step(
            4,
            "CG Privacy Pre-check",
            "CG",
            flow["context_card"],
            flow["cg_pre_check"],
            "allow",
            nemo_decision,
            0.14,
        ),
        _step(
            5,
            "Learner Profile Diagnosis",
            "ProfileDiagnosisAgent",
            flow["profile_encoding"],
            flow["diagnosis_result"],
            "allow",
            nemo_decision,
            0.2,
        ),
        _step(
            6,
            "C2-RAG Resource Control",
            "CopyrightAwareResourceAgent",
            flow["diagnosis_result"],
            flow["controlled_resource_snippets"],
            "allow",
            nemo_decision,
            0.22,
        ),
        _step(
            7,
            "Protected Teaching Generation",
            "PedagogicalTeachingAgent",
            flow["controlled_resource_snippets"],
            flow["teaching_answer"],
            "allow",
            nemo_decision,
            0.18,
        ),
        _step(
            8,
            "Learning Assessment Evidence",
            "LearningAssessmentAgent",
            demo_case.simulated_student_response,
            flow["assessment_result"],
            "allow",
            nemo_decision,
            0.19,
        ),
        _step(
            9,
            "Profile Update Gate",
            "CG",
            flow["assessment_result"].get("profile_update_evidence", {}),
            flow["profile_update_approval"],
            "allow",
            nemo_decision,
            0.12,
        ),
        _step(
            10,
            "HSW-ST Watermark Binding",
            "HSW-ST",
            flow["teaching_answer"],
            audit_trace,
            "allow",
            nemo_decision,
            0.1,
        ),
        _step(
            11,
            "Audit Chain Commit",
            "HSW-ST",
            audit_trace.get("audit_hash"),
            {"audit_complete": audit_trace.get("audit_complete")},
            "allow",
            nemo_decision,
            0.08,
        ),
        _step(
            12,
            "Closed-loop Feedback Snapshot",
            "CG Closed Loop",
            protection_logs,
            {"final_answer_preview": final_answer[:220]},
            "allow",
            nemo_decision,
            0.11,
        ),
    ]


def _step(
    number: int,
    name: str,
    layer: str,
    input_summary: Any,
    output_summary: Any,
    cg_decision: str,
    nemo_decision: str,
    risk_score: float,
) -> dict[str, Any]:
    return {
        "step_id": f"step_{number:03d}",
        "step_name": name,
        "layer": layer,
        "input_summary": _summarize(input_summary),
        "output_summary": _summarize(output_summary),
        "cg_decision": cg_decision,
        "nemo_decision": nemo_decision,
        "risk_score": round(float(risk_score), 4),
        "timestamp": _utc_now(),
    }


def _build_protection_logs(
    *,
    context_card: dict[str, Any],
    profile_encoding: dict[str, Any],
    snippets: list[dict[str, Any]],
    audit_trace: dict[str, Any],
    cg_pre_check: dict[str, Any],
    profile_update: dict[str, Any],
    runtime_status: dict[str, Any],
    compliance_state: dict[str, Any],
    compliance_policy: dict[str, Any],
    compliance_audit_log: list[dict[str, Any]],
) -> dict[str, Any]:
    exposure_cost = round(
        sum(_safe_float(item.get("exposure_cost"), 0.0) for item in snippets),
        4,
    )
    return {
        "mm_fopd": {
            "path": "enhanced",
            "use_enhanced_fopd": True,
            "disclosure_score": context_card.get("disclosure_score", 0.24),
            "privacy_level": context_card.get("privacy_level", "MM-FOPD-minimum-context"),
            "profile_encoding": profile_encoding,
            "student_privacy_state": {
                "raw_payload_sent_to_agents": False,
                "profile_encoding_only": True,
                "forbidden_fields": context_card.get("forbidden_profile_fields", []),
            },
        },
        "c2_rag": {
            "snippet_count": len(snippets),
            "return_modes": [item.get("return_mode") for item in snippets],
            "exposure_cost": exposure_cost,
            "trace_scope": "resource_level_provenance",
            "trace_owner": "C2-RAG",
            "watermark_boundary": "generation_watermarking_is_owned_by_HSW-ST",
            "source_traces": [
                item.get("source_trace") for item in snippets if item.get("source_trace")
            ],
            "resource_provenance_commitments": [
                item.get("resource_provenance_commitment")
                for item in snippets
                if item.get("resource_provenance_commitment")
            ],
            "quote_span_hashes": [
                item.get("quote_span_hash") for item in snippets if item.get("quote_span_hash")
            ],
            "policy_reasons": [
                item.get("policy_reason") for item in snippets if item.get("policy_reason")
            ],
        },
        "hsw_st": {
            "watermark_id": audit_trace.get("watermark_id"),
            "audit_hash": audit_trace.get("audit_hash"),
            "audit_complete": audit_trace.get("audit_complete", False),
        },
        "cg": {
            "pre_check": cg_pre_check,
            "profile_update_decision": profile_update,
            "compliance_state": compliance_state,
            "compliance_policy": compliance_policy,
            "compliance_audit_log": compliance_audit_log[-8:],
        },
        "nemo_guardrails": {
            "enabled": runtime_status.get("nemo_guardrails_enabled", False),
            "backend": runtime_status.get("guardrail_backend", "disabled"),
        },
    }


def _profile_card_id(context_card: dict[str, Any], demo_case: DemoCase) -> str:
    return str(
        context_card.get("context_card_id")
        or context_card.get("card_id")
        or f"card_{demo_case.task_id}"
    )


def _select_return_mode(copyright_level: float, allowed: list[str]) -> str:
    allowed_set = set(allowed or [])
    if copyright_level >= 0.7 and "variant" in allowed_set:
        return "variant"
    if copyright_level >= 0.45 and "summary" in allowed_set:
        return "summary"
    if "snippet" in allowed_set:
        return "snippet"
    return (allowed or ["summary"])[0]


def _controlled_content(
    *,
    knowledge_point: str,
    return_mode: str,
    teaching_request: dict[str, Any],
) -> str:
    strategy = teaching_request.get("suggested_teaching_strategy", "scaffold_then_variant")
    if return_mode == "variant":
        return (
            f"Controlled variant for {knowledge_point}: use the same concept with "
            "changed surface details, then ask the learner to explain the key step."
        )
    if return_mode == "snippet":
        return f"Short controlled cue for {knowledge_point}: identify the rule first."
    return (
        f"Controlled summary for {knowledge_point}: apply {strategy}, avoid full "
        "teacher resource reproduction, and keep the explanation task-focused."
    )


def _exposure_cost(return_mode: str, copyright_level: float) -> float:
    base = {
        "variant": 0.06,
        "summary": 0.1,
        "outline": 0.12,
        "snippet": 0.14,
        "quote": 0.2,
    }.get(return_mode, 0.1)
    return round(min(0.35, base + max(0.0, copyright_level - 0.5) * 0.08), 4)


def _demo_resource_source_trace(
    *,
    resource: dict[str, Any],
    content: str,
    return_mode: str,
    copyright_level: float,
    exposure_cost: float,
) -> dict[str, Any]:
    resource_id = str(resource.get("resource_id") or "teacher_resource_demo")
    chunk_id = str(resource.get("chunk_id") or "chunk_demo_001")
    license_policy = {
        "allow_quote": bool(resource.get("allow_quote", False)),
        "allow_summary": True,
        "allow_outline": True,
        "allow_variant": True,
        "max_quote_len": int(resource.get("max_quote_len", 24)),
        "max_exposure": float(resource.get("max_exposure", 0.6)),
    }
    controlled_hash = _sha256_json(content)
    quote_hash = (
        _sha256_json(
            {
                "resource_id": resource_id,
                "chunk_id": chunk_id,
                "return_mode": return_mode,
                "quoted_text": content,
            }
        )
        if return_mode in {"quote", "snippet"}
        else None
    )
    provenance_core = {
        "resource_id": resource_id,
        "chunk_id": chunk_id,
        "return_mode": return_mode,
        "copyright_level": copyright_level,
        "exposure_after": exposure_cost,
        "license_policy": license_policy,
        "quote_span_hash": quote_hash,
        "controlled_output_hash": controlled_hash,
    }
    policy_reason = (
        "high_copyright_or_reconstruction_risk_variant"
        if return_mode == "variant"
        else "controlled_summary_or_snippet_with_resource_trace"
    )
    commitment = _sha256_json(provenance_core)
    return {
        "trace_scope": "resource_level_provenance",
        "trace_owner": "C2-RAG",
        "watermark_boundary": "generation_watermarking_is_owned_by_HSW-ST",
        "source_trace_id": f"trace_{commitment[:12]}",
        "resource_id": resource_id,
        "chunk_id": chunk_id,
        "return_mode": return_mode,
        "copyright_level": copyright_level,
        "source_type": str(resource.get("source_type") or "teacher_resource_repository"),
        "license_type": str(resource.get("license_type") or "course_limited_license"),
        "license_policy": license_policy,
        "policy_reason": policy_reason,
        "decision_factors": {
            "copyright_level": copyright_level,
            "exposure_cost": exposure_cost,
            "allowed_modes": ["summary", "outline", "snippet", "variant"],
        },
        "retrieval_trace": [
            {
                "rank": 1,
                "resource_id": resource_id,
                "chunk_id": chunk_id,
                "score": 1.0,
                "components": {
                    "demo_case_match": 1.0,
                    "copyright_level": copyright_level,
                },
            }
        ],
        "quote_span_hash": quote_hash,
        "controlled_output_hash": controlled_hash,
        "resource_provenance_commitment": commitment,
        "exposure_before": 0.0,
        "exposure_after": exposure_cost,
        "timestamp": _utc_now(),
    }


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _summarize(value: Any, limit: int = 480) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value)
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= limit:
        return value
    return f"{text[: limit - 3]}..."


def _emit(event_sink: EventSink | None, event: dict[str, Any]) -> None:
    if event_sink is None:
        return
    event.setdefault("timestamp", _utc_now())
    event_sink(event)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-index", type=int, default=0)
    parser.add_argument("--episode-id", default=None)
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    result = run_demo(
        data_root=args.data_root,
        case_index=args.case_index,
        episode_id=args.episode_id,
    )
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
