"""Repository launchers and tool configuration retain their canonical paths."""

import json
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_entrypoints_are_kept_and_supporting_files_are_grouped():
    for name in ("run.cmd", "serve.cmd", "pyproject.toml", "requirements.txt"):
        assert (ROOT / name).is_file(), name
    assert not list(ROOT.glob("requirements-*"))
    for name in (
        "START_HERE.md",
        "CODE_MAP.md",
        "pytest.ini",
        "CogniGuard-focused.code-workspace",
        "requirements-langgraph.txt",
        "requirements-langgraph-lock.txt",
        "requirements-research.txt",
        "requirements-benchmarks.txt",
        "main.py",
        "server.py",
    ):
        assert not (ROOT / name).exists(), name
    for relative in (
        "docs/getting-started.md",
        "docs/code-map.md",
        "requirements/runtime.txt",
        "requirements/runtime-lock.txt",
        "requirements/research.txt",
        "requirements/benchmarks.txt",
        "cogniguard/cli.py",
        "cogniguard/api/__main__.py",
    ):
        assert (ROOT / relative).is_file(), relative


def test_editor_workspace_resolves_to_repository_root():
    path = ROOT / "tools/editor/CogniGuard.code-workspace"
    workspace = json.loads(path.read_text(encoding="utf-8"))
    assert len(workspace["folders"]) == 1
    assert (path.parent / workspace["folders"][0]["path"]).resolve() == ROOT


def test_pytest_uses_shared_pyproject_configuration(pytestconfig):
    assert Path(pytestconfig.inipath).resolve() == ROOT / "pyproject.toml"
    settings = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = settings["tool"]["pytest"]["ini_options"]
    assert expected["addopts"] == "--import-mode=importlib"
    assert expected["cache_dir"] == "var/cache/pytest"
    assert expected["norecursedirs"] == [
        "third_party",
        "var",
        "assets",
        ".git",
        ".venv",
        ".venv-langgraph",
        ".cache",
        ".tmp",
        "node_modules",
        ".bundle",
        ".python_deps",
        "artifacts",
        "experiments/results",
    ]
    assert pytestconfig.getini("norecursedirs") == expected["norecursedirs"]
    assert pytestconfig.getini("cache_dir") == expected["cache_dir"]
    assert pytestconfig.getoption("importmode") == "importlib"


def test_local_requirement_and_constraint_includes_exist_recursively():
    visited = set()

    def check_file(path):
        path = path.resolve()
        assert path.is_file(), f"Missing requirement or constraint file: {path}"
        if path in visited:
            return
        visited.add(path)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = re.match(
                r"^(?:-r\s*|-c\s*|--requirement(?:\s+|=)|--constraint(?:\s+|=))(.+)$",
                line.strip(),
            )
            if match is None:
                continue
            values = shlex.split(match.group(1), comments=True)
            assert values, f"Empty include at {path}:{number}"
            if "://" in values[0]:
                continue  # This check never fetches a remote requirements file.
            target = path.parent / values[0]
            assert target.is_file(), f"Missing local include at {path}:{number}: {target}"
            check_file(target)

    for relative in (
        "requirements.txt",
        "requirements/research.txt",
        "requirements/benchmarks.txt",
        "requirements/runtime-lock.txt",
    ):
        check_file(ROOT / relative)
