"""Module-identity compatibility alias for cogniguard.workflows.tool_jobs."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("cogniguard.workflows.tool_jobs")
