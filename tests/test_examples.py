"""Examples execute outside the checkout cwd without invoking real models."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_example(name: str, tmp_path: Path) -> dict:
    # Exercise checkout imports from an unrelated cwd. Explicit PYTHONPATH is a
    # test harness fallback, not evidence that editable installation succeeded.
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    script = ROOT / "examples" / name
    runner = """
import json
import runpy
import sys
namespace = runpy.run_path(sys.argv[1])
payload = namespace['run_example']()
payload['_imported_roots'] = sorted({name.split('.')[0] for name in sys.modules})
payload['_nonstdlib_roots'] = sorted(set(payload['_imported_roots']) - sys.stdlib_module_names - {'cogniguard', '__main__'})
print(json.dumps(payload))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", runner, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_governance_quickstart_has_predictable_decisions_and_light_imports(tmp_path):
    payload = run_example("quickstart.py", tmp_path)
    assert payload["audit_valid"] is True
    decisions = payload["decisions"]
    assert {name: item["action"] for name, item in decisions.items()} == {
        "allow": "allow",
        "refuse": "refuse",
        "quarantine": "quarantine",
    }
    assert decisions["allow"]["allowed_payload"] == {"question": "Explain 2 + 2."}
    assert decisions["allow"]["rollback_required"] is False
    for name in ("refuse", "quarantine"):
        assert decisions[name]["allowed_payload"] == {}
        assert decisions[name]["rollback_required"] is True
    assert not {"langgraph", "torch", "transformers", "experiments", "core"}.intersection(
        payload["_imported_roots"]
    )
    # Python startup on some installations also loads a setuptools site hook.
    assert set(payload["_nonstdlib_roots"]) <= {"_distutils_hack"}


def test_education_example_minimizes_profile_and_summarizes_without_a_model(tmp_path):
    payload = run_example("education.py", tmp_path)
    assert "x=2" in payload["answer"]
    assert payload["return_mode"] == "summary"
    assert payload["selected_record_ids"] == ["mastery-demo"]
    assert payload["teaching_input"]["resource_mode"] == "summary"
    assert "SYNTHETIC_PRIVATE_ADDRESS" not in json.dumps(payload)
    assert payload["lifecycle_governance_enabled"] is False
    assert payload["watermark_enabled"] is False
    assert payload["execution_mode"] == "offline_rule_based"
    assert not {"torch", "transformers", "experiments"}.intersection(payload["_imported_roots"])
