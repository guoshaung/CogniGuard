from __future__ import annotations

import pytest

from core import paths


@pytest.mark.parametrize(
    "old,new",
    [
        ("backend/app/api/http_server.py", "cogniguard/api/http_server.py"),
        ("frontend/dist/index.html", "visualization/dist/index.html"),
        ("code/options/test_editguard.yml", "third_party/editguard/options/test_editguard.yml"),
        ("dfg_locguard/configs/default.yaml", "protection/supporting/image_watermark/configs/default.yaml"),
        ("outputs/teaching_images/demo.png", "var/outputs/teaching_images/demo.png"),
        ("logs/backend.log", "var/logs/backend.log"),
        ("results/focused/summary.json", "var/results/focused/summary.json"),
        ("models/hf_cache/config.json", "assets/models/hf_cache/config.json"),
        ("checkpoints/clean.pth", "assets/checkpoints/clean.pth"),
        ("datasets/karc/cases.json", "data/benchmarks/karc/cases.json"),
        ("dfg_locguard/api_jobs/job/input.png", "var/outputs/sce_locguard_api_jobs/job/input.png"),
        (
            "protection/image_watermark/api_jobs/job/input.png",
            "var/outputs/sce_locguard_api_jobs/job/input.png",
        ),
    ],
)
def test_relative_and_absolute_historical_paths_are_translated(tmp_path, old, new):
    assert paths.resolve_project_path(old, tmp_path) == tmp_path / new
    assert paths.resolve_project_path(tmp_path / old, tmp_path) == tmp_path / new
    assert not (tmp_path / "var").exists()


def test_external_paths_and_current_layout_are_preserved(tmp_path):
    root = tmp_path / "project"
    external = tmp_path / "elsewhere/models/model.bin"
    assert paths.resolve_project_path(external, root) == external
    assert (
        paths.resolve_project_path("var/outputs/demo.json", root) == root / "var/outputs/demo.json"
    )
    assert (
        paths.resolve_project_path("experiments/results/demo.json", root)
        == root / "experiments/results/demo.json"
    )


def test_repository_has_named_image_modules_and_no_old_root_directories():
    assert (paths.FRAMEWORK_DIR / "api/http_server.py").is_file()
    assert (paths.VISUALIZATION_DIR / "package.json").is_file()
    assert not (paths.PROJECT_ROOT / "backend").exists()
    assert (paths.EDITGUARD_DIR / "options/test_editguard.yml").is_file()
    assert (paths.IMAGE_WATERMARK_DIR / "api/service.py").is_file()
    for old in paths.LEGACY_PREFIXES:
        assert not (paths.PROJECT_ROOT / old).exists(), f"Unexpected root directory: {old}"
