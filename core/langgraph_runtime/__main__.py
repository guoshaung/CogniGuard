"""Compatibility CLI; run ``python -m cogniguard.workflows`` for new callers."""
from importlib import import_module as _import_module
import sys as _sys

if __name__ == "__main__":
    raise SystemExit(_import_module("cogniguard.workflows.__main__").main())

_sys.modules[__name__] = _import_module("cogniguard.workflows.__main__")
