"""Strict, credential-free post-hoc task envelopes and model identities."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass

HEX = re.compile(r"[0-9a-f]{64}\Z")
TASK_ID = re.compile(r"[0-9a-f]{32}\Z")
PRF = "sha256-u32le-first16-big-mod32-pcg64-permutation"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class ModelIdentity:
    model_id: str
    revision: str
    precision: str
    manifest_sha256: str
    tokenizer_sha256: str

    def validate(self) -> None:
        if self.model_id != "Qwen/Qwen2.5-7B-Instruct" or not self.revision:
            raise ValueError("Explicit Qwen2.5-7B identity/revision required")
        if self.precision not in {"fp16", "gguf-q4_k_m"}:
            raise ValueError("Precision branch must be explicit")
        for value in (self.manifest_sha256, self.tokenizer_sha256):
            if not HEX.fullmatch(value):
                raise ValueError("Invalid model/tokenizer hash")


@dataclass(frozen=True)
class Task:
    task_id: str
    input_text: str
    input_sha256: str
    contract_sha256: str
    source_review_sha256: str
    messages: list[dict[str, str]]
    messages_sha256: str
    method: str
    model: ModelIdentity
    key_sha256: str
    output_relpath: str
    seed: int = 0
    max_new_tokens: int = 32
    gamma: float = 0.25
    delta: float = 2.0
    window: int = 4
    vocab_size: int = 151643
    threshold: float = 3.0
    prf: str = PRF
    schema_version: int = 1

    def validate(self) -> None:
        if self.schema_version != 1 or not TASK_ID.fullmatch(self.task_id):
            raise ValueError("Invalid schema/task ID")
        if self.method not in {"clean", "kgw"}:
            raise ValueError("Only existing CLEAN/KGW rewrites allowed")
        self.model.validate()
        if not self.input_text or digest(self.input_text.encode()) != self.input_sha256:
            raise ValueError("Frozen original hash mismatch")
        if digest(canonical(self.messages)) != self.messages_sha256:
            raise ValueError("Frozen messages mismatch")
        for h in (self.contract_sha256, self.source_review_sha256, self.key_sha256):
            if not HEX.fullmatch(h):
                raise ValueError("Missing frozen contract/review/key commitment")
        if (
            len(self.messages) != 2
            or [m.get("role") for m in self.messages] != ["system", "user"]
            or any(set(m) != {"role", "content"} for m in self.messages)
            or self.input_text not in self.messages[-1]["content"]
        ):
            raise ValueError("Worker must receive the actual original, not a new QA task")
        if self.output_relpath != f"results/{self.task_id}.json":
            raise ValueError("Output path must remain inside the task namespace")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("Invalid fixed seed")
        if type(self.max_new_tokens) is not int or not 1 <= self.max_new_tokens <= 1024:
            raise ValueError("Token cap outside bounded protocol")
        if (self.gamma, self.delta, self.window, self.vocab_size, self.threshold, self.prf) != (
            0.25,
            2.0,
            4,
            151643,
            3.0,
            PRF,
        ):
            raise ValueError("Frozen KGW definition cannot be changed by migration")

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)

    @property
    def sha256(self) -> str:
        return digest(canonical(self.to_dict()))

    @classmethod
    def from_dict(cls, value: dict) -> Task:
        data = dict(value)
        data["model"] = ModelIdentity(**data["model"])
        task = cls(**data)
        task.validate()
        return task


def same_numeric_model(a: ModelIdentity, b: ModelIdentity) -> bool:
    """An FP16 migration is never an exact GGUF comparison."""
    return a == b
