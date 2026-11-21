from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

VIEW_FIELDS = frozenset(
    {"question", "knowledge", "difficulty", "context_card", "resource_mode", "resource_text"}
)
DATA_LABELS = frozenset({"task", "minimized_profile", "controlled_resource"})


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", value):
        raise ValueError("Expected a short configuration identifier")
    return value


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError("Duplicate YAML key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def load_document(path):
    raw = Path(path).read_bytes()
    data = yaml.load(raw.decode("utf-8-sig"), Loader=UniqueKeyLoader)
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError("Expected catalog schema_version: 1")
    return data, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PromptSpec:
    teacher: str
    display_name: str
    version: str
    system: str

    @property
    def sha256(self):
        return digest(asdict(self))


class PromptLibrary:
    def __init__(self, path):
        data, self.sha256 = load_document(path)
        if (
            set(data) != {"schema_version", "teachers"}
            or not isinstance(data["teachers"], dict)
            or not data["teachers"]
        ):
            raise ValueError("Invalid prompt library")
        self._prompts = {}
        for teacher, entry in data["teachers"].items():
            slug(teacher)
            if not isinstance(entry, dict) or set(entry) != {"display_name", "versions"}:
                raise ValueError("Invalid teacher definition")
            if (
                not isinstance(entry["display_name"], str)
                or not isinstance(entry["versions"], dict)
                or not entry["versions"]
            ):
                raise ValueError("Invalid teacher display name/versions")
            for version, system in entry["versions"].items():
                slug(version)
                if not isinstance(system, str) or not 20 <= len(system) <= 12000:
                    raise ValueError("Prompt must be a nonempty trusted system instruction")
                self._prompts[teacher, version] = PromptSpec(
                    teacher, entry["display_name"], version, system
                )

    def get(self, teacher, version):
        try:
            return self._prompts[teacher, version]
        except KeyError:
            raise ValueError("Unknown teacher/prompt version") from None

    def inventory(self):
        return [
            {"teacher": t, "version": v, "display_name": p.display_name, "sha256": p.sha256}
            for (t, v), p in sorted(self._prompts.items())
        ]


@dataclass(frozen=True)
class TeacherNode:
    id: str
    teacher: str
    prompt: str = "v1"
    backend: str = "default"
    view_fields: tuple[str, ...] = ("question", "knowledge", "difficulty")
    requires_all_inputs: bool = True
    max_output_chars: int = 2400
    upstream_labels: tuple[str, ...] = ("task", "minimized_profile", "controlled_resource")


@dataclass(frozen=True)
class TeacherEdge:
    source: str
    target: str
    max_chars: int = 2400
    allowed_labels: tuple[str, ...] = ("task", "minimized_profile", "controlled_resource")


@dataclass(frozen=True)
class TeamSpec:
    name: str
    nodes: tuple[TeacherNode, ...]
    edges: tuple[TeacherEdge, ...]
    output: str

    @property
    def sha256(self):
        return digest(asdict(self))

    def parents(self, node):
        return tuple(e.source for e in self.edges if e.target == node)

    def order(self):
        remaining = {n.id: set(self.parents(n.id)) for n in self.nodes}
        order = []
        while remaining:
            ready = sorted(k for k, parents in remaining.items() if not parents)
            if not ready:
                raise ValueError("Teacher graph must be acyclic")
            order.extend(ready)
            for k in ready:
                remaining.pop(k)
            for parents in remaining.values():
                parents.difference_update(ready)
        return tuple(order)

    def validate(self, library):
        slug(self.name)
        if not 1 <= len(self.nodes) <= 24:
            raise ValueError("Teacher DAG must have 1..24 nodes")
        ids = [slug(n.id) for n in self.nodes]
        if len(set(ids)) != len(ids) or "teacher_finalize" in ids or self.output not in ids:
            raise ValueError("Duplicate/reserved node or unknown output")
        for n in self.nodes:
            library.get(n.teacher, n.prompt)
            slug(n.backend)
            if (
                not n.view_fields
                or len(set(n.view_fields)) != len(n.view_fields)
                or set(n.view_fields) - VIEW_FIELDS
            ):
                raise ValueError("Teacher can read only explicitly allowed TeachingInput fields")
            if (
                type(n.requires_all_inputs) is not bool
                or type(n.max_output_chars) is not int
                or not 64 <= n.max_output_chars <= 12000
            ):
                raise ValueError("Invalid teacher node limits")
            if set(n.upstream_labels) - DATA_LABELS:
                raise ValueError("Unknown upstream data label")
        pairs = [(e.source, e.target) for e in self.edges]
        if len(set(pairs)) != len(pairs) or len(pairs) > 96:
            raise ValueError("Duplicate or excessive edges")
        for e in self.edges:
            if e.source not in ids or e.target not in ids or e.source == e.target:
                raise ValueError("Invalid teacher edge")
            if type(e.max_chars) is not int or not 1 <= e.max_chars <= 12000:
                raise ValueError("Invalid edge disclosure limit")
            if set(e.allowed_labels) - DATA_LABELS:
                raise ValueError("Unknown edge data label")
        self.order()
        ancestors = {self.output}
        while True:
            expanded = ancestors | {e.source for e in self.edges if e.target in ancestors}
            if expanded == ancestors:
                break
            ancestors = expanded
        if ancestors != set(ids) or any(e.source == self.output for e in self.edges):
            raise ValueError("Every teacher must contribute to the single output sink")


class TeamCatalog:
    def __init__(self, path, library):
        data, self.sha256 = load_document(path)
        if (
            set(data) != {"schema_version", "teams"}
            or not isinstance(data["teams"], dict)
            or not data["teams"]
        ):
            raise ValueError("Invalid team catalog")
        self.teams = {}
        for name, entry in data["teams"].items():
            if not isinstance(entry, dict) or set(entry) != {"nodes", "edges", "output"}:
                raise ValueError("Team contains unrecognized fields")
            if not isinstance(entry["nodes"], list) or not isinstance(entry["edges"], list):
                raise ValueError("Expected node and edge lists")
            nodes = []
            for item in entry["nodes"]:
                if not isinstance(item, dict) or set(item) - set(TeacherNode.__dataclass_fields__):
                    raise ValueError("Unrecognized node fields")
                item = dict(item)
                for key in ("view_fields", "upstream_labels"):
                    if key in item:
                        if not isinstance(item[key], list):
                            raise ValueError("Node field lists required")
                        item[key] = tuple(item[key])
                nodes.append(TeacherNode(**item))
            edges = []
            for item in entry["edges"]:
                if not isinstance(item, dict) or set(item) - set(TeacherEdge.__dataclass_fields__):
                    raise ValueError("Unrecognized edge fields")
                item = dict(item)
                if "allowed_labels" in item:
                    if not isinstance(item["allowed_labels"], list):
                        raise ValueError("Edge label list required")
                    item["allowed_labels"] = tuple(item["allowed_labels"])
                edges.append(TeacherEdge(**item))
            spec = TeamSpec(name, tuple(nodes), tuple(edges), entry["output"])
            spec.validate(library)
            self.teams[name] = spec

    def get(self, name):
        try:
            return self.teams[name]
        except KeyError:
            raise ValueError("Unknown teacher team") from None
