from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
import yaml
from core.langgraph_runtime.experiments import (load_plan, run_matrix, variant_config,
                                               isolated_env, Job, ROOT)


def save_plan(tmp_path, job):
    p = tmp_path / "plan.yaml"
    p.write_text(yaml.safe_dump({"schema_version": 1, "jobs": [job]}), encoding="utf-8")
    return p


def test_component_ablation_never_removes_hard_access_policy():
    original = {"access": {"max_profile_sensitivity": .7}, "fopd": {"use_enhanced_fopd": False}}
    previous = deepcopy(original)
    changed = variant_config(original, "enhanced_without_orthogonal")
    assert changed["fopd"]["components"]["use_orthogonal"] is False
    assert changed["access"] == original["access"]
    assert original == previous


@pytest.mark.parametrize("field", ["attack_indicators", "expected_action", "oracle", "api_key"])
def test_runtime_plan_rejects_labels_and_secrets(tmp_path, field):
    p = save_plan(tmp_path, {"adapter": "pipeline", field: "MUST_NOT_ENTER_RUNTIME"})
    with pytest.raises(ValueError):load_plan(p)


def test_plan_only_never_executes_adapter_or_overwrites(tmp_path, monkeypatch):
    p = save_plan(tmp_path, {"adapter": "pipeline", "variants": ["graph_default"]})
    def forbidden(*args, **kwargs):raise AssertionError("Subprocess must not run in plan-only mode")
    monkeypatch.setattr("core.langgraph_runtime.experiments.subprocess.run", forbidden)
    output = tmp_path / "output"
    summary = run_matrix(p, output)
    assert summary["jobs"][0]["status"] == "planned"
    assert summary["failed_jobs"] == 0
    before = (output / "summary.json").read_bytes()
    with pytest.raises(FileExistsError):run_matrix(p, output)
    assert before == (output / "summary.json").read_bytes()


def test_real_model_execution_requires_separate_opt_in(tmp_path, monkeypatch):
    p = save_plan(tmp_path, {"adapter": "teaching", "dry_run": False})
    def forbidden(*args, **kwargs):raise AssertionError("No model execution expected")
    monkeypatch.setattr("core.langgraph_runtime.experiments.subprocess.run", forbidden)
    summary = run_matrix(p, tmp_path / "blocked", execute=True)
    assert summary["failed_jobs"] == 1
    trace = next((tmp_path / "blocked").glob("job-*/node-trace.json")).read_text()
    assert '"stage": "validate_plan"' in trace
    assert "execute_adapter" not in trace


def test_pipeline_dry_run_is_respected_even_with_execute_flag(tmp_path, monkeypatch):
    p = save_plan(tmp_path, {"adapter": "pipeline", "dry_run": True})
    def forbidden(*args, **kwargs):raise AssertionError("dry-run pipeline must not execute")
    monkeypatch.setattr("core.langgraph_runtime.experiments.subprocess.run", forbidden)
    summary = run_matrix(p, tmp_path / "dry_pipeline", execute=True)
    assert summary["jobs"][0]["status"] == "planned"
    assert summary["failed_jobs"] == 0


def test_subprocess_has_fixed_hash_seed_and_disabled_native_tracing():
    previous = dict(os.environ)
    env = isolated_env(891)
    assert env["PYTHONHASHSEED"] == "891"
    assert env["LANGSMITH_TRACING"] == "false"
    assert env["LANGCHAIN_TRACING_V2"] == "false"
    assert dict(os.environ) == previous


def test_unregistered_adapter_and_fake_variant_are_rejected(tmp_path):
    for job in ({"adapter": "arbitrary_python"}, {"adapter": "teaching", "variants": ["enhanced_full"]}):
        with pytest.raises(ValueError):load_plan(save_plan(tmp_path, job))


def test_default_plan_covers_graph_ablation_and_safe_dry_runs():
    jobs = load_plan(ROOT / "configs/langgraph-experiments.yaml")
    assert len(jobs) == 9
    assert {j.variant for j in jobs if j.adapter == "pipeline"} == {
        "graph_default", "enhanced_full", "enhanced_without_orthogonal",
        "enhanced_without_attention", "enhanced_without_bottleneck"}
    assert all(j.dry_run for j in jobs if j.adapter != "pipeline")
