from pathlib import Path

from protection.student_profile.src.pipeline import run_demo
from protection.student_profile.src.pipeline.legacy_graph import (
    LEGACY_GRAPH, LegacyFrame, run_legacy_batch,
)


ROOT = Path(__file__).resolve().parents[3]


def test_historical_fopd_c2rag_batch_runs_through_fine_grained_graph(tmp_path, monkeypatch):
    original = run_demo.load_config

    def offline(path):
        config = original(path)
        config.setdefault("llm", {})["enabled"] = False
        return config

    monkeypatch.setattr(run_demo, "load_config", offline)
    output = tmp_path / "results.jsonl"
    result = run_demo.run_pipeline(
        ROOT / "protection/student_profile/data/profiles.jsonl",
        ROOT / "protection/student_profile/data/student_questions.jsonl",
        ROOT / "protection/teacher_resource/data/teacher_resources.jsonl",
        ROOT / "protection/student_profile/configs/default.yaml",
        output,
    )
    assert result["summary"]["num_requests"] == 3
    assert len(result["rows"]) == 3
    assert {"select_task", "retrieve_and_control", "answer_and_bind",
            "score_and_package", "advance"} <= set(LEGACY_GRAPH.get_graph().nodes)
    assert output.exists()
    assert (tmp_path / "unified_trace_logs.jsonl").exists()


def test_historical_graph_empty_batch_never_calls_services():
    frame = LegacyFrame([], {}, [], {}, None, None, None, None, None)
    assert run_legacy_batch(frame).rows == []
