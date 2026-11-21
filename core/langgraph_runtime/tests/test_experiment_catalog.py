import json

import pytest

from core.langgraph_runtime import tool_jobs
from core.langgraph_runtime.experiment_catalog import (CATALOG, format_inventory,
                                                      inventory_summary, list_experiments,
                                                      resolve_experiment, run_experiment)


def test_catalog_is_unique_and_reviewed():
    records = list_experiments()
    discovered = {item["module"] for item in tool_jobs.list_tools()}
    assert len(records) == len(discovered) + 1
    assert {row["module"] for row in records if row["module"]} == discovered
    assert len({row["name"] for row in records}) == len(records)
    assert inventory_summary(records)["tiers"]["managed"] == len(CATALOG)
    assert inventory_summary(records)["tiers"]["unavailable"] == 5
    tree = format_inventory(records)
    assert "image-watermark" in tree
    assert "protection.supporting.image_watermark.scripts/" in tree
    assert "unavailable (5)" in tree
    assert "comparison-matrix" in CATALOG
    for spec in CATALOG.values():
        if spec.module:
            assert tool_jobs._source_file(spec.module).is_file()
            assert spec.risk == tool_jobs._risk(spec.module)
            assert spec.output_option in tool_jobs.OUTPUT_OPTIONS


def test_legacy_and_archive_are_visible_with_their_original_risk():
    image = resolve_experiment("protection.supporting.image_watermark.src.run_v0_pipeline")
    assert image.family == "image-watermark"
    assert image.risk == "unreviewed"
    assert image.output_option is None
    archive = resolve_experiment("protection.Layer1_fopd_c2rag.src.pipeline.run_demo")
    assert archive.risk == "unavailable_archive"
    assert any(row["name"] == image.name for row in list_experiments(family="image-watermark"))


def test_named_plan_uses_one_output_and_result_index(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", root)
    output = root / "privacy-plan"
    result = run_experiment("mmfopd-uci", output)
    assert result["status"] == "PLANNED"
    assert not (output / "artifacts").exists()
    index = json.loads((output / "experiment-index.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == 1
    assert index["name"] == "mmfopd-uci"
    assert manifest["risk"] == "offline"
    assert manifest["script_output_override_present"] is True
    assert not (output / "stdout.txt").exists()


def test_named_run_retains_model_gate_and_never_touches_existing_output(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", root)
    with pytest.raises(PermissionError):
        run_experiment("rag-scifact-calibration", root / "blocked", execute=True)
    assert not (root / "blocked").exists()
    existing = root / "existing"
    existing.mkdir(parents=True)
    (existing / "sentinel.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run_experiment("mmfopd-uci", existing)
    assert (existing / "sentinel.txt").read_text(encoding="utf-8") == "keep"
    with pytest.raises(ValueError):
        run_experiment("mmfopd-uci", tmp_path / "wrong-root")


def test_matrix_only_accepts_plan_argument(tmp_path, monkeypatch):
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", tmp_path / "jobs")
    with pytest.raises(ValueError, match="only to comparison-matrix"):
        run_experiment("mmfopd-uci", tmp_path / "jobs" / "wrong-plan", plan=tmp_path / "x.yaml")
    assert not (tmp_path / "jobs" / "wrong-plan").exists()


def test_compatible_entry_uses_same_index_without_promotion(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", root)
    name = "experiments.evaluation.cg_v3_pilot"
    output = root / "compatible-plan"
    result = run_experiment(name, output)
    assert result["status"] == "PLANNED"
    assert result["tier"] == "compatible"
    assert result["output_mode"] == "script_defined"
    with pytest.raises(PermissionError, match="Unreviewed"):
        run_experiment(name, root / "blocked", execute=True, allow_default_output=True)
    assert not (root / "blocked").exists()


def test_archive_cannot_execute_and_managed_arguments_cannot_redirect(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", root)
    with pytest.raises(PermissionError, match="Archived Layer1"):
        run_experiment("protection.Layer1_fopd_c2rag.src.pipeline.run_demo",
                       root / "archive-run", execute=True,
                       allow_unreviewed=True, allow_model_calls=True,
                       allow_network=True, allow_default_output=True)
    assert not (root / "archive-run").exists()
    with pytest.raises(ValueError, match="Managed experiments"):
        run_experiment("mmfopd-uci", root / "redirect", script_args=("--output", "elsewhere"))
    assert not (root / "redirect").exists()
