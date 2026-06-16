from __future__ import annotations

from pathlib import Path

from protection.fopd_c2rag_mvp.src.pipeline.run_demo import run_pipeline


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_outputs_trace(tmp_path: Path) -> None:
    out = tmp_path / "demo_results.jsonl"
    result = run_pipeline(
        ROOT / "data/profiles.jsonl",
        ROOT / "data/student_questions.jsonl",
        ROOT / "data/teacher_resources.jsonl",
        ROOT / "configs/default.yaml",
        out,
    )
    assert out.exists()
    resource_rows = [r for r in result["rows"] if r["task"]["need_resource"]]
    assert resource_rows
    for row in resource_rows:
        trace = row["source_trace"]
        assert trace["resource_id"]
        assert trace["chunk_id"]
        assert trace["return_mode"] == row["return_mode"]
        assert row["watermark_id"].startswith("wm_")
        assert row["source_trace_log"]["watermark_id"] == row["watermark_id"]
        assert row["source_trace_log"]["trace_binding_id"] == row["trace_binding_id"]
        assert row["agent_logs"]["AG1"]["agent"] == "AG1 learner_task_agent"
        assert row["agent_logs"]["AG3"]["agent"] == "AG3 copyright_resource_agent"
        assert "FOPD" in row["algorithm_links"]

    source_logs = tmp_path / "source_trace_logs.jsonl"
    watermark_logs = tmp_path / "watermark_logs.jsonl"
    unified_logs = tmp_path / "unified_trace_logs.jsonl"
    hsw_input = tmp_path / "hsw_st_input.jsonl"
    assert source_logs.exists()
    assert watermark_logs.exists()
    assert unified_logs.exists()
    assert hsw_input.exists()
