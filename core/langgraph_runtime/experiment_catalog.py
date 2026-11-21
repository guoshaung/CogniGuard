"""Module-identity compatibility alias for cogniguard.workflows.experiment_catalog."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("cogniguard.workflows.experiment_catalog")
