from experiments.attacks.episode_attack_runner import EpisodeAttackRunner
from experiments.dataset_builders.build_math_datasets import DEFAULT_OUTPUT


def test_episode_attack_runner_initializes_with_slots_and_is_seeded() -> None:
    first = EpisodeAttackRunner(seed=2026).run_episode("ep_0001")
    second = EpisodeAttackRunner(seed=2026).run_episode("ep_0001")
    assert first == second
    assert first["episode_id"] == "ep_0001"
    assert 0.0 <= first["attack_success_probability"] <= 1.0


def test_episode_attack_runner_consumes_expanded_clean_attack_pairs() -> None:
    result = EpisodeAttackRunner(seed=2026).run_expanded_dataset(
        DEFAULT_OUTPUT / "mixed_math_suite"
    )
    summary = result["summary"]
    assert summary["episodes"] == 480
    assert summary["clean_episodes"] == 240
    assert summary["attack_episodes"] == 240
    assert summary["pairs"] == 240
    assert summary["students_covered"] == 90
    assert summary["resources_covered"] == 62
    assert summary["restricted_target_rate"] == 1.0
    assert set(summary["family_summary"]) == {
        "membership_inference",
        "model_inversion",
        "copyright_extraction",
        "prompt_injection",
        "audit_evasion",
    }
