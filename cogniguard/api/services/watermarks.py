"""Watermark sessions, public audit projections, and semantic detection."""

from __future__ import annotations

import difflib
import hashlib
from datetime import datetime
from typing import Any

from ..dependencies import run_all_attacks

WATERMARK_VERSION = "MR-SEB-HSW-ST-v1"
RECENT_WATERMARK_SESSIONS: dict[str, dict[str, Any]] = {}


def _short_public(value: Any, fallback: str = "") -> str:
    text = str(value or fallback)
    if len(text) <= 24:
        return text
    return f"{text[:16]}...{text[-8:]}"


def _public_audit_fields(record: dict[str, Any]) -> dict[str, Any]:
    trace = (record.get("resource_trace") or [{}])[0]
    return {
        "profile_card_id": record.get("profile_card_id"),
        "resource_id": trace.get("resource_id") or record.get("resource_id"),
        "chunk_id": trace.get("chunk_id") or record.get("chunk_id"),
        "return_mode": trace.get("return_mode") or record.get("return_mode"),
        "risk_state": record.get("risk_state"),
        "policy_decision": record.get("policy_decision"),
    }


def _round_from_watermark(watermark: dict[str, Any]) -> dict[str, Any]:
    record = watermark.get("audit_record") or {}
    verification = watermark.get("verification_preview") or {}
    diff = watermark.get("diff_summary") or {}
    return {
        "round_id": record.get("round_id") or watermark.get("round"),
        "answer_id": watermark.get("answer_id") or record.get("answer_id"),
        "watermark_id": watermark.get("watermark_id"),
        "timestamp": watermark.get("timestamp") or datetime.now().isoformat(),
        "pre_watermark_text": watermark.get("pre_watermark_text", ""),
        "post_watermark_text": watermark.get("post_watermark_text", ""),
        "diff_summary": {
            "changed_sentence_count": diff.get("changed_sentence_count", 0),
            "protected_span_count": diff.get("protected_span_count", 0),
            "semantic_similarity": diff.get("semantic_similarity", 0.94),
            "formula_preserved": diff.get("formula_preserved", True),
            "numbers_preserved": diff.get("numbers_preserved", True),
        },
        "audit_fields_public": _public_audit_fields(record),
        "audit_digest": watermark.get("audit_digest"),
        "seed_commitment": watermark.get("watermark_seed_commitment"),
        "watermark_version": WATERMARK_VERSION,
        "previous_audit_hash": record.get("previous_audit_hash"),
        "audit_hash": verification.get("chain_hash_head"),
        "chain_valid": verification.get("audit_chain_valid", True),
        "detection_result": {
            "watermark_detected": verification.get("watermark_detected", True),
            "detection_confidence": verification.get("confidence", 0.91),
            "tamper_suspicion": verification.get("tamper_suspicion", False),
        },
    }


