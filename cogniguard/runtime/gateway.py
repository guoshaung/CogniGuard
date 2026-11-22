"""Mandatory application boundary around CGC and the three domain protections."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Callable
from uuid import uuid4

from cogniguard.integrations.nemo.flow_guard import configured_colang_gates
from cogniguard.integrations.nemo.native import (
    NativeNeMoUnavailable,
    configured_native_guard,
    configured_semantic_guard,
)
from cogniguard.observability import (
    LangSmithMonitor,
    SafeTelemetry,
    active_recorder,
    request_observation,
)
from cogniguard.protection.cg.nemo_guardrails_adapter import (
    DOMAIN_REQUEST_POLICY_IDS,
    NeMoGuardrailsAdapter,
)
from cogniguard.protection.output_validation import (
    SAFE_OUTPUT_REPLACEMENT,
    OutputValidationResult,
    validate_output,
)
from cogniguard.protection.text_provenance import TextProvenanceService, WatermarkUnavailableError
from cogniguard.runtime.protection_context import (
    ProtectionContext,
    active_protection,
    protection_scope,
    publish_session_token,
    transport_credentials,
)
from cogniguard.runtime.sessions import InvalidSessionToken, SessionStore
from core.paths import CG_GUARDRAILS_DIR, RUNTIME_DIR


def _output_intercepted(result: dict) -> bool:
    # Cancel only when the whole answer was withheld. A nested field scrubbed to
    # "[受保护内容已移除]" still delivers the main answer. input_blocked and
    # semantic_output_blocked replace that answer with SAFE_OUTPUT_REPLACEMENT.
    # 不确定时按已交付记账，宁可高估泄露，不能低估。
    validation = result.get("output_validation")
    if not (isinstance(validation, dict) and validation.get("allowed") is True):
        return True
    if result.get("input_blocked") or result.get("semantic_output_blocked"):
        return True
    answer = result.get("answer")
    return isinstance(answer, str) and SAFE_OUTPUT_REPLACEMENT in answer


def _registered_receipt_ids(frame) -> tuple[object, list]:
    store = getattr(frame, "disclosure_store", None)
    receipt_ids = getattr(frame, "disclosure_receipt_ids", None)
    if store is None or not receipt_ids:
        return None, []
    return store, receipt_ids


def _commit_registered_disclosures(frame) -> None:
    store, receipt_ids = _registered_receipt_ids(frame)
    if store is None:
        return
    while receipt_ids:
        store.commit(receipt_ids[0])
        del receipt_ids[0]


def _cancel_registered_disclosures(frame) -> None:
    store, receipt_ids = _registered_receipt_ids(frame)
    if store is None:
        return
    while receipt_ids:
        store.cancel(receipt_ids[0])
        del receipt_ids[0]


def _signing_key() -> bytes:
    path = RUNTIME_DIR / "secrets" / "text-provenance.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix="key-", delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(secrets.token_bytes(32))
        try:
            # Publish complete bytes atomically, without replacing another process's key.
            os.link(temporary, path)
        except FileExistsError:
            pass
        finally:
            temporary.unlink()
    key = path.read_bytes()
    if len(key) < 32:
        raise WatermarkUnavailableError("Invalid server provenance signing key")
    return key


class ProtectionGateway:
    """Server-owned state and final delivery, independent of optional NeMo flags.

    Domain algorithms still authorize, minimize and measure their own releases.
    This boundary persists their costs, validates content, and signs delivery.
    """

    def __init__(
        self, store=None, provenance=None, adapter=None, native_guard=None, semantic_guard=None
    ):
        self.store = store or SessionStore(
            limits={
                "images": 2,
                "requests": 1000,
                "privacy": 2,
                "copyright": 1,
            }
        )
        self.provenance = provenance or TextProvenanceService(_signing_key(), required=True)
        self.adapter = adapter or NeMoGuardrailsAdapter(
            str(CG_GUARDRAILS_DIR), enabled=True
        )
        self.native_guard = native_guard if native_guard is not None else configured_native_guard()
        self.colang_gates = None
        try:
            self.semantic_guard = (
                semantic_guard if semantic_guard is not None else configured_semantic_guard()
            )
            if self.semantic_guard and not self.native_guard:
                self.semantic_guard.close()
                raise NativeNeMoUnavailable("Semantic guard requires native NeMo base guard")
            self.colang_gates = configured_colang_gates()
        except Exception:
            if getattr(self, "semantic_guard", None):
                self.semantic_guard.close()
            if self.native_guard:
                self.native_guard.close()
            raise

    def run(
        self,
        surface: str,
        payload: dict,
        operation: Callable[[ProtectionContext], dict],
        *,
        session_token: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        if active_recorder() is not None:
            return self._run(
                surface, payload, operation, session_token=session_token, request_id=request_id
            )
        recorder = SafeTelemetry()
        monitor = LangSmithMonitor.from_environment()
        try:
            with request_observation(recorder), recorder.span("gateway.request") as metrics:
                result = self._run(
                    surface, payload, operation, session_token=session_token, request_id=request_id
                )
                metrics["completed"] = True
                return result
        finally:
            # Observation is outside policy execution and never changes its result.
            try:
                monitor.export(recorder)
            except Exception:
                pass

    def _run(
        self,
        surface: str,
        payload: dict,
        operation: Callable[[ProtectionContext], dict],
        *,
        session_token: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        current = active_protection()
        if current is not None:
            if session_token is not None and not hmac.compare_digest(
                session_token, current.session.token
            ):
                raise InvalidSessionToken("Nested operation cannot change server sessions")
            return operation(current)
        transport_token, transport_request = transport_credentials()
        session = self.store.get_or_create(
            session_token if session_token is not None else transport_token
        )
        publish_session_token(session.token)
        request_id = request_id or transport_request or uuid4().hex
        canonical = json.dumps([surface, payload], sort_keys=True, ensure_ascii=False, default=str)
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        with session.request(request_id, fingerprint=fingerprint) as request:
            if request.cached:
                result = deepcopy(request.result)
                evidence = result.get("protection", {}).get("evidence", [])
                fixed_refusal = result.get("input_blocked") is True and any(
                    item.get("stage") == "input" and item.get("decision") == "block"
                    for item in evidence
                    if isinstance(item, dict)
                )
                if fixed_refusal:
                    verified = self.provenance.verify(
                        result.get("answer", ""), result.get("text_watermark", {})
                    )
                    if not verified.get("valid") or not verified.get("watermark_verified"):
                        raise WatermarkUnavailableError("Cached refusal provenance verification failed")
                text = str(payload.get("message") or payload.get("student_message") or "")
                cached_output = (
                    result.get("answer", "")
                    if fixed_refusal
                    else json.dumps(result, ensure_ascii=False, default=str)
                )
                if self.native_guard:
                    if (not fixed_refusal and not self.native_guard.check_input(text)) or not (
                        self.native_guard.check_output(cached_output)
                    ):
                        raise NativeNeMoUnavailable("Cached delivery failed native NeMo revalidation")
                if self.semantic_guard:
                    if (not fixed_refusal and not self.semantic_guard.check_input(text)) or not (
                        self.semantic_guard.check_output(cached_output)
                    ):
                        raise NativeNeMoUnavailable("Cached delivery failed semantic revalidation")
                if self.colang_gates and not fixed_refusal and not self.colang_gates.check("dialog", text):
                    raise NativeNeMoUnavailable("Cached delivery failed Colang dialog revalidation")
            else:
                with session.transaction() as state:
                    frame = ProtectionContext(session, request_id, surface, state, nemo_colang=self.colang_gates)
                    with protection_scope(frame):
                        try:
                            text = str(payload.get("message") or payload.get("student_message") or "")
                            recorder = active_recorder()
                            with recorder.span("gateway.input") as metrics:
                                nemo_allowed = (
                                    self.native_guard.check_input(text) if self.native_guard else True
                                )
                                semantic_allowed = (
                                    self.semantic_guard.check_input(text)
                                    if self.semantic_guard and nemo_allowed and text else nemo_allowed
                                )
                                dialog_allowed = (
                                    self.colang_gates.check("dialog", text)
                                    if self.colang_gates and semantic_allowed else semantic_allowed
                                )
                                check = (
                                    self.adapter.check_user_input(
                                        text,
                                        {"surface": surface, "policy_owner": "CGC"},
                                        _skip_policy_ids=DOMAIN_REQUEST_POLICY_IDS,
                                    )
                                    if dialog_allowed
                                    else {"decision": "block"}
                                )
                                metrics["blocked"] = check.get("decision") not in {"allow", "disabled"}
                            if self.native_guard:
                                frame.evidence.append(
                                    {"stage": "nemo_input", "decision": "allow" if nemo_allowed else "block"}
                                )
                            if self.semantic_guard and nemo_allowed and text:
                                frame.evidence.append(
                                    {"stage": "nemo_semantic_input", "decision":
                                     "allow" if semantic_allowed else "block"}
                                )
                            if self.colang_gates and semantic_allowed:
                                frame.evidence.append(
                                    {"stage": "nemo_dialog", "decision": "allow" if dialog_allowed else "block"}
                                )
                            frame.evidence.append(
                                {"stage": "input", "decision": check.get("decision"), "owner": "CGC"}
                            )
                            if check.get("decision") not in {"allow", "disabled"}:
                                result = {
                                    "success": True,
                                    "answer": SAFE_OUTPUT_REPLACEMENT,
                                    "input_blocked": True,
                                }
                            else:
                                with recorder.span("gateway.operation"):
                                    result = operation(frame)
                            with recorder.span("gateway.delivery") as metrics:
                                result = self._deliver(deepcopy(result), frame)
                                if self.semantic_guard:
                                    # A blocked input never reaches the operation. Its output is
                                    # the server-owned refusal plus trusted delivery metadata.
                                    # Review the watermarked refusal itself; including control
                                    # metadata can make a model misclassify a safe refusal.
                                    semantic_text = (
                                        result["answer"]
                                        if check.get("decision") not in {"allow", "disabled"}
                                        else json.dumps(result, ensure_ascii=False, default=str)
                                    )
                                    if not self.semantic_guard.check_output(semantic_text):
                                        frame.evidence.append(
                                            {"stage": "nemo_semantic_output", "decision": "block"}
                                        )
                                        result = self._deliver(
                                            {"success": True, "answer": SAFE_OUTPUT_REPLACEMENT,
                                             "semantic_output_blocked": True}, frame
                                        )
                                        if not self.semantic_guard.check_output(
                                            json.dumps(result, ensure_ascii=False, default=str)
                                        ):
                                            raise NativeNeMoUnavailable(
                                                "Semantic replacement failed output check"
                                            )
                                    result["protection"]["evidence"].append(
                                        {"stage": "nemo_semantic_output", "decision": "allow"}
                                    )
                                metrics["watermark_verified"] = True
                                metrics["blocked"] = not result["output_validation"]["allowed"]
                            result["observability"] = {
                                "trace_id": recorder.run_id,
                                "content_policy": "metrics_only",
                            }
                            with recorder.span("gateway.finalize"):
                                self._save_dialogue(frame, payload, result)
                            deliveries = state.setdefault("final_deliveries", [])
                            deliveries.append(
                                {
                                    key: deepcopy(result[key])
                                    for key in (
                                        "session_id",
                                        "round_id",
                                        "text_watermark",
                                        "output_validation",
                                        "protection",
                                    )
                                    if key in result
                                }
                            )
                            state["final_deliveries"] = deliveries[-20:]
                            if _output_intercepted(result):
                                _cancel_registered_disclosures(frame)
                            else:
                                _commit_registered_disclosures(frame)
                        except Exception:
                            _cancel_registered_disclosures(frame)
                            raise
                request.complete(result)
        result["session_token"] = session.token
        return result

    def _validate(self, text, frame, claimed_source_ids=()):
        if self.native_guard and text and not self.native_guard.check_output(text):
            return OutputValidationResult(
                allowed=False,
                decision="block",
                text=SAFE_OUTPUT_REPLACEMENT,
                reasons=("nemo_base_output_blocked",),
            )
        return validate_output(
            text,
            private_values=frame.private_values,
            protected_resources=frame.protected_resources,
            approved_chunks=frame.approved_chunks,
            approved_source_ids=frame.approved_source_ids,
            claimed_source_ids=claimed_source_ids,
            guardrail_adapter=self.adapter,
        )

    def _deliver(self, result: dict, frame: ProtectionContext) -> dict:
        validation_cache = {}

        def validate(text, claimed_source_ids=()):
            key = (text, tuple(map(str, claimed_source_ids)))
            if key not in validation_cache:
                validation_cache[key] = self._validate(text, frame, claimed_source_ids)
            return validation_cache[key]

        answer_keys = (
            "answer",
            "teacher_answer",
            "final_protected_teaching_answer",
            "final_protected_answer",
        )
        candidate = next(
            (result[k] for k in answer_keys if isinstance(result.get(k), str) and result[k]), ""
        )
        if not candidate:
            candidate = next(
                (
                    str(m.get("content", ""))
                    for m in reversed(result.get("messages", []))
                    if m.get("role") in {"teacher", "assistant", "security"}
                ),
                "",
            )
        candidate = candidate or "本轮处理已完成，未生成可展示的教学文本。"
        claims = result.get("source_ids", result.get("claimed_source_ids", []))
        validation = validate(candidate, [claims] if isinstance(claims, str) else claims or [])
        record = self.provenance.bind(
            validation.text,
            answer_id=f"{frame.session.session_id}:{frame.request_id}",
            sources=frame.approved_chunks,
        )
        after = validate(record["text"])
        if not after.allowed:
            validation = after
            record = self.provenance.bind(
                SAFE_OUTPUT_REPLACEMENT, answer_id=f"{frame.request_id}:refused"
            )
            if not validate(record["text"]).allowed:
                raise WatermarkUnavailableError("Final replacement failed output validation")
        verification = self.provenance.verify(record["text"], record)
        if not verification.get("valid") or not verification.get("watermark_verified"):
            raise WatermarkUnavailableError("Final delivery provenance verification failed")

        def metadata_allowed(value):
            if isinstance(value, str):
                return validate(value).allowed
            if isinstance(value, list):
                return all(metadata_allowed(item) for item in value)
            if isinstance(value, dict):
                return all(
                    metadata_allowed(str(key)) and metadata_allowed(item)
                    for key, item in value.items()
                )
            return True

        if not metadata_allowed(record):
            # Signed metadata is also a release: never redact an existing signature.
            raise WatermarkUnavailableError("Final provenance metadata failed content validation")

        # Diagnostics and model transcripts share the same release boundary.
        # Never serialize a forbidden answer through an alternate nested field.
        def scrub(value):
            if isinstance(value, str):
                if value == candidate:
                    return record["text"]
                return value if validate(value).allowed else "[受保护内容已移除]"
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, dict):
                cleaned = {}
                for key, item in value.items():
                    if key == "session_token" or not validate(str(key)).allowed:
                        continue
                    if key in {"source_id", "resource_id", "chunk_id"}:
                        cleaned[key] = (
                            item if str(item) in frame.approved_source_ids else "[未批准来源]"
                        )
                    elif key in {"source_ids", "claimed_source_ids"}:
                        ids = [item] if isinstance(item, str) else item
                        cleaned[key] = (
                            [sid for sid in ids if str(sid) in frame.approved_source_ids]
                            if isinstance(ids, list)
                            else []
                        )
                    else:
                        cleaned[key] = scrub(item)
                return cleaned
            return value

        result = scrub(result)
        result["answer"] = record["text"]
        for key in answer_keys[1:]:
            if key in result:
                result[key] = record["text"]
        for message in result.get("messages", []):
            if message.get("role") in {"teacher", "assistant"}:
                message["content"] = record["text"]
        result["output_validation"] = {
            **validation.to_dict(),
            "delivered_content_hash": record["content_hash"],
            "post_watermark_validated": True,
        }
        result["text_watermark"] = record
        result["session_id"] = frame.session.session_id
        result["protection"] = {
            "session_id": frame.session.session_id,
            "request_id": frame.request_id,
            "policy_owner": "CGC",
            "rails": ["input", "retrieval", "dialog", "execution", "output"],
            "colang_executed": False,
            "nemo_base_backend": "iorails" if self.native_guard else "disabled",
            "nemo_semantic_backend": "local_self_check" if self.semantic_guard else "disabled",
            "evidence": scrub(frame.evidence),
            "budgets": frame.session.budget_snapshot(),
            "watermark_verification": verification,
        }
        return result

    def _save_dialogue(self, frame, payload, result):
        if frame.surface == "free_chat" and not result.get("input_blocked"):
            history = frame.state.setdefault("history", [])
            history.extend(
                [
                    {"role": "user", "content": str(payload.get("message", ""))},
                    {"role": "assistant", "content": result["answer"]},
                ]
            )
            frame.state["history"] = history[-20:]
        elif frame.surface == "classroom" and isinstance(result.get("session_state"), dict):
            frame.state["classroom"] = deepcopy(result["session_state"])
            frame.state["classroom"]["round_number"] = int(
                result.get("round_number", frame.state["classroom"].get("round_number", 0))
            )


_gateway = None
_gateway_lock = RLock()


def get_gateway() -> ProtectionGateway:
    global _gateway
    with _gateway_lock:
        if _gateway is None:
            _gateway = ProtectionGateway()
        return _gateway
