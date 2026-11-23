from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProfileRecord:
    record_id: str
    type: str
    knowledge: str
    value: Any
    confidence: float
    sensitivity: float
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileRecord":
        return cls(
            record_id=str(data.get("record_id", "")),
            type=str(data.get("type", "")),
            knowledge=str(data.get("knowledge", "")),
            value=data.get("value", ""),
            confidence=float(data.get("confidence", 0.0)),
            sensitivity=float(data.get("sensitivity", 0.0)),
            updated_at=str(data.get("updated_at", "")),
        )

    def text(self) -> str:
        return f"{self.type} {self.knowledge} {self.value}"


@dataclass(slots=True)
class StudentProfile:
    student_id: str
    local_only_fields: dict[str, Any] = field(default_factory=dict)
    profile_records: list[ProfileRecord] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StudentProfile":
        return cls(
            student_id=str(data.get("student_id", "")),
            local_only_fields=dict(data.get("local_only_fields") or {}),
            profile_records=[
                ProfileRecord.from_dict(item) for item in data.get("profile_records", [])
            ],
        )


@dataclass(slots=True)
class Task:
    request_id: str
    student_id: str
    question: str
    knowledge: str
    difficulty: str
    need_resource: bool

    def text(self) -> str:
        return f"{self.question} {self.knowledge} {self.difficulty}"


@dataclass(slots=True)
class ResourcePolicy:
    allow_quote: bool = False
    allow_summary: bool = True
    allow_outline: bool = True
    allow_variant: bool = True
    max_quote_len: int = 20
    max_exposure: float = 0.55

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ResourcePolicy":
        data = data or {}
        return cls(
            allow_quote=bool(data.get("allow_quote", False)),
            allow_summary=bool(data.get("allow_summary", True)),
            allow_outline=bool(data.get("allow_outline", True)),
            allow_variant=bool(data.get("allow_variant", True)),
            max_quote_len=int(data.get("max_quote_len", 20)),
            max_exposure=float(data.get("max_exposure", 0.55)),
        )


@dataclass(slots=True)
class TeacherResource:
    # owner_principal_id 和 org_id 只是元数据，不得用作授权依据；授权以后端构建的 AssetOwnership 登记为准。
    resource_id: str
    chunk_id: str
    content: str
    knowledge: str
    difficulty: str
    cognitive_level: str
    resource_type: str
    copyright_level: float
    policy: ResourcePolicy
    owner_principal_id: str | None = None
    org_id: str | None = None

    @property
    def confidentiality_level(self) -> float:
        return self.copyright_level

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeacherResource":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            chunk_id=str(data.get("chunk_id", "")),
            content=str(data.get("content", "")),
            knowledge=str(data.get("knowledge", "")),
            difficulty=str(data.get("difficulty", "")),
            cognitive_level=str(data.get("cognitive_level", "")),
            resource_type=str(data.get("resource_type", "")),
            copyright_level=float(data.get("copyright_level", 0.0)),
            policy=ResourcePolicy.from_dict(data.get("policy")),
            owner_principal_id=None if data.get("owner_principal_id") is None else str(data["owner_principal_id"]),
            org_id=None if data.get("org_id") is None else str(data["org_id"]),
        )


@dataclass(slots=True)
class RetrievedResource:
    resource: TeacherResource
    score: float
    components: dict[str, float]


@dataclass(slots=True)
class ControlledResource:
    mode: str
    text: str
    resource: TeacherResource | None
    exposure_before: float
    exposure_after: float
    source_trace: dict[str, Any]
