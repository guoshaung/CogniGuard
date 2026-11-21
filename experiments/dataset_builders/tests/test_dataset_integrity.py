from __future__ import annotations

from experiments.dataset_builders.build_math_datasets import DEFAULT_OUTPUT
from experiments.dataset_builders.validate_math_dataset import validate_suite


def test_generated_default_suite_satisfies_v2_invariants() -> None:
    report = validate_suite(DEFAULT_OUTPUT)
    assert report["valid"] is True
    assert report["independent_task_count"] == 240
    assert report["packs"]["mixed_math_suite"]["questions"] == 240
    assert report["packs"]["mixed_math_suite"]["profiles"] == 90
    assert report["packs"]["mixed_math_suite"]["learning_events"] == 900
    assert report["packs"]["mixed_math_suite"]["attack_templates"] == 75
    assert report["packs"]["mixed_math_suite"]["episodes"] == 480
