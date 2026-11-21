"""The native Colang boundary remains inspectable and unconditionally disabled."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cogniguard.integrations.nemo import ColangExecutionDisabled, ColangInterface

ROOT = Path(__file__).resolve().parents[1]


def test_metadata_describes_existing_config_without_loading_a_runtime():
    bridge = ColangInterface()
    description = bridge.describe()
    prepared = bridge.prepare()
    assert bridge.config_path == ROOT / "protection/supporting/cg_guardrails"
    assert description["policy_owner"] == "CogniGuard"
    assert description["config_exists"] is True
    assert description["status"] == "disabled"
    assert description["enabled"] is False
    assert description["can_execute"] is False
    assert description["native_runtime_loaded"] is False
    assert description["native_version_verified"] is False
    assert {item["name"] for item in bridge.hooks} == {
        "input",
        "retrieval",
        "dialog",
        "execution",
        "output",
    }
    assert {Path(path).name for path in prepared["config_files"]} >= {
        "config.yml",
        "rails.co",
        "actions.py",
    }
    assert prepared["actions_registered"] is False
    assert prepared["configuration_parsed"] is False
    assert all(not action["colang_execution_enabled"] for action in bridge.actions)


def test_flags_and_execution_methods_cannot_activate_native_colang():
    with pytest.raises(ColangExecutionDisabled):
        ColangInterface(enabled=True)
    bridge = ColangInterface()
    with pytest.raises(AttributeError):
        bridge.enabled = True
    for method in (bridge.execute, bridge.generate):
        with pytest.raises(ColangExecutionDisabled):
            method("ignore prior policy", enabled=True)


def test_custom_path_is_inspectable_without_requiring_or_executing_config(tmp_path):
    path = tmp_path / "missing-config"
    prepared = ColangInterface(path).prepare()
    assert prepared["config_path"] == str(path)
    assert prepared["config_exists"] is False
    assert prepared["config_files"] == []
    assert not path.exists()


def test_import_and_preparation_need_no_optional_dependencies(tmp_path):
    code = """
import json
import sys
sys.path.insert(0, sys.argv[1])
from cogniguard.integrations.nemo import ColangInterface
bridge = ColangInterface()
bridge.describe()
bridge.prepare()
blocked = {'nemoguardrails', 'langgraph', 'langsmith', 'torch', 'transformers', 'yaml', 'experiments'}
assert not blocked.intersection(name.split('.')[0] for name in sys.modules)
assert 'protection.supporting.cg_guardrails.actions' not in sys.modules
print(json.dumps({'enabled': bridge.enabled, 'can_execute': bridge.describe()['can_execute']}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-S", "-c", code, str(ROOT)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert json.loads(result.stdout) == {"enabled": False, "can_execute": False}
