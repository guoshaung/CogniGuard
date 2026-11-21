from __future__ import annotations

from pathlib import Path

from scripts.server import preflight_image_watermark as preflight


def test_preflight_accepts_not_yet_created_runtime_directories(tmp_path: Path) -> None:
    args = preflight.parse_args(["--project-root", str(tmp_path)])
    report = preflight.CheckReport()

    _, output_root = preflight.check_paths(args, tmp_path, report)

    check = next(row for row in report.checks if row["name"] == "paths.output_root")
    assert output_root == tmp_path / "var" / "outputs" / "sce_locguard_jobs"
    assert check["status"] == "pass"
    assert check["details"]["checked_parent"] == str(tmp_path)
    assert not (tmp_path / "var").exists()


def test_linux_launchers_keep_python_cache_under_runtime_directory() -> None:
    scripts_dir = Path(__file__).parent
    launchers = [*scripts_dir.glob("*.sh"), *scripts_dir.glob("*.sbatch")]

    assert launchers
    for launcher in launchers:
        assert "export PYTHONPYCACHEPREFIX=" in launcher.read_text(encoding="utf-8")
        assert "/var/cache/python}" in launcher.read_text(encoding="utf-8")


def test_slurm_log_is_under_runtime_directory() -> None:
    source = (Path(__file__).parent / "image_watermark_benchmark.sbatch").read_text(
        encoding="utf-8"
    )
    assert "#SBATCH --output=var/logs/slurm-%x-%j.out" in source
