import pytest

from experiments.common.sequential_suite_graph import SUITE_GRAPH, run_sequential_suite
from experiments.ablation import run_all_ablations, run_protection_ablations
from experiments.baselines import run_baseline_comparisons
from experiments.evaluation import cg_external_controller_comparison


def test_suite_graph_runs_ordered_steps_and_retains_results_outside_state():
    calls = []
    results = run_sequential_suite([
        ("prepare", lambda: calls.append("prepare")),
        ("privacy", lambda: calls.append("privacy") or {"n": 3}),
        ("copyright", lambda: calls.append("copyright") or {"n": 2}),
    ])
    assert calls == ["prepare", "privacy", "copyright"]
    assert results["privacy"] == {"n": 3}
    assert {"execute_step", "advance"} <= set(SUITE_GRAPH.get_graph().nodes)


def test_suite_graph_empty_and_duplicate_steps():
    assert run_sequential_suite([]) == {}
    with pytest.raises(ValueError):
        run_sequential_suite([("same", lambda: 1), ("same", lambda: 2)])


def test_baseline_and_protection_suite_use_ordered_graph_steps(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(run_baseline_comparisons, "run_privacy_baselines",
                        lambda *a, **k: calls.append("privacy") or {"privacy": 1})
    monkeypatch.setattr(run_baseline_comparisons, "run_copyright_baselines",
                        lambda *a, **k: calls.append("copyright") or {"copyright": 1})
    baseline = run_baseline_comparisons.run_suite(
        tmp_path / "dummy.yaml", tmp_path / "baseline")
    assert calls == ["privacy", "copyright"]
    assert baseline["privacy_baselines"] == {"privacy": 1}
    assert baseline["copyright_baselines"] == {"copyright": 1}
    assert (tmp_path / "baseline/baseline_comparison_summary.json").exists()

    calls.clear()
    monkeypatch.setattr(run_protection_ablations, "run_fopd_ablation",
                        lambda *a, **k: calls.append("fopd") or {"fopd": 1})
    monkeypatch.setattr(run_protection_ablations, "run_c2rag_ablation",
                        lambda *a, **k: calls.append("c2rag") or {"c2rag": 1})
    ablation = run_protection_ablations.run_suite(
        tmp_path / "dummy.yaml", tmp_path / "ablation")
    assert calls == ["fopd", "c2rag"]
    assert ablation["fopd_component_ablation"] == {"fopd": 1}
    assert ablation["c2rag_component_ablation"] == {"c2rag": 1}


def test_hsw_st_suite_dry_run_keeps_four_commands_without_model_calls(tmp_path):
    commands = run_all_ablations.run_suite(
        run_all_ablations.DEFAULT_CONFIG,
        tmp_path / "hsw-st",
        mode="experiment",
        dry_run=True,
    )
    assert len(commands) == 4
    assert all("--config" in command for command in commands)


def test_external_controller_suite_dispatches_each_controller_via_graph(tmp_path, monkeypatch):
    mod = cg_external_controller_comparison
    seen = []
    monkeypatch.setattr(mod, "OUTPUT", tmp_path)
    monkeypatch.setattr(mod, "load_episodes", lambda path: [{"episode_id": "e", "round_sequence": []}])
    monkeypatch.setattr(mod, "NeMoGuardrailsAdapter",
                        lambda *args, **kwargs: type("Adapter", (), {"runtime_available": False})())
    monkeypatch.setattr(mod, "_run_mode",
                        lambda mode, episodes, **kwargs: seen.append(mode) or
                        [{"episode_id": "e", "rounds": []}])
    monkeypatch.setattr(mod, "compute_mode_metrics", lambda name, rows: {"controller": name})
    result = mod.run()
    assert seen == list(mod.CONTROLLERS.values())
    assert len(result["summaries"]) == len(mod.CONTROLLERS)
    assert (tmp_path / "summary.json").exists()
