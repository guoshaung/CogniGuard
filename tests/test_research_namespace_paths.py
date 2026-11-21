"""Static activity checks and doc packaging paths; never execute experiment runners."""

from __future__ import annotations

import ast
import re

import pytest

from core.paths import PROJECT_ROOT

_BLOCKED = {"frozen", "results", "archive", "external_data", "__pycache__", "node_modules"}
_BLOCKED_TERMS = ("watermark", "hsw", "locguard", "audit_trace", "formal_v2_output")


def _active_sources():
    for folder in (
        "experiments",
        "scripts",
        "protection/student_profile",
        "protection/teacher_resource",
    ):
        for path in (PROJECT_ROOT / folder).rglob("*.py"):
            relative = path.relative_to(PROJECT_ROOT)
            name = relative.as_posix().casefold()
            if any(
                part in _BLOCKED or part.startswith(("retained_", "preserved_"))
                for part in relative.parts
            ):
                continue
            if any(term in name for term in _BLOCKED_TERMS):
                continue
            if any(re.search(r"20\d{6}", part) for part in relative.parts):
                continue
            if "group_meeting_review" in name or "review_existing" in name:
                continue
            yield path


def test_active_non_watermark_research_uses_canonical_imports():
    forbidden = ("core.langgraph_runtime", "cogniguard.demo")
    problems = []
    for path in _active_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            if any(
                name == prefix or name.startswith(prefix + ".")
                for name in names
                for prefix in forbidden
            ):
                problems.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    assert not problems, problems


def test_packager_collects_current_retrieval_docs_without_building_an_archive(tmp_path):
    from experiments.c2rag_v3.package_v5 import documentation_paths

    docs = tmp_path / "docs/research/retrieval"
    docs.mkdir(parents=True)
    for name in (
        "C2RAG_LICENSE.md",
        "c2rag_design.md",
        "not_selected.md",
        "development_pilot_report.md",
        "RUN_READINESS.md",
    ):
        (docs / name).write_text("fixture", encoding="utf-8")
    selected = documentation_paths(tmp_path)
    assert {path.name for path in selected} == {
        "C2RAG_LICENSE.md",
        "c2rag_design.md",
        "development_pilot_report.md",
        "RUN_READINESS.md",
    }
    assert all(path.parent == docs for path in selected)
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize(
    "filename, report",
    [
        ("cg_v3_five_baseline_pilot.py", "CG_V3_FIVE_BASELINE_PILOT_REPORT.md"),
        ("cg_v3_pilot_v3_1.py", "CG_V3_THREE_MODE_PILOT_REPORT_V3_1.md"),
        ("cg_v3_pilot.py", "CG_V3_THREE_MODE_PILOT_REPORT.md"),
    ],
)
def test_cgc_report_targets_use_the_current_research_directory(filename, report):
    path = PROJECT_ROOT / "experiments/evaluation" / filename
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    expressions = [
        ast.get_source_segment(source, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
    ]
    assert any('"docs/research/cgc"' in segment and report in segment for segment in expressions)
    assert f'ROOT / "docs" / "{report}"' not in source


def test_packager_current_repository_document_paths_exist():
    from experiments.c2rag_v3.package_v5 import documentation_paths

    docs = documentation_paths()
    assert docs
    assert all(path.is_file() for path in docs)
    assert all(path.is_relative_to(PROJECT_ROOT / "docs/research/retrieval") for path in docs)
