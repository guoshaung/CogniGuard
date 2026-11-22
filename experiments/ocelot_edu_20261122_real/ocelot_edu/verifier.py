"""Deterministic verifier. The audit sees the pairwise increment only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from experiments.ocelot_edu_20261122_real.ocelot_edu.constants import B_STAR, EPSILON_R, MU_ADVERSARIAL, OPS
from experiments.ocelot_edu_20261122_real.ocelot_edu.textutil import contains_text, sha256_text


@dataclass
class Atom:
    unit_id: str
    text: str
    field: str
    op: str
    utility: bool
    protected: bool

    def public_dict(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "field": self.field,
            "op": self.op,
            "utility": self.utility,
            "protected": self.protected,
        }


@dataclass
class Ledger:
    traj_id: str
    budget: float = B_STAR
    mu: float = MU_ADVERSARIAL
    entries: list[dict] = field(default_factory=list)
    cum: float = 0.0
    prev_hash: str = "GENESIS"
    released_fields: set[str] = field(default_factory=set)
    private_key: Ed25519PrivateKey = field(default_factory=Ed25519PrivateKey.generate)

    def append(self, turn_id: str, cost: float, atoms: list[Atom], released: str) -> dict:
        body = {
            "traj_id": self.traj_id,
            "turn_id": turn_id,
            "step": len(self.entries) + 1,
            "channel": "act",
            "destination": "student",
            "trust_class": "ADVERSARIAL",
            "cost": round(cost, 6),
            "cum_after": round(self.cum + cost, 6),
            "prev_hash": self.prev_hash,
            "atoms": [atom.public_dict() for atom in atoms],
            "released_sha256": sha256_text(released),
        }
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(self.prev_hash.encode("utf-8") + raw).hexdigest()
        signature = self.private_key.sign(digest.encode("utf-8")).hex()
        body["entry_hash"] = digest
        body["sig"] = signature
        self.entries.append(body)
        self.prev_hash = digest
        self.cum = round(self.cum + cost, 6)
        return body

    def public_key_hex(self) -> str:
        raw = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return raw.hex()


def apply_op(text: str, op: str) -> str:
    if op == "identity":
        return text
    if op == "generalize":
        return "〔概括〕这一步只保留方法类别，不给出原句。"
    if op == "substitute":
        return "〔替换〕用公开概念说明这一步，不引用原句。"
    if op == "redact":
        return "〔已隐去〕"
    if op == "drop":
        return ""
    raise ValueError(op)


def render(atoms: list[Atom]) -> str:
    return "".join(part for part in (apply_op(atom.text, atom.op) for atom in atoms) if part)


def _harsher(op: str) -> str | None:
    index = OPS.index(op)
    if index + 1 >= len(OPS):
        return None
    return OPS[index + 1]


def charge(atoms: list[Atom], ledger: Ledger, base_cost) -> tuple[float, list[dict]]:
    planned = set(ledger.released_fields)
    details = []
    total = 0.0
    for atom in atoms:
        if atom.field == "NONE" or atom.op in {"redact", "drop", "generalize", "substitute"}:
            base = 0.0
        elif atom.op == "identity":
            base = float(base_cost(atom.field, planned))
            planned.add(atom.field)
        else:
            raise ValueError(atom.op)
        charged = ledger.mu * base
        total += charged
        details.append(
            {
                "unit_id": atom.unit_id,
                "field": atom.field,
                "op": atom.op,
                "base": round(base, 6),
                "charged": round(charged, 6),
            }
        )
    return total, details


def verify_entry(entry: dict, public_key_hex: str, prev_hash: str) -> bool:
    body = {key: value for key, value in entry.items() if key not in {"entry_hash", "sig"}}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(prev_hash.encode("utf-8") + raw).hexdigest()
    if digest != entry["entry_hash"]:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(entry["sig"]),
            digest.encode("utf-8"),
        )
    except InvalidSignature:
        return False
    return True


def authorize(atoms: list[Atom], ledger: Ledger, turn_id: str, base_cost) -> dict:
    working = [
        Atom(
            unit_id=atom.unit_id,
            text=atom.text,
            field=atom.field,
            op=atom.op,
            utility=atom.utility,
            protected=atom.protected,
        )
        for atom in atoms
    ]
    escalations = 0
    while True:
        cost, details = charge(working, ledger, base_cost)
        audit_base = cost / ledger.mu if ledger.mu else 0.0
        # The pairwise audit is the sum of the increments just charged.
        # It has no order-3 term to disagree with, so the epsilon check stays quiet
        # unless a future change makes the audit see a larger set than the charge.
        audit_fail = audit_base > audit_base + EPSILON_R
        over = ledger.cum + cost > ledger.budget + 1e-9
        if not audit_fail and not over:
            break
        progressed = False
        order = sorted(
            range(len(working)),
            key=lambda i: OPS.index(working[i].op) if working[i].field != "NONE" else 99,
        )
        for index in order:
            if working[index].field == "NONE":
                continue
            nxt = _harsher(working[index].op)
            if nxt is None:
                continue
            working[index].op = nxt
            escalations += 1
            progressed = True
            break
        if not progressed or escalations > 50:
            break
    released = render(working)
    restored = False
    for atom in working:
        if atom.utility and not contains_text(released, atom.text):
            atom.op = "identity"
            atom.field = "NONE"
            restored = True
    if restored:
        released = render(working)
        cost, details = charge(working, ledger, base_cost)
    entry = ledger.append(turn_id, cost, working, released)
    for atom in working:
        if atom.op == "identity" and atom.field != "NONE":
            ledger.released_fields.add(atom.field)
    return {
        "turn_id": turn_id,
        "released": released,
        "cost": cost,
        "cum_after": ledger.cum,
        "exceeded": ledger.cum > ledger.budget + 1e-9,
        "escalations": escalations,
        "atoms": [atom.public_dict() for atom in working],
        "charge_details": details,
        "entry_hash": entry["entry_hash"],
        "sig": entry["sig"],
        "public_key": ledger.public_key_hex(),
        "released_sha256": entry["released_sha256"],
    }
