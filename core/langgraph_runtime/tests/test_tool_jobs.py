import json
from pathlib import Path

import pytest

from core.langgraph_runtime import tool_jobs
from core.langgraph_runtime.tool_jobs import TOOL_GRAPH, ToolRequest, list_tools, run_tool_job


@pytest.fixture
def results_root(tmp_path, monkeypatch):
    root = tmp_path / "jobs"
    monkeypatch.setattr(tool_jobs, "TOOL_RESULTS_ROOT", root)
    return root


def test_inventory_is_first_party_without_vendor_imports():
    names = {item["module"] for item in list_tools()}
    assert "experiments.formal_v2.run_formal" in names
    assert "experiments.mmfopd_uci.alignment_probe" in names
    assert "experiments.evaluation.eval_joint_synergy" in names
    assert "protection.audit_trace.src.main" in names
    assert "scripts.build_episode_dataset" in names
    assert "protection.supporting.image_watermark.src.run_v0_pipeline" in names
    assert "third_party.editguard.train" in names
    assert "scripts.run_tests" not in names
    assert not {"cogniguard.cli", "cogniguard.__main__", "cogniguard.api.__main__"} & names
    assert not any("external_data" in name or ".tests." in name for name in names)
    assert {"validate", "freeze", "execute", "collect"} <= set(TOOL_GRAPH.get_graph().nodes)


def test_plan_never_runs_module(results_root):
    output = results_root / "planned"
    summary = run_tool_job(ToolRequest("experiments.formal_v2.run_formal", ("--help",), output))
    assert summary["status"] == "PLANNED"
    assert not (output / "stdout.txt").exists()
    assert json.loads((output / "manifest.json").read_text())["orchestrator"] == "langgraph"


def test_legacy_code_directory_is_planned_as_script_not_stdlib_code_module(results_root):
    output = results_root / "code-plan"
    summary = run_tool_job(ToolRequest("third_party.editguard.train", ("--help",), output))
    assert summary["status"] == "PLANNED"
    assert summary["execution_kind"] == "script"


def test_historical_tool_names_resolve_to_named_modules():
    assert ToolRequest("backend.app.demo.run_demo", (), Path("unused")).module == "cogniguard.demo.run_demo"
    assert ToolRequest("code.train", (), Path("unused")).module == "third_party.editguard.train"
    assert ToolRequest("dfg_locguard.src.run_v0_pipeline", (), Path("unused")).module == "protection.supporting.image_watermark.src.run_v0_pipeline"


def test_explicit_offline_run_captures_only_local_diagnostics(results_root):
    output = results_root / "help-run"
    summary = run_tool_job(ToolRequest("experiments.formal_v2.run_formal", ("--help",), output,
                                           execute=True))
    assert summary["status"] == "COMPLETED"
    assert summary["exit_code"] == 0
    assert b"--case-limit" in (output / "stdout.txt").read_bytes()
    assert (output / "node-trace.json").exists()


def test_risky_tools_require_explicit_flags_before_writing(results_root):
    output = results_root / "blocked"
    with pytest.raises(PermissionError):
        run_tool_job(ToolRequest("experiments.c2rag_v3.runner", ("--help",), output,
                                     execute=True))
    assert not output.exists()
    with pytest.raises(PermissionError, match="Archived Layer1"):
        run_tool_job(ToolRequest(
            "protection.Layer1_fopd_c2rag.src.pipeline.run_demo",
            ("--help",), output, execute=True,
            allow_unreviewed=True, allow_model_calls=True, allow_network=True))
    assert not output.exists()
    with pytest.raises(PermissionError):
        run_tool_job(ToolRequest("experiments.rag_real.prepare", ("--help",), output,
                                     execute=True))
    assert not output.exists()
    with pytest.raises(PermissionError):
        run_tool_job(ToolRequest("scripts.server.freeze_image_watermark_formal_config",
                                     ("--help",), output, execute=True,
                                     allow_model_calls=True, allow_network=True))
    assert not output.exists()


def test_script_output_override_is_separate_from_job_directory(results_root):
    output = results_root / "unbounded-default"
    with pytest.raises(PermissionError, match="script's own output"):
        run_tool_job(ToolRequest("experiments.formal_v2.run_formal", (), output,
                                     execute=True))
    assert not output.exists()


def test_legacy_underscore_output_flag_is_recorded_without_running(results_root):
    output = results_root / "underscore-output-plan"
    summary = run_tool_job(ToolRequest("protection.supporting.image_watermark.scripts.run_stage7_semantic_structured_template",
                                      ("--output_dir", str(output / "artifacts")), output))
    assert summary["status"] == "PLANNED"
    assert summary["script_output_override_present"] is True


def test_nonsecret_token_count_option_is_allowed_but_credentials_are_rejected(results_root):
    planned = results_root / "token-count-plan"
    summary = run_tool_job(ToolRequest(
        "experiments.formal_v2.run_formal", ("--max-tokens", "256"), planned))
    assert summary["status"] == "PLANNED"
    for option in ("--api-key=redacted", "--auth-token=redacted", "--password=redacted"):
        blocked = results_root / ("blocked-" + option.split("=")[0][2:])
        with pytest.raises(ValueError, match="secrets"):
            run_tool_job(ToolRequest(
                "experiments.formal_v2.run_formal", (option,), blocked))
        assert not blocked.exists()


def test_unknown_and_existing_output_never_get_modified(results_root):
    existing = results_root / "existing"
    existing.mkdir(parents=True)
    sentinel = existing / "node-trace.json"
    sentinel.write_text("KEEP")
    with pytest.raises(FileExistsError):
        run_tool_job(ToolRequest("experiments.formal_v2.run_formal", (), existing))
    assert sentinel.read_text() == "KEEP"
    with pytest.raises(ValueError):
        run_tool_job(ToolRequest("os", (), results_root / "unknown"))
    assert not (results_root / "unknown").exists()
    with pytest.raises(ValueError):
        run_tool_job(ToolRequest("experiments.formal_v2.run_formal", (),
                                     results_root.parent / "outside"))
    assert not (results_root.parent / "outside").exists()
