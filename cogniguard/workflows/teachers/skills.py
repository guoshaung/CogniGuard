"""Trusted, versioned teaching-agent skill catalog (not Codex skills)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .catalog import digest, load_document, slug


@dataclass(frozen=True)
class SkillSpec:
    teacher: str
    version: str
    title: str
    instructions: str

    @property
    def sha256(self) -> str:
        return digest(asdict(self))

    @property
    def system_fragment(self) -> str:
        return f"\n\n【教学技能：{self.title}｜{self.version}】\n{self.instructions}"


class SkillLibrary:
    def __init__(self, path: str | Path):
        data, self.sha256 = load_document(path)
        if (
            set(data) != {"schema_version", "skills"}
            or not isinstance(data["skills"], dict)
            or not data["skills"]
        ):
            raise ValueError("Invalid teaching skill catalog")
        self._skills = {}
        for teacher, entry in data["skills"].items():
            slug(teacher)
            if not isinstance(entry, dict) or set(entry) != {"version", "title", "instructions"}:
                raise ValueError("Invalid teaching skill entry")
            slug(entry["version"])
            if not isinstance(entry["title"], str) or not 1 <= len(entry["title"]) <= 100:
                raise ValueError("Invalid teaching skill title")
            if (
                not isinstance(entry["instructions"], str)
                or not 20 <= len(entry["instructions"]) <= 12000
            ):
                raise ValueError("Invalid teaching skill instructions")
            self._skills[teacher] = SkillSpec(
                teacher, entry["version"], entry["title"], entry["instructions"]
            )

    def get(self, teacher: str) -> SkillSpec:
        try:
            return self._skills[teacher]
        except KeyError:
            raise ValueError("Unknown teaching skill") from None

    def inventory(self) -> list[dict[str, str]]:
        return [
            {
                "teacher": teacher,
                "version": item.version,
                "title": item.title,
                "sha256": item.sha256,
            }
            for teacher, item in sorted(self._skills.items())
        ]
