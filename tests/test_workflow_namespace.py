"""Workflow migration keeps old imports as identities, not copied definitions."""

from importlib import import_module
from pathlib import Path

import pytest

from core.paths import PROJECT_ROOT

MODULES = (
    "pipeline",
    "adapters",
    "experiment_catalog",
    "experiments",
    "model_site",
    "tool_jobs",
    "__main__",
    "teachers.catalog",
    "teachers.chain",
    "teachers.dag",
    "teachers.handoff_guard",
    "teachers.runner",
    "teachers.skills",
    "teachers.store",
    "benchmarks.cli",
    "benchmarks.corpus",
    "benchmarks.plan",
    "benchmarks.runner",
)


@pytest.mark.parametrize("name", MODULES)
def test_historical_module_is_the_canonical_module(name):
    old = import_module(f"core.langgraph_runtime.{name}")
    current = import_module(f"cogniguard.workflows.{name}")
    assert old is current
    assert Path(current.__file__).resolve().is_relative_to(PROJECT_ROOT / "cogniguard/workflows")


def test_monkeypatch_and_exported_classes_are_shared(monkeypatch):
    old = import_module("core.langgraph_runtime.pipeline")
    current = import_module("cogniguard.workflows.pipeline")
    assert old.LangGraphProtectionPipeline is current.LangGraphProtectionPipeline
    monkeypatch.setattr(old, "MIGRATION_PROBE", "one-module", raising=False)
    assert current.MIGRATION_PROBE == "one-module"
    historical = import_module("core.langgraph_runtime.teachers")
    canonical = import_module("cogniguard.workflows.teachers")
    assert historical.PromptLibrary is canonical.PromptLibrary
    assert historical.TeacherDAGGenerator is canonical.TeacherDAGGenerator


def test_project_paths_stay_stable_and_canonical_sources_are_frozen():
    from cogniguard.workflows import experiments, model_site, tool_jobs

    assert experiments.ROOT == model_site.ROOT == tool_jobs.ROOT == PROJECT_ROOT
    hashes = experiments.source_hashes()
    assert "cogniguard/workflows/pipeline.py" in hashes
    assert "core/langgraph_runtime/pipeline.py" in hashes


def test_workflow_cli_is_not_a_research_tool():
    from cogniguard.workflows.tool_jobs import _source_file

    with pytest.raises(ValueError, match="entrypoints"):
        _source_file("cogniguard.workflows.__main__")
