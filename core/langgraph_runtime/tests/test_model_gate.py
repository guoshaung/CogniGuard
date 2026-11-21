from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def test_real_model_entrypoint_requires_explicit_opt_in():
    result = subprocess.run(
        [sys.executable, "-m", "cogniguard", "redteam"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "--allow-model-calls" in result.stderr