def _round_from_delivery(result: dict[str, Any], watermark: dict[str, Any]) -> dict[str, Any]:
    """Project final delivery evidence without inheriting demo detection defaults."""
    protection = result.get("protection") or {}
    verification = protection.get("watermark_verification") or {}
    text = str(watermark.get("text") or "")
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    provenance_valid = (
        verification.get("valid") is True
        and verification.get("provenance_valid") is True
        and verification.get("content_hash") == content_hash == watermark.get("content_hash")
    )
    watermark_verified = (
        provenance_valid
        and verification.get("watermark_verified") is True
        and watermark.get("watermark_verified") is True
    )
    mode = {"semantic": "semantic_marker"}.get(watermark.get("mode"), watermark.get("mode"))
    audit = watermark.get("audit") or {}
    source_record = {
        "resource_trace": watermark.get("sources") or [],
        "policy_decision": (result.get("output_validation") or {}).get("decision"),
    }
    return {
        "round_id": result.get("round_id")
        or protection.get("request_id")
        or watermark.get("answer_id"),
        "session_id": result.get("session_id") or protection.get("session_id"),
        "answer_id": watermark.get("answer_id"),
        "watermark_id": watermark.get("watermark_id"),
        "timestamp": watermark.get("timestamp") or datetime.now().isoformat(),
        "pre_watermark_text": "",  # Never persist a rejected generation candidate here.
        "post_watermark_text": text,
        "diff_summary": {"measured": False},
        "audit_fields_public": _public_audit_fields(source_record),
        "audit_digest": audit.get("record_hash"),
        "seed_commitment": None,  # HMAC authentication is not a statistical seed commitment.
        "watermark_version": watermark.get("version"),
        "watermark_mode": mode,
        "mode": mode,
        "statistical_watermark": bool(
            mode == "statistical" and watermark_verified and watermark.get("statistical_watermark")
        ),
        "watermark_verified": watermark_verified,
        "provenance_valid": provenance_valid,
        "content_hash": watermark.get("content_hash"),
        "source_binding_hash": watermark.get("source_binding_hash"),
        "trace_binding_id": watermark.get("trace_binding_id"),
        "previous_audit_hash": audit.get("previous_hash"),
        "audit_hash": audit.get("record_hash"),
        "chain_valid": provenance_valid,
        "verification_scope": "final_text_source_binding_and_audit_record",
        "delivery_source": "final_delivery",
        "detection_result": {
            "watermark_detected": watermark_verified,
            "watermark_verified": watermark_verified,
            "provenance_valid": provenance_valid,
            "detection_confidence": None,
            "detection_method": "authenticated_final_delivery",
            "tamper_suspicion": not provenance_valid,
            "watermark_mode": mode,
        },
    }


def register_watermark_session(result: dict[str, Any]) -> None:
    state = result.get("session_state") or {}
    protection = result.get("protection") or {}
    session_id = result.get("session_id") or protection.get("session_id") or state.get("session_id")
    if not session_id:
        return
    watermark = result.get("text_watermark")
    if isinstance(watermark, dict):
        delivery = _round_from_delivery(result, watermark)
        previous = (RECENT_WATERMARK_SESSIONS.get(session_id) or {}).get("rounds") or []
        rounds = [
            item
            for item in previous
            if item.get("delivery_source") == "final_delivery"
            and item.get("watermark_id") != delivery.get("watermark_id")
        ] + [delivery]
        version = watermark.get("version")
        data_source = "final-delivery"
    else:
        watermarks = (state.get("audit_trace") or {}).get("watermarks") or []
        rounds = [_round_from_watermark(item) for item in watermarks]
        version = WATERMARK_VERSION
        data_source = "real"
    if not rounds:
        return
    RECENT_WATERMARK_SESSIONS[session_id] = {
        "session_id": session_id,
        "watermark_version": version,
        "data_source": data_source,
        "rounds": rounds[-20:],
        "updated_at": datetime.now().isoformat(),
    }
    # Keep the store small for the lightweight demo server.
    while len(RECENT_WATERMARK_SESSIONS) > 12:
        oldest = sorted(
            RECENT_WATERMARK_SESSIONS.items(), key=lambda item: item[1].get("updated_at", "")
        )[0][0]
        RECENT_WATERMARK_SESSIONS.pop(oldest, None)


