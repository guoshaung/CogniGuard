"""Domain protection packages.

Historical Layer1/Layer2 trees live in legacy/layers. Their old import names
still resolve, without a second copy at this directory.
"""

from __future__ import annotations

import sys
from importlib.machinery import ModuleSpec
from pathlib import Path

_LAYER_ROOT = Path(__file__).resolve().parent / "legacy" / "layers"


class _LegacyLayerFinder:
    """Resolve protection.Layer* to protection/legacy/layers/Layer*."""

    def find_spec(self, fullname, path, target=None):
        parts = fullname.split(".")
        if len(parts) < 2 or parts[0] != "protection" or not parts[1].startswith("Layer"):
            return None
        base = _LAYER_ROOT / parts[1]
        if not base.is_dir():
            return None
        leaf = base if len(parts) == 2 else base.joinpath(*parts[2:])
        module_file = leaf.with_suffix(".py")
        if module_file.is_file():
            from importlib.machinery import SourceFileLoader

            loader = SourceFileLoader(fullname, str(module_file))
            return ModuleSpec(fullname, loader, is_package=False)
        if leaf.is_dir():
            spec = ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(leaf)]
            return spec
        return None


if not any(finder.__class__.__name__ == "_LegacyLayerFinder" for finder in sys.meta_path):
    sys.meta_path.insert(0, _LegacyLayerFinder())
