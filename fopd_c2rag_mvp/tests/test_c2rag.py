from __future__ import annotations

from pathlib import Path

from src.c2rag.exposure_budget import ExposureBudget
from src.c2rag.return_policy import decide_return_mode, produce_controlled_resource
from src.c2rag.variant_generator import generate_variant
from src.pipeline.run_demo import load_config, load_resources


ROOT = Path(__file__).resolve().parents[1]


def test_c2rag_high_copyright_no_quote() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    resource = load_resources(ROOT / "data/teacher_resources.jsonl")[0]
    controlled = produce_controlled_resource(resource, ExposureBudget(config), config)
    assert controlled.mode != "quote"
    assert resource.content not in controlled.text


def test_exposure_budget_increases() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    resource = load_resources(ROOT / "data/teacher_resources.jsonl")[1]
    budget = ExposureBudget(config)
    first = budget.update(resource, resource.content[:18])["after"]
    second = budget.update(resource, resource.content[:24])["after"]
    assert second > first


def test_policy_degrades_mode() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    resource = load_resources(ROOT / "data/teacher_resources.jsonl")[1]
    assert decide_return_mode(resource, 0.0, config) == "quote"
    assert decide_return_mode(resource, 0.20, config) == "summary"
    assert decide_return_mode(resource, 0.36, config) == "outline"
    assert decide_return_mode(resource, 0.50, config) == "variant"


def test_variant_not_same_as_original() -> None:
    config = load_config(ROOT / "configs/default.yaml")
    resource = load_resources(ROOT / "data/teacher_resources.jsonl")[0]
    variant = generate_variant(resource, config)
    assert variant["KMatch"]
    assert variant["DifficultyMatch"]
    assert variant["Solvable"]
    assert variant["variant_question"] != resource.content
    assert variant["LCS"] <= config["variant"]["max_lcs_ratio"]
    assert variant["SurfaceSim"] <= config["variant"]["max_surface_sim"]