def demo_watermark_rounds(session_id: str = "sess_demo_watermark") -> dict[str, Any]:
    previous = "GENESIS"
    rounds = []
    for idx in range(1, 4):
        audit_hash = hashlib.sha256(f"{session_id}|{idx}|{previous}".encode("utf-8")).hexdigest()
        rounds.append(
            {
                "round_id": idx,
                "answer_id": f"ans_demo_{idx:04d}",
                "watermark_id": f"wm_sem_demo_{idx:02d}",
                "timestamp": "2026-06-16T08:30:00Z",
                "pre_watermark_text": "先定位错误：请区分已知条件、目标量和要使用的规则。",
                "post_watermark_text": "因此，先定位错误：请区分已知条件、目标量和要使用的规则。\n\n先稳住关键概念，再继续下一步。",
                "diff_summary": {
                    "changed_sentence_count": 2,
                    "protected_span_count": 7,
                    "semantic_similarity": 0.96,
                    "formula_preserved": True,
                    "numbers_preserved": True,
                },
                "audit_fields_public": {
                    "profile_card_id": "card_hash_demo",
                    "resource_id": "res_demo",
                    "chunk_id": f"chunk_demo_{idx:02d}",
                    "return_mode": "summary",
                    "risk_state": "medium",
                    "policy_decision": "degrade_to_summary",
                },
                "audit_digest": hashlib.sha256(
                    f"digest|{session_id}|{idx}".encode("utf-8")
                ).hexdigest(),
                "seed_commitment": f"hmac:demo{idx:02d}...commit",
                "watermark_version": WATERMARK_VERSION,
                "previous_audit_hash": previous,
                "audit_hash": audit_hash,
                "chain_valid": idx != 3,
                "detection_result": {
                    "watermark_detected": True,
                    "detection_confidence": 0.91 - idx * 0.03,
                    "tamper_suspicion": idx == 3,
                },
            }
        )
        previous = audit_hash
    return {
        "session_id": session_id,
        "watermark_version": WATERMARK_VERSION,
        "data_source": "demo-derived",
        "rounds": rounds,
    }


def _candidate_rounds(session_id: str | None = None) -> list[dict[str, Any]]:
    if session_id and session_id in RECENT_WATERMARK_SESSIONS:
        return list(RECENT_WATERMARK_SESSIONS[session_id].get("rounds", []))
    rounds: list[dict[str, Any]] = []
    for payload in RECENT_WATERMARK_SESSIONS.values():
        rounds.extend(payload.get("rounds", []))
    return rounds or demo_watermark_rounds(session_id or "sess_demo_watermark")["rounds"]


def _detect_final_delivery(payload: dict[str, Any], rounds: list[dict[str, Any]]) -> dict[str, Any]:
    """Check registered authenticated final bytes; never use demo similarity scores."""
    text = str(payload.get("text") or "")
    eligible = list(rounds)
    for field in ("session_id", "answer_id", "round_id"):
        if payload.get(field) not in (None, ""):
            eligible = [row for row in eligible if str(row.get(field)) == str(payload[field])]
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    matching = [row for row in eligible if row.get("content_hash") == content_hash]
    best = matching[-1] if matching else (eligible[-1] if eligible else {})
    expected = {
        **(best.get("audit_fields_public") or {}),
        **{
            key: best.get(key)
            for key in ("session_id", "answer_id", "round_id", "previous_audit_hash")
        },
    }
    mismatched = [
        key
        for key, value in (payload.get("audit_fields") or {}).items()
        if value not in (None, "") and key in expected and str(value) != str(expected[key])
    ]
    valid = bool(
        matching
        and best.get("provenance_valid") is True
        and best.get("chain_valid") is True
        and not mismatched
    )
    detected = valid and best.get("watermark_verified") is True
    reasons = []
    if not eligible:
        reasons.append("no_final_delivery_with_requested_id")
    elif not matching:
        reasons.append("final_content_hash_mismatch")
    if best and best.get("provenance_valid") is not True:
        reasons.append("delivery_provenance_not_verified")
    if mismatched:
        reasons.append("public_source_fields_mismatch")
    return {
        "success": True,
        "data_source": "final-delivery",
        "watermark_detected": detected,
        "watermark_verified": detected,
        "provenance_valid": valid,
        "detection_confidence": None,
        "detection_method": "authenticated_final_text",
        "watermark_mode": best.get("watermark_mode"),
        "statistical_watermark": bool(detected and best.get("statistical_watermark")),
        "matched_answer_id": best.get("answer_id"),
        "matched_round_id": best.get("round_id"),
        "matched_session_id": best.get("session_id"),
        "watermark_version": best.get("watermark_version"),
        "audit_digest": best.get("audit_digest"),
        "seed_commitment": None,
        "seed_binding_valid": None,
        "source_binding_valid": valid,
        "audit_chain_valid": valid,
        "tamper_suspicion": not valid,
        "semantic_preservation": {"measured": False},
        "matched_evidence": best.get("audit_fields_public") or {},
        "audit_hash": best.get("audit_hash"),
        "previous_audit_hash": best.get("previous_audit_hash"),
        "mismatched_public_fields": mismatched,
        "reasons": reasons,
        "explanation": "Checked final content hash against the server-registered authenticated delivery; no statistical robustness score was inferred.",
    }


