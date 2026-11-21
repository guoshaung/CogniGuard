"""Compatibility import; implementation: cogniguard.workflows.education.protected_turn."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("cogniguard.workflows.education.protected_turn")
