"""Deterministic WVD verifier for OCELOT-Edu.

Substitute relative to the paper: validation predicates are evaluated in
Python, not discharged with Z3. The ledger is a SHA-256 hash chain signed
with Ed25519. The Phase-3 audit uses the declared pairwise graph only;
it does not see undeclared order-3 or order-4 dependence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from experiments.ocelot_edu_20261121.ocelot_edu.assets import SCAFFOLD, Unit
from experiments.ocelot_edu_20261121.ocelot_edu.constants import (
    B_STAR,
    EPSILON_R,
    MU_ADVERSARIAL,
    OPS,
)


@dataclass
class Atom:
    span: str
    field: str  # unit_id or NONE
    kind: str  # direct | none
    necessity: str
    op: str
    marker: str | None = None
    protected: bool = False

    def as_dict(self) -> dict:
        return {
            "span": self.span,
            "field": self.field,
            "kind": self.kind,
            "necessity": self.necessity,
            "op": self.op,
            "marker": self.marker,
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
    # unit_id -> how many identity-charged fragments already committed
    released_counts: dict[str, int] = field(default_factory=dict)
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
            "atoms": [a.as_dict() for a in atoms],
            "released_sha256": hashlib.sha256(released.encode("utf-8")).hexdigest(),
        }
        raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(self.prev_hash.encode("utf-8") + raw).hexdigest()
        sig = self.private_key.sign(digest.encode("utf-8")).hex()
        body["entry_hash"] = digest
        body["sig"] = sig
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


def apply_op(span: str, op: str, marker: str | None) -> str:
    if op == "identity":
        return span
    if op == "generalize":
        return "〔概括〕这一步只保留方法类别，不给出讲义编号。"
    if op == "substitute":
        return "〔替换〕用公共概念说明这一步，不引用讲义原句。"
    if op == "redact":
        return "〔已隐去〕"
    if op == "drop":
        return ""
    raise ValueError(op)


def render(atoms: list[Atom]) -> str:
    parts = [apply_op(a.span, a.op, a.marker) for a in atoms]
    return "".join(p for p in parts if p)


def _harsher(op: str) -> str | None:
    i = OPS.index(op)
    if i + 1 >= len(OPS):
        return None
    return OPS[i + 1]


def charge(atoms: list[Atom], units: dict[str, Unit], ledger: Ledger) -> tuple[float, list[dict]]:
    """Pairwise incremental charge. Does not price undeclared higher-order sets."""
    planned = dict(ledger.released_counts)
    details = []
    total_base = 0.0
    for atom in atoms:
        if atom.field == "NONE" or atom.op in {"redact", "drop"}:
            base = 0.0
        else:
            unit = units[atom.field]
            n_after = planned.get(atom.field, 0) + (1 if atom.op == "identity" else 0)
            # generalize/substitute do not reveal the marker; count stays put
            if atom.op == "identity":
                base = unit.base_cost("identity", n_after)
                planned[atom.field] = n_after
            else:
                base = unit.base_cost(atom.op, planned.get(atom.field, 0))
        charged = ledger.mu * base
        total_base += base
        details.append({"marker": atom.marker, "field": atom.field, "op": atom.op, "base": base, "charged": charged})
    return ledger.mu * total_base, details


def pairwise_audit(atoms: list[Atom], units: dict[str, Unit], ledger: Ledger) -> float:
    """Audit on the declared pairwise graph. Equals the charged base sum.

    Order-3 and order-4 sequence secrets are invisible to this audit, matching
    Appendix C.1: only pre-registered pairs are jointly calibrated.
    """
    cost, _ = charge(atoms, units, ledger)
    return cost / ledger.mu if ledger.mu else 0.0


def authorize(
    atoms: list[Atom],
    units: dict[str, Unit],
    ledger: Ledger,
    turn_id: str,
) -> dict:
    working = [Atom(**{**a.as_dict()}) for a in atoms]
    # The paper's missing-label detector for structural fields is not published.
    # This verifier does not consult gold labels. A NONE field stays NONE and
    # costs 0, which is the free-text path in section 4.2. Unknown field names
    # are rejected by the prompt parser before they reach this function.
    escalations = 0
    while True:
        cost, details = charge(working, units, ledger)
        audit = pairwise_audit(working, units, ledger)
        audit_fail = audit > (cost / ledger.mu if ledger.mu else 0.0) + EPSILON_R
        over = ledger.cum + cost > ledger.budget + 1e-9
        if not audit_fail and not over:
            break
        progressed = False
        # Escalate the mildest non-NONE operator one step.
        order = sorted(
            range(len(working)),
            key=lambda i: OPS.index(working[i].op) if working[i].field != "NONE" else 99,
        )
        for i in order:
            if working[i].field == "NONE":
                continue
            nxt = _harsher(working[i].op)
            if nxt is None:
                continue
            working[i].op = nxt
            escalations += 1
            progressed = True
            break
        if not progressed:
            # DROP costs 0, so this is a bug if reached.
            cost, details = charge(working, units, ledger)
            break
        if escalations > 50:
            break
    released = render(working)
    # Utility predicate: the public scaffold must survive on every release that had it.
    had_scaffold = any(SCAFFOLD in a.span for a in atoms)
    utility_ok = (SCAFFOLD in released) if had_scaffold else True
    if had_scaffold and not utility_ok:
        # Put the scaffold back as NONE/identity. It carries no marker.
        for atom in working:
            if SCAFFOLD in atom.span:
                atom.op = "identity"
                atom.field = "NONE"
        released = render(working)
        cost, details = charge(working, units, ledger)
    entry = ledger.append(turn_id, cost, working, released)
    for atom in working:
        if atom.op == "identity" and atom.field not in {"NONE", "UNKNOWN-SENSITIVE"} and atom.marker:
            ledger.released_counts[atom.field] = ledger.released_counts.get(atom.field, 0) + 1
    return {
        "turn_id": turn_id,
        "released": released,
        "cost": cost,
        "cum_after": ledger.cum,
        "exceeded": ledger.cum > ledger.budget + 1e-9,
        "escalations": escalations,
        "atoms": [a.as_dict() for a in working],
        "charge_details": details,
        "entry_hash": entry["entry_hash"],
        "ledger_entry": entry,
        "utility_ok": SCAFFOLD in released if had_scaffold else True,
    }


def _body_without_auth(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in {"entry_hash", "sig"}}


def verify_stored_chain(entries: list[dict], public_key_hex: str) -> bool:
    """Check the hash link and the Ed25519 signature from persisted entries.

    The private key is not stored. Verification uses only the public key.
    """
    if not entries:
        return False
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    except ValueError:
        return False
    prev = "GENESIS"
    ordered = sorted(entries, key=lambda e: e.get("step", 0))
    for entry in ordered:
        if entry.get("prev_hash") != prev:
            return False
        raw = json.dumps(_body_without_auth(entry), ensure_ascii=False, sort_keys=True).encode("utf-8")
        digest = hashlib.sha256(prev.encode("utf-8") + raw).hexdigest()
        if digest != entry.get("entry_hash"):
            return False
        try:
            public_key.verify(bytes.fromhex(entry["sig"]), digest.encode("utf-8"))
        except (InvalidSignature, ValueError, KeyError):
            return False
        prev = digest
    return True


def verify_chain(ledger: Ledger) -> bool:
    return verify_stored_chain(ledger.entries, ledger.public_key_hex())