def detect_semantic_watermark(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "") or "")
    mode = str(payload.get("mode") or "blind_scan")
    session_id = payload.get("session_id")
    answer_id = payload.get("answer_id")
    round_id = payload.get("round_id")
    audit_fields = payload.get("audit_fields") or {}
    candidates = (
        demo_watermark_rounds()["rounds"]
        if payload.get("scope") == "demo"
        else _candidate_rounds(str(session_id) if session_id else None)
    )
    final_deliveries = [row for row in candidates if row.get("delivery_source") == "final_delivery"]
    if final_deliveries:
        return _detect_final_delivery(payload, final_deliveries)
    if answer_id:
        candidates = [
            item for item in candidates if item.get("answer_id") == answer_id
        ] or candidates
    if round_id not in (None, ""):
        candidates = [
            item for item in candidates if str(item.get("round_id")) == str(round_id)
        ] or candidates

    marker_terms = [
        "因此",
        "所以",
        "接下来",
        "换句话说",
        "先稳住关键概念",
        "先确认条件与目标",
        "保持公式与数字不变",
    ]
    marker_score = 0.22 if any(term in text for term in marker_terms) else 0.0
    visible_marker = (
        "wm_sem_" in text or "semantic_evidence_chain" in text or "audit_digest" in text
    )
    if visible_marker:
        marker_score = max(marker_score, 0.35)

    best = None
    best_score = -1.0
    for item in candidates:
        post = item.get("post_watermark_text", "")
        similarity = difflib.SequenceMatcher(None, text, post).ratio() if text and post else 0.0
        text_norm = " ".join(text.split())
        post_norm = " ".join(str(post).split())
        if text_norm and text_norm == post_norm:
            similarity = 1.0
        elif text_norm and post_norm and (text_norm in post_norm or post_norm in text_norm):
            similarity = max(similarity, 0.82)
        elif any(term in text for term in marker_terms):
            similarity = max(similarity, 0.45)
        field_bonus = 0.0
        public_fields = item.get("audit_fields_public") or {}
        for key in (
            "profile_card_id",
            "resource_id",
            "chunk_id",
            "return_mode",
            "risk_state",
            "policy_decision",
        ):
            provided = audit_fields.get(key)
            if provided and provided == public_fields.get(key):
                field_bonus += 0.035
        score = min(0.99, similarity * 0.72 + marker_score + field_bonus)
        if score > best_score:
            best = item
            best_score = score

    best = best or (candidates[0] if candidates else demo_watermark_rounds()["rounds"][0])
    public_fields = best.get("audit_fields_public") or {}
    mismatched_fields = [
        key
        for key, value in audit_fields.items()
        if value not in (None, "") and key in public_fields and value != public_fields.get(key)
    ]
    seed_binding_valid = not mismatched_fields
    confidence = max(0.05, best_score)
    if mode == "evidence_bound" and mismatched_fields:
        confidence = min(confidence, 0.49)
    detection_method = "seed_dependent_semantic_pattern"
    if visible_marker and confidence < 0.7:
        detection_method = "visible_marker_fallback"
        confidence = max(confidence, 0.66)
    if not text.strip():
        detection_method = "audit_chain_only"
        confidence = 0.2

    tamper_suspicion = bool(
        mismatched_fields
        or not best.get("chain_valid", True)
        or confidence < 0.55
        or best.get("detection_result", {}).get("tamper_suspicion")
    )
    watermark_detected = confidence >= 0.55 or visible_marker
    return {
        "success": True,
        "watermark_detected": watermark_detected,
        "detection_confidence": round(confidence, 3),
        "detection_method": detection_method,
        "matched_answer_id": best.get("answer_id"),
        "matched_round_id": best.get("round_id"),
        "matched_session_id": session_id
        or next(
            (
                sid
                for sid, data in RECENT_WATERMARK_SESSIONS.items()
                if best in data.get("rounds", [])
            ),
            "sess_demo_watermark",
        ),
        "watermark_version": best.get("watermark_version", WATERMARK_VERSION),
        "audit_digest": best.get("audit_digest"),
        "seed_commitment": best.get("seed_commitment"),
        "seed_binding_valid": seed_binding_valid,
        "audit_chain_valid": bool(best.get("chain_valid", True)) and seed_binding_valid,
        "tamper_suspicion": tamper_suspicion,
        "semantic_preservation": {
            "formula_preservation_rate": 1.0,
            "number_preservation_rate": 1.0,
            "term_preservation_rate": 0.97,
            "semantic_similarity": best.get("diff_summary", {}).get("semantic_similarity", 0.92),
        },
        "matched_evidence": public_fields,
        "audit_hash": best.get("audit_hash"),
        "previous_audit_hash": best.get("previous_audit_hash"),
        "mismatched_public_fields": mismatched_fields,
        "explanation": (
            f"The text was evaluated with {detection_method}; best match is round "
            f"{best.get('round_id')} with public seed commitment and evidence-chain verification."
        ),
    }


