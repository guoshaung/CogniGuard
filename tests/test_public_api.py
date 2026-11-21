"""Contract checks for the public, model-independent framework namespace."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import cogniguard

ROOT = Path(__file__).resolve().parents[1]


def test_public_types_belong_to_the_public_implementation():
    assert len(cogniguard.__all__) == len(set(cogniguard.__all__))
    for name in cogniguard.__all__:
        public_type = getattr(cogniguard, name)
        assert public_type.__module__.startswith("cogniguard.governance.")


def test_historical_governance_imports_share_class_identity():
    for module in ("audit", "capability", "evidence", "lifecycle", "trust"):
        historical = importlib.import_module(f"core.governance.{module}")
        current = importlib.import_module(f"cogniguard.governance.{module}")
        for name in historical.__all__:
            assert getattr(historical, name) is getattr(current, name)
    historical_root = importlib.import_module("core.governance")
    for name in cogniguard.__all__:
        assert getattr(historical_root, name) is getattr(cogniguard, name)


def test_import_works_without_site_packages_or_domain_runtime():
    code = """
import json
import sys
import cogniguard
forbidden = ('langgraph', 'langsmith', 'torch', 'numpy', 'experiments', 'protection', 'core')
assert not any(name.split('.')[0] in forbidden for name in sys.modules)
assert 'cogniguard.api' not in sys.modules
print(json.dumps(cogniguard.__all__))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-S", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert json.loads(result.stdout) == cogniguard.__all__
