"""Explicit read-only bridge to pre-existing heavyweight model dependencies.

The canonical graph environment stays small. Locked local torch/transformers
are loaded from the preserved model environment only in model-specific workers.
No package is installed into or removed from either environment here.
"""

from __future__ import annotations

import importlib.metadata
import site
from pathlib import Path

from core.paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def enable_existing_model_environment(root: Path = ROOT) -> dict[str, str]:
    old_site = Path(root) / ".venv" / "Lib" / "site-packages"
    if not old_site.is_dir():
        raise RuntimeError(f"Existing model environment is missing: {old_site}")
    site.addsitedir(str(old_site))
    versions = {}
    for package in ("torch", "transformers"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(
                f"Model dependency missing in preserved environment: {package}"
            ) from exc
    return versions