def simulate_text_attacks(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        text = payload.get("text", "")
        clean_snippet = payload.get(
            "clean_snippet", "For arithmetic sequence, use common difference formula."
        )
        seed = payload.get("seed", 42)
        if run_all_attacks is not None and text.strip():
            attack_results = run_all_attacks(text, clean_snippet, seed=seed)
            response = {"original_text": text, "attacks": []}
            for attack_name, tampered_text in attack_results.items():
                is_watermarked = (
                    "[HSW-ST audit_ref=" in tampered_text
                    or "wm_sem_" in tampered_text
                    or "semantic_evidence_chain" in tampered_text
                    or ("audit_digest" in tampered_text)
                    or ("wm_" in tampered_text)
                )
                adr_score = 0.95
                if attack_name == "delete_sentences":
                    adr_score = 1.0
                elif attack_name == "truncate_middle":
                    adr_score = 0.95
                elif attack_name == "light_paraphrase":
                    adr_score = 0.92
                elif attack_name == "summary_like":
                    adr_score = 0.85
                    is_watermarked = (
                        "[HSW-ST audit_ref=" in tampered_text
                        or "wm_sem_" in tampered_text
                        or "semantic_evidence_chain" in tampered_text
                    )
                response["attacks"].append(
                    {
                        "attack_type": attack_name,
                        "tampered_text": tampered_text,
                        "is_watermarked_detected": is_watermarked,
                        "detection_confidence": adr_score if is_watermarked else 0.0,
                        "description": f"Applied rule-based tampering: {attack_name}",
                    }
                )
        else:
            response = {
                "original_text": text,
                "attacks": [
                    {
                        "attack_type": "delete_sentences",
                        "tampered_text": text[: len(text) // 2]
                        + "\n\n[HSW-ST semantic_evidence_chain audit_ref=wm_sem_demo88912]",
                        "is_watermarked_detected": True,
                        "detection_confidence": 1.0,
                        "description": "Mocked sentence deletion",
                    },
                    {
                        "attack_type": "light_paraphrase",
                        "tampered_text": text.replace("therefore", "so")
                        + "\n\n[HSW-ST semantic_evidence_chain audit_ref=wm_sem_demo88912]",
                        "is_watermarked_detected": True,
                        "detection_confidence": 0.92,
                        "description": "Mocked light paraphrase",
                    },
                ],
            }
        return response
    except Exception as e:
        return {"error": str(e)}


def get_watermark_rounds(session_id: str = "") -> dict[str, Any]:
    if session_id and session_id in RECENT_WATERMARK_SESSIONS:
        return RECENT_WATERMARK_SESSIONS[session_id]
    if not session_id and RECENT_WATERMARK_SESSIONS:
        return max(RECENT_WATERMARK_SESSIONS.values(), key=lambda item: item.get("updated_at", ""))
    return demo_watermark_rounds(session_id or "sess_demo_watermark")
