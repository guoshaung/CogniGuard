"""Runtime-local origin/integrity chain, not a semantic trust classifier.

Keys are per run and never enter prompts, graph state, or serialized artifacts.
This protects the harness boundary, not a compromised signing runtime/host.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import asdict, dataclass
from threading import RLock
from uuid import uuid4

from .catalog import DATA_LABELS


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TeacherMessage:
    run_id: str
    graph_hash: str
    source: str
    message_id: str
    prompt_hash: str
    parent_ids: tuple[str, ...]
    hop: int
    lineage_valid: bool
    data_labels: tuple[str, ...]
    text: str
    signature: str

    def signed_body(self):
        body = asdict(self)
        body.pop("signature")
        body["text"] = text_hash(self.text)
        return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class MessageView:
    source: str
    message_id: str
    text: str
    received_content_hash: str
    delivered_content_hash: str
    origin_valid: bool
    chain_valid: bool
    data_labels: tuple[str, ...]
    boundary: str = "untrusted_data"
    instruction_permission: bool = False


class TrustChain:
    def __init__(self, run_id, team, *, mode="enforce"):
        if mode not in {"enforce", "observe_only"}:
            raise ValueError("Unknown trust-chain mode")
        self.run_id, self.team, self.mode = run_id, team, mode
        self._key = secrets.token_bytes(32)
        self._seen = set()
        self._lock = RLock()

    def issue(
        self, source, prompt_hash, text, parents=(), *, lineage_valid=True, data_labels=("task",)
    ):
        message = TeacherMessage(
            self.run_id,
            self.team.sha256,
            source,
            str(uuid4()),
            prompt_hash,
            tuple(p.message_id for p in parents),
            1 + max((p.hop for p in parents), default=-1),
            lineage_valid,
            tuple(sorted(data_labels)),
            text,
            "",
        )
        from dataclasses import replace

        signature = hmac.new(self._key, message.signed_body(), hashlib.sha256).hexdigest()
        return replace(message, signature=signature)

    def admit(self, message, edge, *, expected_prompt_hash):
        with self._lock:
            reasons = []
            well_formed = (
                isinstance(message, TeacherMessage)
                and all(
                    isinstance(getattr(message, k), str)
                    for k in (
                        "run_id",
                        "graph_hash",
                        "source",
                        "message_id",
                        "prompt_hash",
                        "text",
                        "signature",
                    )
                )
                and isinstance(message.parent_ids, tuple)
                and all(isinstance(p, str) for p in message.parent_ids)
                and isinstance(message.data_labels, tuple)
                and all(isinstance(k, str) for k in message.data_labels)
                and not (set(message.data_labels) - DATA_LABELS)
                and type(message.hop) is int
                and 0 <= message.hop <= len(self.team.nodes)
                and type(message.lineage_valid) is bool
                and len(message.text) <= 12000
                and bool(re.fullmatch(r"[0-9a-f]{64}", message.signature))
            )
            if not well_formed:
                return None, {
                    "source": edge.source,
                    "target": edge.target,
                    "accepted": False,
                    "origin_valid": False,
                    "chain_valid": False,
                    "reasons": ["malformed_message"],
                    "boundary": "untrusted_data",
                    "instruction_permission": False,
                    "delivered_chars": 0,
                }
            configured = next(
                (e for e in self.team.edges if (e.source, e.target) == (edge.source, edge.target)),
                None,
            )
            allowed = configured is not None
            if not allowed:
                reasons.append("edge_not_authorized")
            if configured is not None and edge != configured:
                reasons.append("edge_policy_mismatch")
            if message.run_id != self.run_id:
                reasons.append("cross_run_replay")
            if message.graph_hash != self.team.sha256:
                reasons.append("graph_binding_invalid")
            if message.source != edge.source:
                reasons.append("sender_mismatch")
            if message.prompt_hash != expected_prompt_hash:
                reasons.append("prompt_binding_invalid")
            expected = hmac.new(self._key, message.signed_body(), hashlib.sha256).hexdigest()
            signature_valid = hmac.compare_digest(message.signature, expected)
            if not signature_valid:
                reasons.append("signature_invalid")
            origin_valid = not any(
                r in reasons
                for r in (
                    "cross_run_replay",
                    "graph_binding_invalid",
                    "sender_mismatch",
                    "prompt_binding_invalid",
                    "signature_invalid",
                )
            )
            target = next((n for n in self.team.nodes if n.id == edge.target), None)
            scope_allowed = (
                configured is not None
                and target is not None
                and set(message.data_labels)
                <= (set(configured.allowed_labels) & set(target.upstream_labels))
            )
            if not scope_allowed:
                reasons.append("data_scope_denied")
            if not message.lineage_valid:
                reasons.append("invalid_ancestor")
            delivery_id = message.message_id, edge.target
            if delivery_id in self._seen:
                reasons.append("duplicate_delivery")
            valid = not reasons
            accepted = valid or (self.mode == "observe_only" and allowed)
            if accepted:
                self._seen.add(delivery_id)
            delivered = message.text[: configured.max_chars] if accepted else ""
            record = {
                "source": edge.source,
                "target": edge.target,
                "message_id": message.message_id,
                "accepted": accepted,
                "origin_valid": origin_valid,
                "chain_valid": valid,
                "signature_valid": signature_valid,
                "scope_allowed": scope_allowed,
                "data_labels": list(message.data_labels),
                "reasons": reasons,
                "boundary": "untrusted_data",
                "instruction_permission": False,
                "source_content_hash": text_hash(message.text),
                "delivered_content_hash": text_hash(delivered),
                "source_chars": len(message.text),
                "delivered_chars": len(delivered),
                "truncated": accepted and len(delivered) < len(message.text),
                "parent_ids": list(message.parent_ids),
                "hop": message.hop,
            }
            view = (
                MessageView(
                    message.source,
                    message.message_id,
                    delivered,
                    text_hash(message.text),
                    text_hash(delivered),
                    origin_valid,
                    valid,
                    message.data_labels,
                )
                if accepted
                else None
            )
            return view, record
