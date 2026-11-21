"""Compatibility import; implementation: cogniguard.workflows.education.research."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.workflows.education.research")
